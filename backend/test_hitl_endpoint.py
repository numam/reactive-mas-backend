"""
Simulate exactly what the /hitl/simulate/scenario endpoint does.
"""
import sys, os, importlib.util, traceback
import pandas as pd
import numpy as np

MAS_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HITL_DIR = os.path.join(MAS_DIR, "hitl")
OUTPUT_HITL = os.path.join(HITL_DIR, "output_3mode")

for p in [MAS_DIR, HITL_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

def _imp(name, base, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(base, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_se = _imp("simulation_engine", HITL_DIR, "simulation_engine.py")
_rb = _imp("reactive_baseline", HITL_DIR, "reactive_baseline.py")
_sl = _imp("scenario_loader",   HITL_DIR, "scenario_loader.py")
_hm = _imp("hitl_module",       HITL_DIR, "hitl_module.py")
_rs = _imp("run_simulation",    HITL_DIR, "run_simulation.py")

run_scenario_hitl     = _se.run_scenario
run_reactive_scenario = _rb.run_reactive_scenario
CSVDataLoaderHITL     = _se.CSVDataLoader
MANAGER_PROFILES      = _hm.MANAGER_PROFILES
load_scenarios_hitl   = _sl.load_scenarios
get_scenario_hitl     = _sl.get_scenario
three_way_comparison  = _rs.three_way_comparison
save_scenario_outputs = _rs.save_scenario_outputs
summary_stats_hitl    = _rs.summary_statistics

_SCENARIOS_JSON = os.path.join(HITL_DIR, "scenarios_100.json")
_sl.reset_cache()
HITL_SCENARIOS = load_scenarios_hitl(json_path=_SCENARIOS_JSON, fallback=True)

def _csv_loader():
    return CSVDataLoaderHITL(data_dir=HITL_DIR)

def _run_one_mode(scenario, mode, seed, csv_ldr, verbose):
    sid = scenario["scenario_id"]
    results_this, stock_dfs, event_dfs, hitl_dfs = {}, [], [], []

    if mode == "reactive":
        rm, rs = run_reactive_scenario(scenario, csv_loader=csv_ldr,
                                        verbose=verbose, rng_seed=seed + sid)
        rm["mode"] = "reactive"
        rs = rs.copy(); rs["scenario_id"] = sid; rs["mode"] = "reactive"
        results_this["reactive"] = rm; stock_dfs.append(rs)
    else:
        s_seed = seed + sid if mode == "autonomous" else seed + sid * 2
        m, s, e, h = run_scenario_hitl(scenario, mode=mode, csv_loader=csv_ldr,
                                        verbose=verbose, rng_seed=s_seed)
        m["mode"] = mode
        s = s.copy(); s["scenario_id"] = sid; s["mode"] = mode
        e = e.copy(); e["scenario_id"] = sid; e["mode"] = mode
        results_this[mode] = m; stock_dfs.append(s)
        if not e.empty: event_dfs.append(e)
        if not h.empty:
            h = h.copy(); h["scenario_id"] = sid; hitl_dfs.append(h)

    print(f"  save_scenario_outputs for sid={sid}, mode={mode}")
    save_scenario_outputs(sid=sid, modes=[mode], results_this=results_this,
        stock_this=stock_dfs, events_this=event_dfs, hitl_this=hitl_dfs,
        output_dir=OUTPUT_HITL)
    print(f"  saved OK")

    mv = list(results_this.values())[0]
    sd = stock_dfs[0] if stock_dfs else pd.DataFrame()
    ed = event_dfs[0] if event_dfs else pd.DataFrame()
    hd = hitl_dfs[0]  if hitl_dfs  else pd.DataFrame()
    return {"mode": mode, "metrics": mv,
            "stock_log": sd.to_dict(orient="records"),
            "event_log": ed.to_dict(orient="records"),
            "hitl_log":  hd.to_dict(orient="records"),
            "saved_dir": os.path.join(OUTPUT_HITL, f"scenario_{sid:03d}")}

# Test scenario_id=1, mode="all"
scenario_id = 1
mode = "all"
rng_seed = 42
verbose = False

print(f"Testing scenario_id={scenario_id}, mode={mode}")
s = get_scenario_hitl(scenario_id, json_path=_SCENARIOS_JSON)
if s is None:
    print(f"ERROR: Skenario {scenario_id} tidak ditemukan")
    sys.exit(1)

modes = ["reactive", "autonomous", "hitl"] if mode == "all" else [mode]
ldr = _csv_loader()

try:
    results = [_run_one_mode(s, m, rng_seed, ldr, verbose) for m in modes]
    print(f"\nAll modes OK!")
    
    # Try three_way_comparison
    if mode == "all" and len(results) == 3:
        print("Testing three_way_comparison...")
        comp = three_way_comparison([results[0]["metrics"]],
                                    [results[1]["metrics"]],
                                    [results[2]["metrics"]])
        print(f"  comparison shape: {comp.shape}")
        print("  OK")
except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()
