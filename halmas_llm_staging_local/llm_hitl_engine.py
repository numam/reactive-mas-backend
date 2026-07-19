"""
11_llm_hitl_engine.py
========================
LLMHitLEngine: a drop-in replacement for HitLEngine (08_hitl_module.py /
hitl_module.py) from Paper 1. Implements the exact same public interface
(process_signal, get_log_df, get_override_rate, get_mean_hrt, get_summary)
so that simulation_engine.py does not need any modification -- only the
line that constructs the `hitl` object needs to change (see
run_llm_simulation.py).

Where HitLEngine draws a random outcome from a fixed probability profile,
LLMHitLEngine sends a structured prompt to an LLM provider (Section 3.2)
and parses a structured decision back. TIMEOUT is not produced by the LLM
itself -- it is assigned here when the elapsed wall-clock time of the API
call exceeds the tier's nominal response-time limit (Table 6), mirroring
how Paper 1 treats a manager who does not respond in time. This keeps the
two engines comparable: HitLEngine's "response_time" is a *simulated*
duration; LLMHitLEngine's "response_time" is the model's *actual* API
latency, with the same timeout semantics applied on top.
"""

import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from hitl_module import MANAGER_PROFILES, ManagerDecision
from prompt_builder import build_prompt, build_instruction_text, prompt_hash
from orchestrator_rules import ORCHESTRATOR_RULES


@dataclass
class LLMHitLLogEntry:
    """
    Extends Paper 1's HitLLogEntry with LLM-specific fields (justification
    text, model name, prompt hash, token counts) needed for Section 5.3
    Reasoning Quality Analysis and Appendix B reproducibility logging.
    """
    tick: int
    timestamp: str
    tier: str
    rule_id: str
    urgency: str
    decision: str
    response_time: float
    modification_factor: float
    n_instructions: int
    rationale: str
    # LLM-specific additions:
    strategy: str = ""           # "cot" | "tot" | "probabilistic"
    model_name: str = ""
    provider_name: str = ""
    justification: str = ""
    prompt_sha256: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    api_latency_ms: float = 0.0
    parse_ok: bool = True
    timed_out: bool = False
    scenario_id: Optional[int] = None


