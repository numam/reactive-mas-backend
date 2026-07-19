"""
╔══════════════════════════════════════════════════════════════════════╗
║  RUN SIMULATION — Main Entry Point v3                               ║
║  Uses simulation_engine.py with supply flow + proper HitL effect   ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
  python run_simulation.py                        # all 100, both modes
  python run_simulation.py --scenario 1           # single scenario
  python run_simulation.py --mode autonomous      # one mode only
  python run_simulation.py --scenario 1 --verbose
"""

import sys, os, argparse
import pandas as pd
import numpy as np
from scipy import stats

from simulation_engine import run_scenario, CSVDataLoader
from scenario_loader   import load_scenarios


def summary_statistics(all_metrics):
    cols = ["Stock Availability Rate (%)","Time to Recovery (hours)",
            "Stockout Duration (hours)","Stockout Frequency",
            "Min Stock During Disruption","Recovery Speed Index"]
    df_m = pd.DataFrame(all_metrics)
    rows = []
    for col in cols:
        if col not in df_m.columns:
            continue
        data = df_m[col].dropna()
        if len(data) < 2:
            continue
        n, mean, std = len(data), data.mean(), data.std()
        ci = stats.t.interval(0.95, df=n-1, loc=mean, scale=stats.sem(data))
        rows.append({
            "Metric"    : col, "N": n,
            "Mean"      : round(mean,3), "Std": round(std,3),
            "Min"       : round(data.min(),3), "Max": round(data.max(),3),
            "CI_95_Lo"  : round(ci[0],3), "CI_95_Hi": round(ci[1],3)
        })
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


