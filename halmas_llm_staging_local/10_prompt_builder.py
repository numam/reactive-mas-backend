"""
10_prompt_builder.py
======================
Builds the final prompt string sent to an LLM provider, by combining:
  - prompts/personas.json        (Block 1, persona text + state field list)
  - the tier's current DB state  (Block 2, injected at runtime)
  - the matched orchestrator rule (Block 3, instruction being reviewed)
  - decision history             (Block 4, last 3 decisions this session)
  - prompts/prompt_template_cot.txt or prompt_template_tot.txt (Block 5)

This module has no knowledge of which LLM provider will receive the
prompt; it only produces a plain string. See 11_llm_hitl_engine.py for
how this is wired into the simulation loop.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_HERE, "prompts")

with open(os.path.join(_PROMPTS_DIR, "personas.json"), encoding="utf-8") as f:
    PERSONAS = json.load(f)

with open(os.path.join(_PROMPTS_DIR, "prompt_template_cot.txt"), encoding="utf-8") as f:
    TEMPLATE_COT = f.read()

with open(os.path.join(_PROMPTS_DIR, "prompt_template_tot.txt"), encoding="utf-8") as f:
    TEMPLATE_TOT = f.read()

_TEMPLATES = {"cot": TEMPLATE_COT, "tot": TEMPLATE_TOT}


def _format_state_lines(tier: str, db_state: dict) -> str:
    """
    Render Block 2 lines for a tier, e.g.:
      - production_capacity : 120 ekor  (threshold: < 60% planned)
    Only fields listed in personas.json[tier]["state_fields"] are shown,
    so the prompt always matches the variables defined for that tier in
    Table 3 (Section 3.4.1) -- no extra or missing fields.
    """
    persona = PERSONAS[tier]
    lines = []
    for field in persona["state_fields"]:
        key = field["key"]
        value = db_state.get(key, "N/A")
        unit = field.get("unit", "")
        note = field.get("threshold_note", "")
        unit_str = f" {unit}" if unit else ""
        note_str = f"  ({note})" if note else ""
        lines.append(f"  - {field['label']:<22}: {value}{unit_str}{note_str}")
    return "\n".join(lines)


def _format_decision_history(history: list) -> str:
    """
    Render Block 4. `history` is a list of up to 3 dicts:
        {"rule_id": "R4", "decision": "ACCEPT", "factor": 1.0}
    Most recent last. Returns a placeholder string if history is empty
    (i.e. this is the manager's first decision in the scenario).
    """
    if not history:
        return "(No prior decisions in this session.)"
    lines = []
    for h in history[-3:]:
        lines.append(f"  - Rule {h.get('rule_id', '?')}: {h.get('decision', '?')} "
                      f"(factor={h.get('factor', 1.0):.2f})")
    return "\n".join(lines)


def build_prompt(tier: str, db_state: dict, rule_id: str, rule_label: str,
                  urgency: str, instruction_text: str, decision_history: list,
                  strategy: str = "cot") -> str:
    """
    Build the complete prompt string for one LLM Manager Agent call.

    Parameters
    ----------
    tier : one of "supplier", "farm", "slaughterhouse", "wholesaler", "retail"
    db_state : current DB state dict for this tier (same shape as used by
               disruption_triggers.check_disruption)
    rule_id : e.g. "R4"
    rule_label : human-readable label for the rule, e.g. "Potential Disruption"
                 (this is ORCHESTRATOR_RULES[rule_id]["decision"] in Paper 1's
                 code -- "decision" there means "what the rule decided about
                 the disruption pattern", not the manager's decision)
    urgency : "normal" | "high" | "crisis"
    instruction_text : human-readable description of the instruction this
                        tier was given (built from ORCHESTRATOR_RULES[rule_id]
                        ["instructions"][tier])
    decision_history : list of up to 3 prior decision dicts this session
    strategy : "cot" or "tot" -- selects which Block 5 template is used

    Returns
    -------
    str : the complete prompt, ready to send to LLMProvider.call()
    """
    if strategy not in _TEMPLATES:
        raise ValueError(f"Unknown strategy {strategy!r}; expected 'cot' or 'tot'")

    persona = PERSONAS[tier]
    persona_text = persona["persona_text"].format(
        years_experience=persona.get("years_experience", 10),
        flock_size=persona.get("flock_size", "N/A"),
    )

    template = _TEMPLATES[strategy]
    prompt = template.format(
        persona_text=persona_text,
        tier_upper=tier.upper(),
        state_lines=_format_state_lines(tier, db_state),
        rule_id=rule_id,
        rule_label=rule_label,
        urgency=urgency,
        instruction_text=instruction_text,
        decision_history=_format_decision_history(decision_history),
    )
    return prompt


def build_instruction_text(instructions: list) -> str:
    """
    Convert ORCHESTRATOR_RULES[rule_id]["instructions"][tier] (a list of
    {variable, operation, value, description, ...} dicts) into a single
    human-readable line for Block 3. If there are multiple instructions
    for this tier under one rule, they are joined with "; ".
    """
    if not instructions:
        return "(No specific instruction for this tier under this rule.)"
    parts = []
    for instr in instructions:
        desc = instr.get("description")
        if desc:
            parts.append(desc)
        else:
            parts.append(f"{instr.get('variable')} {instr.get('operation')} {instr.get('value')}")
    return "; ".join(parts)


def prompt_hash(prompt: str) -> str:
    """SHA-256 hash of the prompt string, for the reproducibility log (Table 5)."""
    import hashlib
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
