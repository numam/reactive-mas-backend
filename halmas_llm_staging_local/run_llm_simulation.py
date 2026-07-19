"""
run_llm_simulation.py
========================
Main entry point for HALMAS-LLM experiments. Re-implements the per-tick
loop from simulation_engine.run_scenario() with exactly one change: the
HitL manager object is an LLMHitLEngine (LLM-backed) instead of a
HitLEngine (probabilistic), for the two new conditions C2 (CoT) and
C3 (ToT). Condition C1 (probabilistic) is run by calling Paper 1's
simulation_engine.run_scenario() directly and unmodified, so that C1 in
this paper's results is not a re-implementation but the original code.

This file does not modify simulation_engine.py. Every class and function
reused below (NodeAgent, CoordinatingAgent, SupplyFlowEngine,
calculate_metrics, AGENT_DATABASE, init_node_state, get_disruption_schedule)
is imported as-is from Paper 1's modules.

Usage
-----
    python run_llm_simulation.py --provider gemini --strategy cot \
        --api-key-env GEMINI_API_KEY --scenarios 1-100 --out outputs/

    python run_llm_simulation.py --strategy probabilistic --scenarios 1-100

Run --help for the full argument list.
"""

import argparse
import os
import re
import sys
import time
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ── Paper 1 modules, imported unmodified ──────────────────────────
from agent_database import AGENT_DATABASE, init_node_state
from scenario_loader import get_disruption_schedule, get_scenario, load_scenarios
import simulation_engine as se  # NodeAgent, CoordinatingAgent, SupplyFlowEngine, calculate_metrics
from simulation_engine import (
    CHAIN_ORDER, TICK_HOURS, TICK_MINUTES,
    NodeAgent, CoordinatingAgent, SupplyFlowEngine, calculate_metrics,
)

# ── New HALMAS-LLM modules ─────────────────────────────────────────
from llm_hitl_engine import LLMHitLEngine

PROVIDERS = {}
try:
    from provider_ollama import OllamaProvider
    PROVIDERS["ollama"] = OllamaProvider
except ImportError:
    pass
try:
    from provider_deepseek import DeepSeekProvider
    PROVIDERS["deepseek"] = DeepSeekProvider
except ImportError:
    pass
try:
    from provider_llama import LlamaProvider
    PROVIDERS["llama"] = LlamaProvider
except ImportError:
    pass
try:
    from provider_gemini import GeminiProvider
    PROVIDERS["gemini"] = GeminiProvider
except ImportError:
    pass
try:
    from provider_claude import ClaudeProvider
    PROVIDERS["claude"] = ClaudeProvider
except ImportError:
    pass
try:
    from provider_openai import OpenAIProvider
    PROVIDERS["openai"] = OpenAIProvider
except ImportError:
    pass


# ════════════════════════════════════════════════════════════════════
# CORE LOOP — identical to simulation_engine.run_scenario(), with the
# HitL engine construction swapped for an LLMHitLEngine.
# ════════════════════════════════════════════════════════════════════

