"""
Simulate the full endpoint response including _make_response serialization.
"""
import sys, os, importlib.util, traceback, json
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
load_scenarios_hitl   = _sl.load_scenarios
get_scenario_hitl     = _sl.get_scenario
three_way_comparison  = _rs.three_way_comparison
save_scenario_outputs = _rs.save_scenario_outputs

_SCENARIOS_JSON = os.path.join(HITL_DIR, "scenarios_100.json")
_sl.reset_cache()
HITL_SCENARIOS = load_scenarios_hitl(json_path=_SCENARIOS_JSON, fallback=True)

def _safe(v):
    if v is None: return None
    if isinstance(v, np.integer): return int(v)
    if isinstance(v, (np.floating, float)):
        return None if (np.isnan(v) or np.isinf(v)) else float(v)
    if isinstance(v, np.bool_): return bool(v)
    if isinstance(v, np.ndarray): return [_safe(x) for x in v.tolist()]
    if isinstance(v, dict): return {k: _safe(val) for k, val in v.items()}
    if isinstance(v, list): return [_safe(x) for x in v]
    return v

def _df_records(df):
    return [_safe(row) for row in df.to_dict(orient="records")]

def _metrics_clean(m):
    return _safe({k: v for k, v in m.items() if k != "Rules Triggered"})

scenario_id = 1
mode = "all"
rng_seed = 42
verbose = False

s = get_scenario_hitl(scenario_id, json_path=_SCENARIOS_JSON)
ldr = CSVDataLoaderHITL(data_dir=HITL_DIR)
modes = ["reactive", "autonomous", "hitl"]

results_raw = []

for m in modes:
    sid = s["scenario_id"]
    results_this, stock_dfs, event_dfs, hitl_dfs = {}, [], [], []

    if m == "reactive":
        rm, rs = run_reactive_scenario(s, csv_loader=ldr, verbose=False, rng_seed=rng_seed+sid)
        rm["mode"] = "reactive"
        rs = rs.copy(); rs["scenario_id"] = sid; rs["mode"] = "reactive"
        results_this["reactive"] = rm; stock_dfs.append(rs)
    else:
        s_seed = rng_seed + sid if m == "autonomous" else rng_seed + sid * 2
        mm, ss, ee, hh = run_scenario_hitl(s, mode=m, csv_loader=ldr, verbose=False, rng_seed=s_seed)
        mm["mode"] = m
        ss = ss.copy(); ss["scenario_id"] = sid; ss["mode"] = m
        ee = ee.copy(); ee["scenario_id"] = sid; ee["mode"] = m
        results_this[m] = mm; stock_dfs.append(ss)
        if not ee.empty: event_dfs.append(ee)
        if not hh.empty:
            hh = hh.copy(); hh["scenario_id"] = sid; hitl_dfs.append(hh)

    mv = list(results_this.values())[0]
    sd = stock_dfs[0] if stock_dfs else pd.DataFrame()
    ed = event_dfs[0] if event_dfs else pd.DataFrame()
    hd = hitl_dfs[0]  if hitl_dfs  else pd.DataFrame()
    
    # Check for NaN/Inf in metrics
    print(f"\n=== Mode: {m} metrics ===")
    for k, v in mv.items():
        if k == "Rules Triggered": continue
        try:
            cleaned = _safe(v)
            if cleaned is None and v is not None:
                print(f"  WARNING: {k} = {v!r} -> None (NaN/Inf)")
            else:
                print(f"  {k}: {cleaned}")
        except Exception as e:
            print(f"  ERROR on {k}: {e}")
    
    results_raw.append({"mode": m, "metrics": mv, "stock_df": sd, "event_df": ed, "hitl_df": hd})

# Try serializing
print("\n=== Serialization Test ===")
try:
    results_out = []
    for r in results_raw:
        m = r["mode"]
        mv = r["metrics"]
        sd = r["stock_df"]
        ed = r["event_df"]
        hd = r["hitl_df"]
        out = {"mode": m, "metrics": _metrics_clean(mv),
               "stock_log": _df_records(sd), "event_log": _df_records(ed),
               "hitl_log": _df_records(hd)}
        results_out.append(out)

    payload = {"scenario_id": scenario_id, "mode": mode,
               "results": results_out, "comparison": None}
    
    def _default(obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.bool_): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.floating):
            return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
        raise TypeError(f"Not serializable: {type(obj)}")
    
    j = json.dumps(_safe(payload), default=_default, allow_nan=False)
    print(f"Serialization OK: {len(j)} bytes")
except Exception as e:
    print(f"Serialization ERROR: {e}")
    traceback.print_exc()
