"""
╔══════════════════════════════════════════════════════════════════════╗
║  RUN SIMULATION — Entry Point Utama                                  ║
║  MAS Poultry Supply Chain Resilience                                 ║
║                                                                      ║
║  Menjalankan 3 mode secara otomatis:                                ║
║    Mode 1: Reactive Baseline (tanpa koordinasi MAS)                 ║
║    Mode 2: MAS Autonomous   (koordinasi penuh, tanpa HitL)          ║
║    Mode 3: MAS + HitL       (koordinasi + advisory manusia)         ║
║                                                                      ║
║  Struktur output:                                                    ║
║    output_3mode/                                                     ║
║      scenario_001/          ← hasil per skenario                    ║
║        metrics.csv                                                   ║
║        stock_log.csv                                                 ║
║        event_log.csv                                                 ║
║        hitl_decision_log.csv                                        ║
║      scenario_002/ ...                                               ║
║      scenario_metrics_3mode.csv   ← gabungan semua skenario         ║
║      stock_log_all.csv                                               ║
║      event_log_all.csv                                               ║
║      hitl_decision_log.csv                                           ║
║      summary_reactive.csv                                            ║
║      summary_autonomous.csv                                          ║
║      summary_hitl.csv                                                ║
║      comparison_3mode.csv                                            ║
║                                                                      ║
║  Cara menjalankan:                                                   ║
║    python run_simulation.py                    ← semua 100 skenario ║
║    python run_simulation.py --scenario 1       ← skenario 1 saja   ║
║    python run_simulation.py --scenario 1 --verbose                  ║
║    python run_simulation.py --mode autonomous  ← satu mode saja    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import argparse
import numpy as np
import pandas as pd
from scipy import stats

# Pastikan folder ini ada di path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation_engine  import run_scenario, CSVDataLoader
from reactive_baseline  import run_reactive_scenario
from scenario_loader    import load_scenarios, reset_cache


# ════════════════════════════════════════════════════════════════════
# SUMMARY STATISTICS
# ════════════════════════════════════════════════════════════════════

def summary_statistics(metrics_list: list) -> pd.DataFrame:
    cols = [
        "Stock Availability Rate (%)",
        "Time to Recovery (hours)",
        "Stockout Duration (hours)",
        "Stockout Frequency",
        "Min Stock During Disruption",
        "Recovery Speed Index",
    ]
    df   = pd.DataFrame(metrics_list)
    rows = []
    for col in cols:
        if col not in df.columns:
            continue
        data = df[col].dropna()
        if len(data) < 2:
            continue
        n, mean, sd = len(data), data.mean(), data.std()
        ci = stats.t.interval(0.95, df=n-1, loc=mean, scale=stats.sem(data))
        rows.append({
            "Metric"  : col,
            "N"       : n,
            "Mean"    : round(mean, 3),
            "Std"     : round(sd,   3),
            "Min"     : round(data.min(), 3),
            "Max"     : round(data.max(), 3),
            "CI_95_Lo": round(ci[0], 3),
            "CI_95_Hi": round(ci[1], 3),
        })
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


def three_way_comparison(reactive, autonomous, hitl) -> pd.DataFrame:
    cols = [
        ("Stock Availability Rate (%)", True),
        ("Stockout Duration (hours)",   False),
        ("Stockout Frequency",          False),
        ("Recovery Speed Index",        True),
        ("Time to Recovery (hours)",    False),
    ]
    dr = pd.DataFrame(reactive)
    da = pd.DataFrame(autonomous)
    dh = pd.DataFrame(hitl)
    rows = []
    for col, higher_better in cols:
        if col not in dr.columns:
            continue
        r = dr[col].dropna()
        a = da[col].dropna()
        h = dh[col].dropna()
        if len(r) < 2:
            continue
        t_ar, p_ar = stats.ttest_ind(a, r)
        t_ha, p_ha = stats.ttest_ind(h, a)
        t_hr, p_hr = stats.ttest_ind(h, r)

        def sig(p):
            return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

        def delta_pct(new, base):
            return round((new - base) / base * 100, 1) if base != 0 else 0.0

        rows.append({
            "Metric"          : col,
            "Reactive_mean"   : round(r.mean(), 3),
            "Auto_mean"       : round(a.mean(), 3),
            "HitL_mean"       : round(h.mean(), 3),
            "Auto_vs_R_pct"   : delta_pct(a.mean(), r.mean()),
            "Auto_vs_R_p"     : round(p_ar, 4),
            "Auto_vs_R_sig"   : sig(p_ar),
            "HitL_vs_A_pct"   : delta_pct(h.mean(), a.mean()),
            "HitL_vs_A_p"     : round(p_ha, 4),
            "HitL_vs_A_sig"   : sig(p_ha),
            "HitL_vs_R_pct"   : delta_pct(h.mean(), r.mean()),
            "HitL_vs_R_p"     : round(p_hr, 4),
            "HitL_vs_R_sig"   : sig(p_hr),
        })
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# PER-SCENARIO SAVE HELPER
# ════════════════════════════════════════════════════════════════════

def save_scenario_outputs(sid: int, modes: list, results_this: dict,
                           stock_this: list, events_this: list,
                           hitl_this: list, output_dir: str):
    """
    Simpan hasil satu skenario ke subfolder output_dir/scenario_XXX/.
    File selalu di-overwrite — data lama diganti data terbaru.
    Deduplikasi antar-skenario dilakukan di level file gabungan (upsert_csv).
    """
    scen_dir = os.path.join(output_dir, f"scenario_{sid:03d}")
    os.makedirs(scen_dir, exist_ok=True)

    # metrics.csv — satu baris per mode, append jika sudah ada (dedup by mode)
    rows = []
    for mode in modes:
        if results_this.get(mode):
            rows.append(results_this[mode])
    if rows:
        new_df = pd.DataFrame(rows)
        m_path = os.path.join(scen_dir, "metrics.csv")
        if os.path.exists(m_path):
            existing = pd.read_csv(m_path)
            combined = pd.concat([existing, new_df], ignore_index=True)
            if "mode" in combined.columns:
                combined = combined.drop_duplicates(subset=["mode"], keep="last")
            combined.to_csv(m_path, index=False)
        else:
            new_df.to_csv(m_path, index=False)

    # stock_log.csv — overwrite langsung (data lengkap per run)
    if stock_this:
        pd.concat(stock_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "stock_log.csv"), index=False)

    # event_log.csv
    if events_this:
        pd.concat(events_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "event_log.csv"), index=False)

    # hitl_decision_log.csv
    if hitl_this:
        pd.concat(hitl_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "hitl_decision_log.csv"), index=False)




def main():
    parser = argparse.ArgumentParser(
        description="MAS Poultry Supply Chain Simulation — 3-Mode Comparison"
    )
    parser.add_argument("--scenario",    type=int,    default=None,
                        help="Nomor skenario (default: semua 100)")
    parser.add_argument("--mode",        choices=["reactive","autonomous","hitl","all"],
                        default="all",
                        help="Mode simulasi (default: all → 3 mode sekaligus)")
    parser.add_argument("--verbose",     action="store_true",
                        help="Tampilkan detail per tick")
    parser.add_argument("--output-dir",  type=str, default="./output_3mode",
                        help="Folder output (default: ./output_3mode)")
    parser.add_argument("--seed",        type=int, default=42,
                        help="Random seed (default: 42)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    np.random.seed(args.seed)

    # ── Load data normal dari CSV ─────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_loader = CSVDataLoader(data_dir=script_dir)
    loaded     = list(csv_loader._cache.keys())

    # ── Load skenario ─────────────────────────────────────────────
    reset_cache()
    json_path  = os.path.join(script_dir, "scenarios_100.json")
    scenarios  = load_scenarios(json_path=json_path, fallback=True)

    if args.scenario:
        scenarios = [s for s in scenarios if s["scenario_id"] == args.scenario]
        if not scenarios:
            print(f"ERROR: Skenario {args.scenario} tidak ditemukan.")
            sys.exit(1)

    modes = (["reactive","autonomous","hitl"]
             if args.mode == "all" else [args.mode])

    # ── Header ───────────────────────────────────────────────────
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  MAS Poultry Supply Chain — 3-Mode Simulation               ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"  Skenario  : {len(scenarios)}")
    print(f"  Mode      : {', '.join(m.upper() for m in modes)}")
    print(f"  Seed      : {args.seed}")
    print(f"  CSV loaded: {loaded if loaded else 'TIDAK ADA — pakai default schema'}")
    print(f"  Output    : {args.output_dir}/")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    results   = {m: [] for m in ["reactive","autonomous","hitl"]}
    all_stock  = []
    all_events = []
    all_hitl   = []

    for scenario in scenarios:
        sid  = scenario["scenario_id"]
        sev  = scenario["severity"]
        sub  = scenario.get("subtype","")

        print(f"[S{sid:03d}] {sub:<28} | {sev:<7}", end="")

        # Kumpulan hasil skenario ini saja (untuk disimpan per folder)
        results_this = {}
        stock_this   = []
        events_this  = []
        hitl_this    = []

        # ── Mode Reactive ─────────────────────────────────────────
        if "reactive" in modes:
            rm, rs = run_reactive_scenario(
                scenario, csv_loader=csv_loader,
                verbose=args.verbose,
                rng_seed=args.seed + sid
            )
            rm["mode"] = "reactive"
            rs["scenario_id"] = sid
            rs["mode"]        = "reactive"
            results["reactive"].append(rm)
            results_this["reactive"] = rm
            all_stock.append(rs)
            stock_this.append(rs)

        # ── Mode Autonomous ───────────────────────────────────────
        if "autonomous" in modes:
            am, as_, ae, _ = run_scenario(
                scenario, mode="autonomous",
                csv_loader=csv_loader,
                verbose=args.verbose,
                rng_seed=args.seed + sid
            )
            am["mode"]        = "autonomous"
            as_["scenario_id"] = sid
            as_["mode"]        = "autonomous"
            ae["scenario_id"]  = sid
            ae["mode"]         = "autonomous"
            results["autonomous"].append(am)
            results_this["autonomous"] = am
            all_stock.append(as_)
            stock_this.append(as_)
            if not ae.empty:
                all_events.append(ae)
                events_this.append(ae)

        # ── Mode HitL ─────────────────────────────────────────────
        if "hitl" in modes:
            hm, hs, he, hd = run_scenario(
                scenario, mode="hitl",
                csv_loader=csv_loader,
                verbose=args.verbose,
                rng_seed=args.seed + sid * 2
            )
            hm["mode"]        = "hitl"
            hs["scenario_id"] = sid
            hs["mode"]        = "hitl"
            he["scenario_id"] = sid
            he["mode"]        = "hitl"
            results["hitl"].append(hm)
            results_this["hitl"] = hm
            all_stock.append(hs)
            stock_this.append(hs)
            if not he.empty:
                all_events.append(he)
                events_this.append(he)
            if not hd.empty:
                hd["scenario_id"] = sid
                all_hitl.append(hd)
                hitl_this.append(hd)

        # ── Simpan hasil skenario ini ke subfolder ────────────────
        save_scenario_outputs(
            sid      = sid,
            modes    = modes,
            results_this = results_this,
            stock_this   = stock_this,
            events_this  = events_this,
            hitl_this    = hitl_this,
            output_dir   = args.output_dir,
        )

        # ── Print ringkasan baris ini ─────────────────────────────
        r_sar = results["reactive"][-1]["Stock Availability Rate (%)"] \
                if "reactive" in modes else "-"
        a_sar = results["autonomous"][-1]["Stock Availability Rate (%)"] \
                if "autonomous" in modes else "-"
        h_sar = results["hitl"][-1]["Stock Availability Rate (%)"] \
                if "hitl" in modes else "-"

        if args.mode == "all":
            print(f" R={r_sar:.1f}% A={a_sar:.1f}% H={h_sar:.1f}%"
                  f"  → saved: scenario_{sid:03d}/")
        else:
            sar = locals().get(f"{args.mode[0]}m",{}).get("Stock Availability Rate (%)","N/A")
            print(f" SAR={sar}%  → saved: scenario_{sid:03d}/")

    # ════════════════════════════════════════════════════════════════
    # SIMPAN OUTPUT GABUNGAN (semua skenario)
    # Jika file sudah ada → append + dedup, bukan buat file baru
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*65}")
    print("  MENYIMPAN HASIL GABUNGAN...")

    def upsert_csv(filepath: str, new_df: pd.DataFrame,
                   dedup_keys: list):
        """
        Jika filepath sudah ada: baca → gabung → deduplikasi → simpan.
        Jika belum ada: simpan langsung.
        Dedup berdasarkan dedup_keys — baris lama diganti data baru
        untuk kombinasi key yang sama.
        """
        if os.path.exists(filepath):
            existing = pd.read_csv(filepath)
            # Gabung: existing dulu, new di bawah
            combined = pd.concat([existing, new_df], ignore_index=True)
            # Deduplikasi: keep='last' → data terbaru menang
            keys_present = [k for k in dedup_keys if k in combined.columns]
            if keys_present:
                combined = combined.drop_duplicates(
                    subset=keys_present, keep='last')
            combined = combined.sort_values(
                keys_present, ignore_index=True) if keys_present else combined
            combined.to_csv(filepath, index=False)
            return "updated"
        else:
            new_df.to_csv(filepath, index=False)
            return "created"

    # Gabungkan semua metrics run ini
    all_metrics = []
    for mode in modes:
        all_metrics.extend(results[mode])
    df_all = pd.DataFrame(all_metrics)

    p = os.path.join(args.output_dir, "scenario_metrics_3mode.csv")
    act = upsert_csv(p, df_all, ["scenario_id", "mode"])
    print(f"  ✓ scenario_metrics_3mode.csv  ({len(df_all)} baris baru, {act})")

    if all_stock:
        df_stock = pd.concat(all_stock, ignore_index=True)
        p = os.path.join(args.output_dir, "stock_log_all.csv")
        act = upsert_csv(p, df_stock, ["scenario_id", "mode", "tick", "node_type"])
        print(f"  ✓ stock_log_all.csv  ({act})")

    if all_events:
        df_ev = pd.concat(all_events, ignore_index=True)
        p = os.path.join(args.output_dir, "event_log_all.csv")
        act = upsert_csv(p, df_ev, ["scenario_id", "mode", "log_id"])
        print(f"  ✓ event_log_all.csv  ({act})")

    if all_hitl:
        df_hd = pd.concat(all_hitl, ignore_index=True)
        p = os.path.join(args.output_dir, "hitl_decision_log.csv")
        act = upsert_csv(p, df_hd, ["scenario_id", "tick", "tier"])
        print(f"  ✓ hitl_decision_log.csv  ({act})")

    # Summary per mode — selalu di-overwrite karena dihitung ulang dari
    # seluruh scenario_metrics_3mode.csv agar statistiknya konsisten
    full_metrics = pd.read_csv(
        os.path.join(args.output_dir, "scenario_metrics_3mode.csv"))
    for mode in ["reactive", "autonomous", "hitl"]:
        subset = full_metrics[full_metrics["mode"] == mode].to_dict("records")
        if subset:
            s = summary_statistics(subset)
            p = os.path.join(args.output_dir, f"summary_{mode}.csv")
            s.to_csv(p)
            print(f"  ✓ summary_{mode}.csv  (dihitung ulang dari {len(subset)} baris)")

    # ════════════════════════════════════════════════════════════════
    # TAMPILKAN HASIL
    # ════════════════════════════════════════════════════════════════
    print(f"\n{'═'*65}")
    print("  HASIL SIMULASI")
    print(f"{'═'*65}")

    if args.mode == "all" and all(results[m] for m in ["reactive","autonomous","hitl"]):
        # Hitung comparison dari data gabungan terbaru (bukan hanya run ini)
        full_r = full_metrics[full_metrics["mode"]=="reactive"].to_dict("records")
        full_a = full_metrics[full_metrics["mode"]=="autonomous"].to_dict("records")
        full_h = full_metrics[full_metrics["mode"]=="hitl"].to_dict("records")

        if full_r and full_a and full_h:
            comp = three_way_comparison(full_r, full_a, full_h)
            p = os.path.join(args.output_dir, "comparison_3mode.csv")
            comp.to_csv(p)
            print(f"  ✓ comparison_3mode.csv  (dihitung ulang dari {len(full_metrics)} baris)")

            n_scen = len(full_metrics) // 3
            print(f"\n  THREE-WAY COMPARISON (n={n_scen} per mode)")
            print(f"  {'Metrik':<35} {'Reactive':>9} {'Auto':>9} {'HitL':>9} "
                  f"{'A-R%':>8} {'H-A%':>8} {'sig':>4}")
            print(f"  {'-'*85}")
            for idx, row in comp.iterrows():
                print(f"  {idx:<35} {row['Reactive_mean']:>9.2f} "
                      f"{row['Auto_mean']:>9.2f} {row['HitL_mean']:>9.2f} "
                      f"{row['Auto_vs_R_pct']:>+8.1f}% {row['HitL_vs_A_pct']:>+8.1f}% "
                      f"{row['Auto_vs_R_sig']:>4}")

            print(f"\n  SAR PER SEVERITY (dari {len(full_metrics)} total baris):")
            col = "Stock Availability Rate (%)"
            for sev in ["low","medium","high","crisis"]:
                rs_ = full_metrics[(full_metrics.mode=="reactive")   & (full_metrics.severity==sev)][col].dropna()
                as_ = full_metrics[(full_metrics.mode=="autonomous") & (full_metrics.severity==sev)][col].dropna()
                hs_ = full_metrics[(full_metrics.mode=="hitl")       & (full_metrics.severity==sev)][col].dropna()
                if len(rs_) > 0:
                    print(f"    {sev:8s} n={len(rs_):2d}: "
                          f"Reactive={rs_.mean():.1f}%  "
                          f"Auto={as_.mean():.1f}% ({as_.mean()-rs_.mean():+.1f}%)  "
                          f"HitL={hs_.mean():.1f}% ({hs_.mean()-rs_.mean():+.1f}%)")

        if results["hitl"]:
            print(f"\n  HitL DECISION METRICS:")
            dh2 = pd.DataFrame(results["hitl"])
            for c in ["HitL_Accept_Rate_%","HitL_Override_Rate_%","HitL_Mean_HRT_hours"]:
                if c in dh2.columns:
                    d = dh2[c].dropna()
                    print(f"    {c:<35}: {d.mean():.3f} ± {d.std():.3f}")
    else:
        for mode in modes:
            if results[mode]:
                s = summary_statistics(results[mode])
                print(f"\n  SUMMARY — {mode.upper()}")
                print(s.to_string() if not s.empty else "  (data tidak cukup)")

    print(f"\n  Output tersimpan di: {args.output_dir}/")
    print(f"  Per-skenario       : {args.output_dir}/scenario_XXX/")
    print(f"{'═'*65}")


if __name__ == "__main__":
    main()