def run_llm_scenario(scenario: dict, llm_engine_factory, csv_loader=None,
                      verbose: bool = False, rng_seed: int = None):
    """
    Run one scenario using an LLM-backed HitL engine.

    Parameters
    ----------
    scenario : one scenario dict from scenarios_100.json
    llm_engine_factory : a zero-argument callable that returns a fresh
        LLMHitLEngine for this scenario (it needs the per-scenario
        `agents` dict, which only exists once this function starts, so
        a factory closure is used rather than passing an engine instance
        directly -- see run_condition() below for how this is built)
    csv_loader, verbose, rng_seed : same meaning as in
        simulation_engine.run_scenario()

    Returns
    -------
    metrics, stock_df, event_df, hitl_df : same 4-tuple shape as
        simulation_engine.run_scenario(), so downstream aggregation code
        is identical for C1 (probabilistic) and C2/C3 (LLM) results.
    """
    np.random.seed(rng_seed)
    rng = np.random.default_rng(rng_seed)
    start_dt = datetime.strptime(scenario["start_datetime"], "%Y-%m-%d %H:%M")
    total_ticks = int(scenario["duration_hours"] / TICK_HOURS)

    if verbose:
        print(f"\n{'=' * 65}")
        print(f"  S{scenario['scenario_id']:03d} | {scenario.get('subtype', '')} "
              f"| {scenario['severity']} | mode=LLM")
        print(f"{'=' * 65}")

    agents = {}
    for tier in CHAIN_ORDER:
        if csv_loader:
            db_state = csv_loader.get_initial_state(tier, rng)
        else:
            db_state = init_node_state(tier)
        agents[tier] = NodeAgent(
            node_type=tier,
            node_id=AGENT_DATABASE[tier]["meta"]["node_id"],
            db_state=db_state,
        )

    coordinator = CoordinatingAgent()
    hitl = llm_engine_factory(agents)  # <-- the one substitution vs. Paper 1
    supply_flow = SupplyFlowEngine()

    schedule = get_disruption_schedule(scenario["scenario_id"])
    disrupt_map = {}
    for ev in schedule:
        tk = int(ev["at_hour"] / TICK_HOURS)
        disrupt_map.setdefault(tk, []).append(ev)

    stock_log = []
    hrt_delays = {}

    for tick in range(total_ticks):
        current_time = start_dt + timedelta(minutes=TICK_MINUTES * tick)

        if tick in disrupt_map:
            for ev in disrupt_map[tick]:
                agents[ev["node"]].inject_disruption(ev.get("db_changes", {}))
                if verbose:
                    status = "DISRUPTED" if ev["disrupted"] else "RECOVERING"
                    print(f"\n  [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"{ev.get('event_id', '')} {ev['node'].upper()} {status}")

        for agent in agents.values():
            agent.consume_demand()

        supply_flow.deliver(tick, agents)
        supply_flow.compute_flow(tick, agents, mode="hitl", pending_signals=hrt_delays)

        reports = []
        for agent in agents.values():
            r = agent.scan(tick, current_time, verbose)
            if r:
                reports.append(r)

        signals = []
        for report in reports:
            signals.extend(coordinator.receive_report(report, agents, verbose))

        hrt_delays = {}
        for signal in signals:
            tier = signal["target_type"]
            instructions = signal.get("instructions", [])
            if not instructions or tier not in agents:
                continue

            dec = hitl.process_signal(
                signal, tick=tick,
                timestamp=current_time.strftime("%Y-%m-%d %H:%M"),
                urgency=signal.get("urgency", "normal"),
            )
            final_inst = dec.final_instructions
            if dec.response_time > 0:
                hrt_delays[f"{tier}_hrt"] = dec.response_time
                if tier == "wholesaler":
                    hrt_delays["wholesaler_to_retail_hrt"] = dec.response_time
                if tier == "slaughterhouse":
                    hrt_delays["slaughter_to_wholesaler_hrt"] = dec.response_time
            if verbose and dec.decision != "accept":
                print(f"    [{current_time.strftime('%H:%M')}] "
                      f"{tier}: {dec.decision.upper()} "
                      f"factor={dec.modification_factor:.2f} "
                      f"HRT={dec.response_time:.2f}h")

            agents[tier].apply_instruction(final_inst)

        for tier, agent in agents.items():
            entry = {
                "tick": tick, "timestamp": current_time.strftime("%Y-%m-%d %H:%M"),
                "node_id": agent.node_id, "node_type": tier, "disrupted": agent.disrupted,
            }
            if tier == "retail":
                entry.update({
                    "retail_inventory": agent.db_state.get("retail_inventory"),
                    "safety_stock": agent.db_state.get("safety_stock"),
                    "stockout_flag": agent.db_state.get("stockout_flag", 0),
                    "shortage_duration": agent.db_state.get("shortage_duration", 0),
                    "sales_rate": agent.db_state.get("sales_rate"),
                    "reorder_request": agent.db_state.get("reorder_request", 0),
                })
            elif tier == "wholesaler":
                entry["inventory_level"] = agent.db_state.get("inventory_level")
                entry["pending_shipments"] = agent.db_state.get("pending_shipments")
            elif tier == "farm":
                entry["production_capacity"] = agent.db_state.get("production_capacity")
                entry["mortality_rate"] = agent.db_state.get("mortality_rate")
            elif tier == "slaughterhouse":
                entry["processing_capacity"] = agent.db_state.get("processing_capacity")
                entry["output_stock"] = agent.db_state.get("output_stock")
            elif tier == "supplier":
                entry["available_supply"] = agent.db_state.get("available_supply")
            stock_log.append(entry)

    metrics = calculate_metrics(stock_log, coordinator, scenario, hitl, csv_loader)
    stock_df = pd.DataFrame(stock_log)
    event_df = pd.DataFrame(coordinator.event_log)
    hitl_df = hitl.get_log_df()

    if verbose:
        print(f"\n  -- Metrics (LLM/{hitl.strategy.upper()}) --")
        for k, v in metrics.items():
            if k not in ("scenario_id", "disruption_type", "subtype", "seed_node"):
                print(f"    {k:<38}: {v}")

    return metrics, stock_df, event_df, hitl_df


# ════════════════════════════════════════════════════════════════════
# CONDITION RUNNER — runs all scenarios for one condition (C1/C2/C3)
# ════════════════════════════════════════════════════════════════════

def parse_scenario_range(spec: str, n_total: int = 100) -> list[int]:
    """Parse '1-100', '1,5,9', or '1-10,50,90-100' into a sorted list of ints."""
    ids = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            ids.update(range(int(a), int(b) + 1))
        elif part:
            ids.add(int(part))
    return sorted(i for i in ids if 1 <= i <= n_total)


def run_condition(strategy: str, scenario_ids: list[int], provider_name: str = None,
                   api_key: str = None, model_name: str = None, rng_seed: int = 42,
                   verbose: bool = False, out_dir: str = "outputs") -> dict:
    """
    Run one full experimental condition (Table 7) across the given
    scenario IDs and write its outputs to `out_dir`.

    strategy : "probabilistic" | "cot" | "tot"

    Resume behaviour: if output CSVs already exist from a previous (interrupted)
    run, completed scenario IDs are loaded from them and skipped automatically.
    This means the program can be safely interrupted (laptop sleep, Ctrl-C, etc.)
    and re-run with the same command — it will continue from where it left off.
    """
    os.makedirs(out_dir, exist_ok=True)

    metrics_path = os.path.join(out_dir, f"scenario_metrics_{strategy}.csv")
    hitl_path    = os.path.join(out_dir, f"llm_decision_log_{strategy}.csv")

    # ── Resume: load already-completed scenarios from existing CSVs ───
    completed_ids = set()
    all_metrics   = []
    all_hitl_logs = []

    if os.path.exists(metrics_path):
        prev_metrics = pd.read_csv(metrics_path)
        if "scenario_id" in prev_metrics.columns:
            completed_ids = set(prev_metrics["scenario_id"].dropna().astype(int).tolist())
            all_metrics   = [row.to_dict() for _, row in prev_metrics.iterrows()]
            print(f"  [RESUME] Found {len(completed_ids)} completed scenario(s) in {metrics_path} — skipping them.")

    if os.path.exists(hitl_path):
        prev_hitl = pd.read_csv(hitl_path, sep=";")
        if not prev_hitl.empty:
            all_hitl_logs.append(prev_hitl)

    # Filter out already-completed scenarios
    remaining_ids = [sid for sid in scenario_ids if sid not in completed_ids]
    if not remaining_ids:
        print("  [RESUME] All scenarios already completed. Nothing to do.")
        metrics_df  = pd.DataFrame(all_metrics)
        hitl_log_df = pd.concat(all_hitl_logs, ignore_index=True) if all_hitl_logs else pd.DataFrame()
        return {"metrics": metrics_df, "hitl_log": hitl_log_df}

    experiment_start = time.time()  # wall-clock timer for this run session

    if strategy == "probabilistic":
        for sid in remaining_ids:
            scenario = get_scenario(sid)
            metrics, stock_df, event_df, hitl_df = se.run_scenario(
                scenario, mode="hitl", verbose=verbose, rng_seed=rng_seed)
            metrics["condition"] = "C1_probabilistic"
            all_metrics.append(metrics)
            if not hitl_df.empty:
                hitl_df["scenario_id"] = sid
                hitl_df["strategy"] = "probabilistic"
                all_hitl_logs.append(hitl_df)

            # Save incrementally after every scenario so progress is never lost
            _save_incremental(all_metrics, all_hitl_logs, metrics_path, hitl_path)
            print(f"  [C1] scenario {sid:3d} done | SAR={metrics.get('Stock Availability Rate (%)'):.1f}%")

    elif strategy in ("cot", "tot"):
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown or unavailable provider {provider_name!r}. "
                              f"Available: {list(PROVIDERS.keys())}")
        ProviderClass = PROVIDERS[provider_name]
        provider_kwargs = {"api_key": api_key}
        if model_name:
            provider_kwargs["model_name"] = model_name

        scenario_elapsed_times = []

        for sid in remaining_ids:
            scenario = get_scenario(sid)
            provider = ProviderClass(**provider_kwargs)

            def factory(agents, _provider=provider, _strategy=strategy, _sid=sid):
                return LLMHitLEngine(provider=_provider, strategy=_strategy,
                                      scenario_id=_sid, agents=agents)

            t0 = time.time()
            metrics, stock_df, event_df, hitl_df = run_llm_scenario(
                scenario, llm_engine_factory=factory, verbose=verbose, rng_seed=rng_seed)
            elapsed = time.time() - t0
            scenario_elapsed_times.append(elapsed)

            metrics["condition"] = f"C{'2' if strategy == 'cot' else '3'}_{strategy}"
            all_metrics.append(metrics)
            if not hitl_df.empty:
                all_hitl_logs.append(hitl_df)

            # Save incrementally after every scenario so progress is never lost
            _save_incremental(all_metrics, all_hitl_logs, metrics_path, hitl_path)

            done      = len(scenario_elapsed_times)
            remaining = len(remaining_ids) - done
            avg_s     = sum(scenario_elapsed_times) / done
            eta_s     = avg_s * remaining
            eta_str   = _fmt_duration(eta_s) if remaining > 0 else "—"

            print(f"  [{strategy.upper()}] scenario {sid:3d} done in {elapsed:.1f}s | "
                  f"SAR={metrics.get('Stock Availability Rate (%)'):.1f}% | "
                  f"n_decisions={len(hitl_df)} | "
                  f"ETA {eta_str} ({remaining} left)")
    else:
        raise ValueError(f"Unknown strategy {strategy!r}")

    experiment_total_s = time.time() - experiment_start

    metrics_df  = pd.DataFrame(all_metrics)
    hitl_log_df = pd.concat(all_hitl_logs, ignore_index=True) if all_hitl_logs else pd.DataFrame()

    print(f"\n  Wrote {metrics_path} ({len(metrics_df)} rows)")
    print(f"  Wrote {hitl_path} ({len(hitl_log_df)} rows)")

    # ── Experiment duration summary (shown for cot/tot only) ──────────
    if strategy in ("cot", "tot"):
        condition_label = f"C{'2' if strategy == 'cot' else '3'}_{strategy.upper()}"
        n_decisions = len(hitl_log_df) if not hitl_log_df.empty else 0
        print(f"\n{'=' * 55}")
        print(f"  EXPERIMENT COMPLETE — {condition_label}")
        print(f"{'=' * 55}")
        print(f"  Scenarios run      : {len(scenario_ids)}")
        print(f"  Total LLM decisions: {n_decisions}")
        if n_decisions > 0 and not hitl_log_df.empty:
            mean_lat = hitl_log_df["api_latency_ms"].mean() / 1000.0
            print(f"  Mean LLM latency   : {mean_lat:.1f}s per call")
        print(f"  Total wall-clock   : {_fmt_duration(experiment_total_s)}")
        print(f"{'=' * 55}\n")

    return {"metrics": metrics_df, "hitl_log": hitl_log_df}


