# HALMAS-LLM — Setup & Usage

This package extends HALMAS (Paper 1) with an LLM-backed HitL Advisory
Layer. The Supply Chain Layer, Coordination Layer, and all 18+23 ECA rules
are reused from Paper 1 without modification. Only the HitL manager model
is replaced for the CoT and ToT conditions.

## 1. Setup

```bash
pip install -r requirements.txt --break-system-packages
```

Get a free Gemini API key at https://aistudio.google.com/app/apikey,
then set it as an environment variable:

```bash
export GEMINI_API_KEY="your-key-here"
```

(On Windows PowerShell: `$env:GEMINI_API_KEY="your-key-here"`)

## 2. File Map

| File | Role |
|---|---|
| `agent_database.py`, `disruption_triggers.py`, `orchestrator_rules.py`, `hitl_module.py`, `simulation_engine.py`, `reactive_baseline.py`, `scenario_loader.py`, `scenario_generator.py`, `scenario_validator.py`, `run_simulation.py`, `scenarios_100.json`, `data_normal_*.csv` | **Paper 1, unmodified.** Copied as-is. |
| `prompts/personas.json` | 5 tier-manager personas (Block 1) |
| `prompts/prompt_template_cot.txt` | CoT prompt template (Blocks 1–5a) |
| `prompts/prompt_template_tot.txt` | ToT prompt template (Blocks 1–5b) |
| `prompts/output_schema.json` | Expected JSON schema + parse-failure policy |
| `09_llm_provider_base.py` (alias `llm_provider_base.py`) | Abstract `LLMProvider` interface, shared retry/parse logic |
| `09a_provider_gemini.py` (alias `provider_gemini.py`) | Concrete Gemini implementation (REST API, no SDK needed) |
| `10_prompt_builder.py` (alias `prompt_builder.py`) | Fills templates from live DB state + matched rule |
| `11_llm_hitl_engine.py` (alias `llm_hitl_engine.py`) | `LLMHitLEngine` — drop-in replacement for `HitLEngine` |
| `run_llm_simulation.py` | **Entry point.** Runs one condition (C1/C2/C3) across scenarios. |

## 3. Running an Experiment

Condition C1 (probabilistic baseline — re-runs Paper 1 directly, unmodified):
```bash
python run_llm_simulation.py --strategy probabilistic --scenarios 1-100 --out outputs
```

Condition C2 (Chain-of-Thought, Gemini):
```bash
python run_llm_simulation.py --strategy cot --provider gemini \
    --scenarios 1-100 --out outputs
```

Condition C3 (Tree-of-Thought, Gemini):
```bash
python run_llm_simulation.py --strategy tot --provider gemini \
    --scenarios 1-100 --out outputs
```

Useful flags:
- `--scenarios 1-10` — test on a small subset first before running all 100
  (recommended, to check API cost and behaviour before a full run)
- `--model-name gemini-1.5-pro` — override the default `gemini-2.0-flash`
- `--verbose` — print per-tick detail (recommended only with a small
  `--scenarios` range)
- `--seed 42` — fixed by default, matches Paper 1

## 4. Outputs

Each run of `run_llm_simulation.py` writes two files to `--out`:

- `scenario_metrics_<strategy>.csv` — same columns as Paper 1's
  `scenario_metrics_3mode.csv`, plus a `condition` column (`C1_probabilistic`,
  `C2_cot`, or `C3_tot`)
- `llm_decision_log_<strategy>.csv` (semicolon-separated, like Paper 1's
  `hitl_decision_log.csv`) — one row per manager decision, including
  `justification` (full LLM reasoning text, for Section 5.3 Reasoning
  Quality Analysis), `tokens_in`/`tokens_out`/`api_latency_ms` (for
  Section 5.4 Cost-Benefit Analysis), and `prompt_sha256` (for Appendix B
  reproducibility logging)

Run all three conditions, then combine the three `scenario_metrics_*.csv`
files (e.g. `pd.concat`) for the cross-condition comparison in Section 5.1.

## 5. Cost Estimate

Before running all 100 scenarios, test on a small range first:

```bash
python run_llm_simulation.py --strategy cot --provider gemini --scenarios 1-5 --out outputs_test
```

Check `outputs_test/llm_decision_log_cot.csv` — the `tokens_in` and
`tokens_out` columns let you estimate total cost before committing to a
full 100-scenario run across both CoT and ToT.

## 6. Adding Another Provider (e.g. Claude, GPT)

Create `09b_provider_claude.py` (or `09c_provider_openai.py`) implementing
the same `LLMProvider` interface as `09a_provider_gemini.py` — only the
`call()` method needs a provider-specific implementation. Then create an
alias file (`provider_claude.py`) and `run_llm_simulation.py` will pick it
up automatically (see the `try/except ImportError` block near the top of
that file) as `--provider claude`.

## 7. Known Limitations (carried over from the paper draft)

- Results are tied to whichever model name is pinned at run time; a
  different model version may produce different decisions even with
  identical prompts (Appendix B).
- `temperature=0` maximises determinism but Gemini, like other providers,
  does not guarantee bit-for-bit reproducibility across calls.
- The Supplier tier was observed to receive few or no logged HitL decisions
  in some Paper 1 runs (see Section 5.2.3 of the Paper 1 manuscript); this
  is a property of which scenarios trigger Supplier-targeted instructions,
  not a bug in this codebase, but it should be checked again once C2/C3
  results are available.