class LLMHitLEngine:
    """
    Same public interface as HitLEngine, backed by an LLM provider.

    Parameters
    ----------
    provider : an instance of a concrete LLMProvider subclass
               (e.g. GeminiProvider from 09a_provider_gemini.py)
    strategy : "cot" or "tot" -- which prompt template (Block 5) to use
    rng_seed : unused by the LLM call itself (the LLM call is whatever
               determinism `temperature=0` gives it), but kept for
               interface parity with HitLEngine and for any future
               provider that needs a local seed (e.g. sampling among
               candidate responses).
    """

    def __init__(self, provider, strategy: str = "cot", rng_seed: Optional[int] = None,
                 scenario_id: Optional[int] = None, agents: Optional[dict] = None):
        """
        agents : reference to the live {tier_name: NodeAgent} dict from the
                 running simulation (simulation_engine.py's `agents` local
                 variable). Paper 1's signal dict does not carry db_state
                 (HitLEngine never needed it -- it only uses the tier name
                 to look up a fixed probability profile), so LLMHitLEngine
                 reads each tier's current db_state directly from this
                 reference at call time instead. See run_llm_simulation.py
                 for how this reference is wired in without modifying
                 simulation_engine.py itself.
        """
        self.provider = provider
        self.strategy = strategy
        self.scenario_id = scenario_id
        self.agents = agents or {}
        self.log: list[LLMHitLLogEntry] = []
        self._counts = {
            t: {"accept": 0, "modify": 0, "override": 0, "timeout": 0}
            for t in MANAGER_PROFILES
        }
        # Decision history per tier, for Block 4 of the prompt
        self._history: dict[str, list[dict]] = {t: [] for t in MANAGER_PROFILES}

    def process_signal(self, signal: dict, tick: int,
                        timestamp: str, urgency: str = "normal") -> ManagerDecision:
        """
        Same signature as HitLEngine.process_signal(). Builds a prompt,
        calls the LLM provider, applies the timeout rule, logs the result,
        and returns a ManagerDecision compatible with simulation_engine.py.
        """
        tier = signal.get("target_type", "")
        instructions = signal.get("instructions", [])
        rule_id = signal.get("rule_id", "R1")

        if tier not in MANAGER_PROFILES or not instructions:
            return ManagerDecision(
                tier=tier, decision="accept", response_time=0.0,
                original_instructions=instructions, final_instructions=instructions,
                modification_factor=1.0, rationale="No review needed",
            )

        profile = MANAGER_PROFILES[tier]
        timeout_limit_h = profile["timeout_hours"]

        rule = ORCHESTRATOR_RULES.get(rule_id, {})
        rule_label = rule.get("decision", rule_id)
        instruction_text = build_instruction_text(instructions)

        # db_state is read live from the agents dict reference (see __init__
        # docstring), not from the signal dict -- Paper 1's signal never
        # carried it. Falls back to {} if the agent reference is missing,
        # in which case the prompt builder will show "N/A" for every field
        # rather than failing outright.
        agent = self.agents.get(tier)
        db_state = dict(agent.db_state) if agent is not None else {}

        prompt = build_prompt(
            tier=tier, db_state=db_state, rule_id=rule_id, rule_label=rule_label,
            urgency=urgency, instruction_text=instruction_text,
            decision_history=self._history[tier], strategy=self.strategy,
        )

        t0 = time.time()
        call_result, parsed = self.provider.call_and_parse(prompt)
        wall_clock_s = time.time() - t0
        # Convert the API call's wall-clock latency into a "response time"
        # in hours, on the same scale as Table 6's HRT limits. This is a
        # deliberate simplification (Section 5.3 / Appendix B): real
        # manager response time is not bounded by API latency, but using
        # latency here lets the timeout mechanism described above apply
        # consistently without inventing a separate stochastic model for
        # "how long the LLM took to decide", which would defeat the
        # purpose of replacing the probabilistic model in the first place.
        response_time_h = wall_clock_s / 3600.0

        timed_out = response_time_h > timeout_limit_h
        if timed_out or not parsed.parse_ok:
            decision = "timeout"
            final = instructions
            factor = 1.0
            justification = parsed.justification if not parsed.parse_ok else (
                f"{profile['role']} response exceeded the {timeout_limit_h}h limit "
                f"(API latency-derived); auto-accept applied."
            )
        else:
            decision = parsed.decision.lower()
            factor = parsed.factor
            if decision == "accept":
                factor = 1.0
                final = instructions
            else:
                final = self._apply_factor(instructions, factor)
            justification = parsed.justification

        self._counts[tier][decision] += 1
        self._history[tier].append({"rule_id": rule_id, "decision": decision, "factor": factor})

        self.log.append(LLMHitLLogEntry(
            tick=tick, timestamp=timestamp, tier=tier, rule_id=rule_id, urgency=urgency,
            decision=decision, response_time=round(response_time_h, 4),
            modification_factor=round(factor, 3), n_instructions=len(instructions),
            rationale=justification, strategy=self.strategy,
            model_name=getattr(self.provider, "model_name", ""),
            provider_name=getattr(self.provider, "provider_name", ""),
            justification=justification, prompt_sha256=prompt_hash(prompt),
            tokens_in=getattr(call_result, "tokens_in", 0),
            tokens_out=getattr(call_result, "tokens_out", 0),
            api_latency_ms=getattr(call_result, "latency_ms", 0.0),
            parse_ok=parsed.parse_ok, timed_out=timed_out,
            scenario_id=self.scenario_id,
        ))

        return ManagerDecision(
            tier=tier, decision=decision, response_time=response_time_h,
            original_instructions=instructions, final_instructions=final,
            modification_factor=factor, rationale=justification,
        )

    @staticmethod
    def _apply_factor(instructions: list, factor: float) -> list:
        """Identical logic to HitLEngine._apply_factor (hitl_module.py),
        duplicated here so this module has no dependency on a HitLEngine
        *instance* -- only on the shared dataclasses/constants."""
        result = []
        for inst in instructions:
            ni = dict(inst)
            op = inst.get("operation", "")
            val = inst.get("value")
            if op in ("multiply", "add", "subtract") and isinstance(val, (int, float)):
                if op == "multiply":
                    ni["value"] = round(1.0 + (val - 1.0) * factor, 4)
                else:
                    ni["value"] = round(val * factor, 4)
            result.append(ni)
        return result

    # ── Metrics (same interface as HitLEngine) ──────────────────────

    def get_log_df(self) -> pd.DataFrame:
        if not self.log:
            return pd.DataFrame()
        return pd.DataFrame([vars(e) for e in self.log])

    def get_override_rate(self) -> dict:
        rates = {}
        for tier, counts in self._counts.items():
            total = sum(counts.values())
            rates[tier] = (counts["override"] / total) if total else 0.0
        return rates

    def get_mean_hrt(self) -> dict:
        df = self.get_log_df()
        if df.empty:
            return {t: 0.0 for t in MANAGER_PROFILES}
        return df.groupby("tier")["response_time"].mean().to_dict()

    def get_summary(self) -> dict:
        """
        Same key names as HitLEngine.get_summary() (hitl_module.py), so
        that simulation_engine.py's calculate_metrics() works unmodified
        regardless of which engine produced the log. Adds LLM-specific
        keys (token/latency/parse-failure stats) alongside, which
        calculate_metrics() simply ignores since it only reads the keys
        it knows about.
        """
        df = self.get_log_df()
        if df.empty:
            return {}
        total = len(df)
        return {
            "total_decisions": total,
            "accept_rate_%": round(len(df[df.decision == "accept"]) / total * 100, 2),
            "modify_rate_%": round(len(df[df.decision == "modify"]) / total * 100, 2),
            "override_rate_%": round(len(df[df.decision == "override"]) / total * 100, 2),
            "timeout_rate_%": round(len(df[df.decision == "timeout"]) / total * 100, 2),
            "mean_HRT_hours": round(float(df.response_time.mean()), 3),
            "mean_modification_factor": round(float(df.modification_factor.mean()), 3),
            "override_rate_per_tier": self.get_override_rate(),
            "mean_HRT_per_tier": self.get_mean_hrt(),
            # LLM-specific additions:
            "parse_failure_rate_%": round((1 - df["parse_ok"].mean()) * 100, 2),
            "mean_tokens_in": round(float(df["tokens_in"].mean()), 1),
            "mean_tokens_out": round(float(df["tokens_out"].mean()), 1),
            "mean_api_latency_ms": round(float(df["api_latency_ms"].mean()), 1),
        }