def _save_incremental(all_metrics: list, all_hitl_logs: list,
                       metrics_path: str, hitl_path: str) -> None:
    """
    Write current progress to CSV after every completed scenario.
    Called inside the scenario loop so that if the process is interrupted
    (sleep, Ctrl-C, crash), all completed scenarios are already saved and
    can be resumed from on the next run.
    """
    pd.DataFrame(all_metrics).to_csv(metrics_path, index=False)
    hitl_log_df = pd.concat(all_hitl_logs, ignore_index=True) if all_hitl_logs else pd.DataFrame()
    hitl_log_df.to_csv(hitl_path, index=False, sep=";")


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as 'Xh Ym Zs' for readability."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Run HALMAS-LLM experiments (Table 7 conditions).")
    parser.add_argument("--strategy", required=True, choices=["probabilistic", "cot", "tot"],
                         help="Experimental condition to run (C1/C2/C3).")
    parser.add_argument("--provider", default="llama", choices=list(PROVIDERS.keys()) or ["llama"],
                         help="LLM provider to use for cot/tot strategies. Ignored for probabilistic.")
    parser.add_argument("--api-key", default=None, help="API key string. Overrides --api-key-env. "
                                                        "Not required for Ollama (local).")
    parser.add_argument("--api-key-env", default="OLLAMA_API_KEY",
                         help="Environment variable to read the API key from "
                              "(default: OLLAMA_API_KEY; not required for Ollama local).")
    parser.add_argument("--model-name", default=None,
                         help="Override the provider's default model name, "
                              "e.g. gemini-2.0-flash, gemini-1.5-pro.")
    parser.add_argument("--scenarios", default="1-100",
                         help="Scenario ID range/list, e.g. '1-100', '1-10,50,90-100'. Default: 1-100.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42, matches Paper 1).")
    parser.add_argument("--out", default="outputs", help="Output directory (default: outputs/).")
    parser.add_argument("--verbose", action="store_true", help="Print per-tick detail.")
    args = parser.parse_args()

    scenario_ids = parse_scenario_range(args.scenarios)
    print(f"Running strategy={args.strategy} on {len(scenario_ids)} scenario(s): "
          f"{scenario_ids[:5]}{'...' if len(scenario_ids) > 5 else ''}")

    api_key = args.api_key or os.environ.get(args.api_key_env) or ""
    if args.strategy != "probabilistic" and args.provider not in ("ollama", "deepseek", "llama") and not api_key:
        print(f"ERROR: no API key found. Set {args.api_key_env} or pass --api-key.", file=sys.stderr)
        sys.exit(1)

    run_condition(
        strategy=args.strategy, scenario_ids=scenario_ids, provider_name=args.provider,
        api_key=api_key, model_name=args.model_name, rng_seed=args.seed,
        verbose=args.verbose, out_dir=args.out,
    )


if __name__ == "__main__":
    main()