def compare_modes(auto_m, hitl_m):
    higher_better = {"Stock Availability Rate (%)","Recovery Speed Index"}
    cols = ["Stock Availability Rate (%)","Time to Recovery (hours)",
            "Stockout Duration (hours)","Stockout Frequency","Recovery Speed Index"]
    df_a, df_h = pd.DataFrame(auto_m), pd.DataFrame(hitl_m)
    rows = []
    for col in cols:
        if col not in df_a.columns or col not in df_h.columns:
            continue
        a = df_a[col].dropna().mean()
        h = df_h[col].dropna().mean()
        # t-test
        t_stat, p_val = stats.ttest_ind(df_a[col].dropna(), df_h[col].dropna())
        delta     = h - a
        delta_pct = (delta / a * 100) if a != 0 else 0
        better    = "HitL" if (col in higher_better and h > a) or \
                              (col not in higher_better and h < a) else "Autonomous"
        rows.append({
            "Metric"         : col,
            "Autonomous_mean": round(a, 3),
            "HitL_mean"      : round(h, 3),
            "Delta"          : round(delta, 3),
            "Delta_%"        : round(delta_pct, 2),
            "t_stat"         : round(t_stat, 3),
            "p_value"        : round(p_val, 4),
            "Significant"    : "Yes" if p_val < 0.05 else "No",
            "Better"         : better,
        })
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="MAS + HitL Poultry SC Simulation v3")
    parser.add_argument("--scenario",   type=int, default=None)
    parser.add_argument("--mode",       choices=["autonomous","hitl","both"], default="both")
    parser.add_argument("--verbose",    action="store_true")
    parser.add_argument("--output-dir", type=str, default="./output_v3")
    parser.add_argument("--data-dir",   type=str, default=".")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    np.random.seed(args.seed)

    # Load CSV data
    csv_loader = CSVDataLoader(data_dir=args.data_dir)
    loaded = list(csv_loader._cache.keys())

    # Load scenarios
    all_scenarios = load_scenarios(
        json_path=os.path.join(args.data_dir, "scenarios_100.json"),
        fallback=True
    )
    scenarios = ([s for s in all_scenarios if s["scenario_id"] == args.scenario]
                 if args.scenario else all_scenarios)
    if not scenarios:
        print(f"ERROR: Scenario {args.scenario} not found"); sys.exit(1)

    modes = ["autonomous","hitl"] if args.mode == "both" else [args.mode]

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  MAS + HitL — Avian Influenza | Poultry Supply Chain v3     ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"  Scenarios: {len(scenarios)} | Mode: {args.mode.upper()} | Seed: {args.seed}")
    print(f"  CSV loaded: {loaded if loaded else 'NONE'}")
    print(f"  Supply flow: ENABLED | HitL delay: ENABLED")
    print("╚══════════════════════════════════════════════════════════════╝")

    results   = {"autonomous":[], "hitl":[]}
    all_stock, all_events, all_hitl = [], [], []

    for scenario in scenarios:
        for mode in modes:
            print(f"\n[S{scenario['scenario_id']:03d}|{mode.upper()[:4]}] "
                  f"{scenario.get('subtype',''):25s} | {scenario['severity']:6s} ...",
                  end=" " if not args.verbose else "\n")

            metrics, stock_df, event_df, hitl_df = run_scenario(
                scenario, mode=mode, csv_loader=csv_loader,
                verbose=args.verbose,
                rng_seed=args.seed + scenario["scenario_id"] * (2 if mode=="hitl" else 1)
            )
            metrics["mode"] = mode
            stock_df["scenario_id"] = scenario["scenario_id"]
            stock_df["mode"]        = mode
            event_df["scenario_id"] = scenario["scenario_id"]
            event_df["mode"]        = mode

            results[mode].append(metrics)
            all_stock.append(stock_df)
            all_events.append(event_df)
            if not hitl_df.empty:
                hitl_df["scenario_id"] = scenario["scenario_id"]
                all_hitl.append(hitl_df)

            if not args.verbose:
                sar = metrics.get("Stock Availability Rate (%)", "N/A")
                ttr = metrics.get("Time to Recovery (hours)", "N/A")
                sod = metrics.get("Stockout Duration (hours)", "N/A")
                print(f"SAR={sar}% | TTR={ttr}h | SOD={sod}h")

    # ── Save outputs ──────────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print("  SAVING RESULTS...")

    all_m = pd.DataFrame(results["autonomous"] + results["hitl"])
    all_m.to_csv(f"{args.output_dir}/scenario_metrics.csv", index=False)
    pd.concat(all_stock,  ignore_index=True).to_csv(f"{args.output_dir}/stock_log_all.csv", index=False)
    pd.concat(all_events, ignore_index=True).to_csv(f"{args.output_dir}/event_log_all.csv", index=False)
    print(f"  ✓ scenario_metrics.csv | stock_log_all.csv | event_log_all.csv")

    if all_hitl:
        pd.concat(all_hitl, ignore_index=True).to_csv(f"{args.output_dir}/hitl_decision_log.csv", index=False)
        print(f"  ✓ hitl_decision_log.csv")

    for mode in modes:
        if results[mode]:
            s = summary_statistics(results[mode])
            s.to_csv(f"{args.output_dir}/summary_{mode}.csv")
            print(f"\n  SUMMARY — {mode.upper()} (n={len(results[mode])})")
            print(s.to_string() if not s.empty else "  insufficient data")

    if args.mode == "both" and results["autonomous"] and results["hitl"]:
        comp = compare_modes(results["autonomous"], results["hitl"])
        comp.to_csv(f"{args.output_dir}/comparison_auto_vs_hitl.csv")
        print(f"\n  COMPARISON — Autonomous vs HitL")
        print(comp.to_string() if not comp.empty else "  insufficient data")

    # ── Per-severity summary ──────────────────────────────────────────
    print(f"\n  SAR BY SEVERITY (Autonomous):")
    auto_df = pd.DataFrame(results["autonomous"])
    for sev in ["low","medium","high","crisis"]:
        sub = auto_df[auto_df["severity"]==sev]["Stock Availability Rate (%)"].dropna()
        if len(sub) > 0:
            print(f"    {sev:8s}: n={len(sub):2d}  mean={sub.mean():.1f}%  "
                  f"std={sub.std():.1f}  range=[{sub.min():.1f},{sub.max():.1f}]")

    print(f"\n  Output saved to: {args.output_dir}/")
    print("═"*65)


if __name__ == "__main__":
    main()
