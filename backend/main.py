"""
FastAPI Backend — MAS Poultry Supply Chain Resilience v2.0
Reactive Baseline Mode — 100 Avian Influenza Scenarios
"""
import sys, os, importlib.util, json as _json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats as _scipy_stats
from backend.routers.database import router as database_router

# ─────────────────────────── PATHS ──────────────────────────────────────
MAS_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR  = os.path.join(MAS_DIR, "output")
HITL_DIR    = os.path.join(MAS_DIR, "hitl")
OUTPUT_HITL = os.path.join(HITL_DIR, "output_3mode")
for p in [MAS_DIR, HITL_DIR]:
    if p not in sys.path: sys.path.insert(0, p)

# ─────────────────────────── IMPORT HELPER ──────────────────────────────
def _imp(name, base, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(base, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

# ─────────────────────────── MODULES ────────────────────────────────────
if HITL_DIR not in sys.path:
    sys.path.insert(0, HITL_DIR)

_adb = _imp("agent_database",     HITL_DIR, "agent_database.py")
_trig= _imp("disruption_triggers",HITL_DIR, "disruption_triggers.py")
_rb  = _imp("reactive_baseline",  HITL_DIR, "reactive_baseline.py")
_sl  = _imp("scenario_loader",    HITL_DIR, "scenario_loader.py")

AGENT_DATABASE        = _adb.AGENT_DATABASE
init_node_state       = _adb.init_node_state
run_reactive_scenario = _rb.run_reactive_scenario
CSVDataLoaderHITL     = _rb.CSVDataLoader
load_scenarios_hitl   = _sl.load_scenarios
get_scenario_hitl     = _sl.get_scenario

os.makedirs(OUTPUT_DIR,  exist_ok=True)
os.makedirs(OUTPUT_HITL, exist_ok=True)

_SCENARIOS_JSON = os.path.join(HITL_DIR, "scenarios_100.json")
_sl.reset_cache()
HITL_SCENARIOS = load_scenarios_hitl(json_path=_SCENARIOS_JSON, fallback=True)

def _csv_loader():
    return CSVDataLoaderHITL(data_dir=HITL_DIR)

# ─────────────────────────── CSV HELPERS ────────────────────────────────
def _read_csv_safe(filepath: str) -> pd.DataFrame:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline()
    sep = ";" if header.count(";") > header.count(",") else ","
    return pd.read_csv(filepath, sep=sep)

def upsert_csv(filepath: str, new_df: pd.DataFrame, dedup_keys: list):
    if not os.path.exists(filepath):
        new_df.to_csv(filepath, index=False)
        return
    try:
        existing = _read_csv_safe(filepath)
    except Exception:
        new_df.to_csv(filepath, index=False)
        return
    keys_present = [k for k in dedup_keys if k in existing.columns and k in new_df.columns]
    if keys_present:
        new_keys = new_df[keys_present].drop_duplicates()
        existing["_keep"] = True
        for _, key_row in new_keys.iterrows():
            mask = pd.Series([True] * len(existing))
            for k in keys_present:
                mask = mask & (existing[k] == key_row[k])
            existing.loc[mask, "_keep"] = False
        existing = existing[existing["_keep"]].drop(columns=["_keep"])
    combined = pd.concat([existing, new_df], ignore_index=True)
    if keys_present:
        sort_keys = [k for k in keys_present if k in combined.columns]
        if sort_keys:
            combined = combined.sort_values(sort_keys, ignore_index=True)
    combined.to_csv(filepath, index=False)

def rebuild_combined_csvs(output_dir: str):
    all_m, all_s = [], []
    for entry in sorted(os.listdir(output_dir)):
        d = os.path.join(output_dir, entry)
        if not (os.path.isdir(d) and entry.startswith("scenario_")):
            continue
        for fname, target in [("metrics.csv", all_m), ("stock_log.csv", all_s)]:
            p = os.path.join(d, fname)
            if os.path.exists(p):
                try: target.append(_read_csv_safe(p))
                except Exception: pass
    if all_m:
        cm = pd.concat(all_m, ignore_index=True)
        if "scenario_id" in cm.columns and "mode" in cm.columns:
            cm = cm.drop_duplicates(subset=["scenario_id","mode"], keep="last")
            cm = cm.sort_values(["scenario_id","mode"], ignore_index=True)
        cm.to_csv(os.path.join(output_dir, "scenario_metrics_3mode.csv"), index=False)
    if all_s:
        pd.concat(all_s, ignore_index=True).to_csv(
            os.path.join(output_dir, "stock_log_all.csv"), index=False)

def summary_statistics_hitl(metrics_list: list) -> pd.DataFrame:
    cols = ["Stock Availability Rate (%)","Time to Recovery (hours)",
            "Stockout Duration (hours)","Stockout Frequency",
            "Min Stock During Disruption","Recovery Speed Index"]
    df   = pd.DataFrame(metrics_list)
    rows = []
    for col in cols:
        if col not in df.columns: continue
        data = df[col].dropna()
        if len(data) < 2: continue
        n, mean, sd = len(data), data.mean(), data.std()
        ci = _scipy_stats.t.interval(0.95, df=n-1, loc=mean, scale=_scipy_stats.sem(data))
        rows.append({"Metric": col, "N": n, "Mean": round(mean,3), "Std": round(sd,3),
                     "Min": round(data.min(),3), "Max": round(data.max(),3),
                     "CI_95_Lo": round(ci[0],3), "CI_95_Hi": round(ci[1],3)})
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()

def save_scenario_outputs(sid: int, modes: list, results_this: dict,
                           stock_this: list, events_this: list,
                           hitl_this: list, output_dir: str):
    scen_dir = os.path.join(output_dir, f"scenario_{sid:03d}")
    os.makedirs(scen_dir, exist_ok=True)
    rows = [results_this[m] for m in modes if results_this.get(m)]
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
    if stock_this:
        pd.concat(stock_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "stock_log.csv"), index=False)
    if events_this:
        pd.concat(events_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "event_log.csv"), index=False)
    if hitl_this:
        pd.concat(hitl_this, ignore_index=True).to_csv(
            os.path.join(scen_dir, "hitl_decision_log.csv"), index=False)

# ─────────────────────────── APP SETUP ──────────────────────────────────
app = FastAPI(
    title="MAS Poultry Supply Chain API",
    description="Backend MAS simulasi ketahanan rantai pasok unggas — Reactive Mode",
    version="2.0.0", docs_url="/docs", redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(database_router)

# ─────────────────────────── PYDANTIC MODELS ────────────────────────────
class RunSimulationRequest(BaseModel):
    scenario_id: int  = Field(..., ge=1, le=5)
    verbose:     bool = Field(False)

class RunAllScenariosRequest(BaseModel):
    verbose: bool = Field(False)

class CheckDisruptionRequest(BaseModel):
    node_type: str            = Field(..., example="supplier")
    db_state:  Dict[str, Any] = Field(...)

class ManualDisruptionRequest(BaseModel):
    node_overrides:   Dict[str, Dict[str, Any]] = Field(default={})
    disruption_hours: List[Dict[str, Any]]      = Field(default=[])
    duration_hours:   int = Field(48)
    start_datetime:   str = Field("2026-06-01 06:00")

class RunHITLRequest(BaseModel):
    scenario_id:       int  = Field(..., ge=1, le=100, description="ID skenario (1-100)")
    mode:              str  = Field("reactive", description="reactive (only mode available)")
    verbose:           bool = Field(False)
    rng_seed:          int  = Field(42)
    use_custom_rules:  bool = Field(False, description="True = pakai custom_rules.json; False = default")

class RunAllHITLRequest(BaseModel):
    mode:             str             = Field("reactive", description="reactive (only mode available)")
    verbose:          bool            = Field(False)
    rng_seed:         int             = Field(42)
    scenario_ids:     Optional[List[int]] = Field(None, description="None = semua 100 skenario")
    use_custom_rules: bool            = Field(False, description="True = pakai custom_rules.json; False = default")

# ── Pydantic models for reactive rules ──────────────────────────────
# ── Pydantic models for reactive rules ──────────────────────────────
# Semua field Optional — user bebas kirim 1, beberapa, atau semua sekaligus.
# Field yang tidak dikirim tidak berubah (merge dengan state sebelumnya).

class TierReorderPolicy(BaseModel):
    threshold_ratio:   Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Reorder ketika stok < threshold_ratio × kapasitas")
    reorder_qty_ratio: Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Jumlah reorder = reorder_qty_ratio × kapasitas")

class RestockInterval(BaseModel):
    wholesaler: Optional[int] = Field(None, ge=1, le=200,
        description="Interval restock Wholesaler dalam ticks (1 tick = 15 menit)")
    retail:     Optional[int] = Field(None, ge=1, le=200,
        description="Interval restock Retail dalam ticks")

class ReactiveRulesPayload(BaseModel):
    reorder_policy:          Optional[Dict[str, TierReorderPolicy]] = Field(
        None, description="Kirim hanya tier yang ingin diubah; tier/field lain tidak berubah")
    restock_interval:        Optional[RestockInterval] = Field(None)
    fixed_disruption_factor: Optional[float] = Field(None, ge=0.0, le=1.0,
        description="Proporsi supply yang masih mengalir saat gangguan (0–1)")

# ─────────────────────────── JSON-SAFE HELPERS ──────────────────────────
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

def _df_records(df: pd.DataFrame) -> List[Dict]:
    return [_safe(row) for row in df.to_dict(orient="records")]

def _make_response(data) -> Response:
    def _default(obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.bool_): return bool(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.floating):
            return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
        raise TypeError(f"Not serializable: {type(obj)}")
    return Response(content=_json.dumps(_safe(data), default=_default, allow_nan=False),
                    media_type="application/json")

def _metrics_clean(m: dict) -> dict:
    return _safe({k: v for k, v in m.items() if k != "Rules Triggered"})

def _check_csv(filename: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"'{filename}' belum ada. Jalankan simulasi dulu.")
    return path

def _check_hitl_csv(filename: str) -> str:
    path = os.path.join(OUTPUT_HITL, filename)
    if not os.path.exists(path):
        raise HTTPException(404, f"'{filename}' belum ada di output_3mode/. "
            "Jalankan POST /hitl/simulate/scenario dulu.")
    return path

# ═══════════════════════════════════════════════════════════════════
# INFO
# ═══════════════════════════════════════════════════════════════════
@app.get("/", tags=["Info"])
def root():
    return {"service": "MAS Poultry Supply Chain API", "version": "2.0.0",
            "status": "running", "docs": "/docs"}

# ═══════════════════════════════════════════════════════════════════
# AGENT DATABASE
# ═══════════════════════════════════════════════════════════════════
@app.get("/agents", tags=["Agent Database"])
def get_all_agents():
    return {nt: {"meta": s["meta"],
                 "variables": {k: {"default": v["default"], "unit": v["unit"],
                               "description": v["description"]}
                               for k, v in s["variables"].items()},
                 "thresholds": s["thresholds"]}
            for nt, s in AGENT_DATABASE.items()}

@app.get("/agents/{node_type}", tags=["Agent Database"])
def get_agent(node_type: str):
    if node_type not in AGENT_DATABASE:
        raise HTTPException(404, f"Node '{node_type}' tidak ditemukan.")
    s = AGENT_DATABASE[node_type]
    return {"node_type": node_type, "meta": s["meta"],
            "variables": s["variables"], "thresholds": s["thresholds"]}

@app.get("/agents/{node_type}/initial-state", tags=["Agent Database"])
def get_initial_state(node_type: str):
    if node_type not in AGENT_DATABASE:
        raise HTTPException(404, f"Node '{node_type}' tidak ditemukan.")
    return {"node_type": node_type, "state": init_node_state(node_type)}

# ═══════════════════════════════════════════════════════════════════
# DISRUPTION ENGINE
# ═══════════════════════════════════════════════════════════════════
@app.post("/check-disruption", tags=["Disruption Engine"])
def check_disruption_endpoint(req: CheckDisruptionRequest):
    if req.node_type not in AGENT_DATABASE:
        raise HTTPException(404, f"Node '{req.node_type}' tidak ditemukan.")
    result    = _trig.check_disruption(req.node_type, req.db_state)
    recovered = _trig.check_recovery(req.node_type, req.db_state)
    return {"node_type": req.node_type, "disrupted": result["disrupted"],
            "triggered_by": result["triggered_by"], "event_types": result["event_types"],
            "details": result["details"], "recovery_possible": recovered}

@app.post("/check-recovery", tags=["Disruption Engine"])
def check_recovery_endpoint(req: CheckDisruptionRequest):
    if req.node_type not in AGENT_DATABASE:
        raise HTTPException(404, f"Node '{req.node_type}' tidak ditemukan.")
    return {"node_type": req.node_type,
            "recovery_met": _trig.check_recovery(req.node_type, req.db_state)}

# ═══════════════════════════════════════════════════════════════════
# ORCHESTRATOR RULES — stubs (rules tidak dipakai di reactive mode)
# ═══════════════════════════════════════════════════════════════════
@app.get("/rules", tags=["Orchestrator Rules"])
def get_all_rules():
    return []

@app.get("/rules/{rule_id}", tags=["Orchestrator Rules"])
def get_rule(rule_id: str):
    raise HTTPException(404, f"Rule '{rule_id}' tidak tersedia di reactive mode.")

@app.get("/match-rule", tags=["Orchestrator Rules"])
def match_rule(supplier: int=Query(0), farm: int=Query(0),
               slaughterhouse: int=Query(0), wholesaler: int=Query(0), retail: int=Query(0)):
    raise HTTPException(404, "match-rule tidak tersedia di reactive mode.")

# ═══════════════════════════════════════════════════════════════════
# SCENARIOS (v1 — stubs, tidak ada di reactive-only)
# ═══════════════════════════════════════════════════════════════════
@app.get("/scenarios", tags=["Scenarios"])
def get_all_scenarios():
    return []

@app.get("/scenarios/{scenario_id}", tags=["Scenarios"])
def get_scenario_v1(scenario_id: int):
    raise HTTPException(404, f"Skenario v1 tidak tersedia. Gunakan /hitl/scenarios.")

@app.get("/scenarios/{scenario_id}/events", tags=["Scenarios"])
def get_scenario_events_v1(scenario_id: int):
    raise HTTPException(404, f"Skenario v1 tidak tersedia. Gunakan /hitl/scenarios.")

# ═══════════════════════════════════════════════════════════════════
# SIMULATION v1 — stubs
# ═══════════════════════════════════════════════════════════════════
@app.post("/simulate/scenario", tags=["Simulation"])
def simulate_scenario(req: RunSimulationRequest):
    raise HTTPException(400, "Endpoint v1 tidak tersedia. Gunakan POST /hitl/simulate/scenario dengan mode=reactive.")

@app.post("/simulate/all", tags=["Simulation"])
def simulate_all_scenarios(req: RunAllScenariosRequest):
    raise HTTPException(400, "Endpoint v1 tidak tersedia. Gunakan POST /hitl/simulate/batch dengan mode=reactive.")

@app.post("/simulate/custom", tags=["Simulation"])
def simulate_custom(req: ManualDisruptionRequest):
    raise HTTPException(400, "Simulasi custom tidak tersedia di reactive mode.")

# ═══════════════════════════════════════════════════════════════════
# CSV DOWNLOAD (v1 output/)
# ═══════════════════════════════════════════════════════════════════
@app.get("/csv/list", tags=["CSV Files"])
def list_csv_files():
    if not os.path.exists(OUTPUT_DIR):
        return {"combined_files": [], "scenario_dirs": {}}
    root_files = [f for f in os.listdir(OUTPUT_DIR)
                  if f.endswith(".csv") and os.path.isfile(os.path.join(OUTPUT_DIR, f))]
    scen_dirs  = {}
    for entry in sorted(os.listdir(OUTPUT_DIR)):
        d = os.path.join(OUTPUT_DIR, entry)
        if os.path.isdir(d) and entry.startswith("scenario_"):
            csvs = [f for f in os.listdir(d) if f.endswith(".csv")]
            if csvs: scen_dirs[entry] = csvs
    return {"output_dir": OUTPUT_DIR, "combined_files": root_files, "scenario_dirs": scen_dirs}

@app.get("/csv/download/{filename}", tags=["CSV Files"])
def download_combined_csv(filename: str):
    if "/" in filename or ".." in filename: raise HTTPException(400, "Nama file tidak valid.")
    if not filename.endswith(".csv"):       raise HTTPException(400, "Hanya .csv.")
    return FileResponse(_check_csv(filename), filename=filename, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.get("/csv/scenario/{scenario_id}/{filename}", tags=["CSV Files"])
def download_scenario_csv(scenario_id: int, filename: str):
    if ".." in filename or "/" in filename: raise HTTPException(400, "Nama file tidak valid.")
    d = os.path.join(OUTPUT_DIR, f"scenario_{scenario_id:02d}")
    if not os.path.isdir(d): raise HTTPException(404, f"Skenario {scenario_id} belum dijalankan.")
    path = os.path.join(d, filename)
    if not os.path.exists(path): raise HTTPException(404, f"File '{filename}' tidak ditemukan.")
    dl = f"scenario{scenario_id}_{filename}"
    return FileResponse(path, filename=dl, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{dl}"'})

@app.get("/csv/scenario/{scenario_id}/json/{datatype}", tags=["CSV Files"])
def get_scenario_csv_as_json(scenario_id: int, datatype: str):
    allowed = {"stock_log": "stock_log.csv", "event_log": "event_log.csv", "metrics": "metrics.csv"}
    if datatype not in allowed: raise HTTPException(400, f"datatype: {list(allowed)}")
    d = os.path.join(OUTPUT_DIR, f"scenario_{scenario_id:02d}")
    if not os.path.isdir(d): raise HTTPException(404, f"Skenario {scenario_id} belum dijalankan.")
    path = os.path.join(d, allowed[datatype])
    if not os.path.exists(path): raise HTTPException(404, f"Data '{datatype}' belum tersedia.")
    df = pd.read_csv(path)
    return _make_response({"scenario_id": scenario_id, "datatype": datatype,
                           "rows": len(df), "data": _df_records(df)})

# ═══════════════════════════════════════════════════════════════════
# RESULTS v1 — stubs
# ═══════════════════════════════════════════════════════════════════
@app.get("/results/metrics", tags=["Results"])
def get_saved_metrics():
    raise HTTPException(404, "Gunakan GET /hitl/results/metrics?mode=reactive")

@app.get("/results/stock-log", tags=["Results"])
def get_stock_log(scenario_id: Optional[int]=None, node_type: Optional[str]=None,
                  limit: int=Query(500, ge=1, le=50000)):
    raise HTTPException(404, "Gunakan GET /hitl/results/stock-log?mode=reactive")

@app.get("/results/event-log", tags=["Results"])
def get_event_log(scenario_id: Optional[int]=None, rule_id: Optional[str]=None,
                  urgency: Optional[str]=None):
    raise HTTPException(404, "Reactive mode tidak menghasilkan event log koordinator.")

@app.get("/results/summary", tags=["Results"])
def get_summary_statistics():
    raise HTTPException(404, "Gunakan GET /hitl/results/summary?mode=reactive")

@app.get("/results/rule-frequency", tags=["Results"])
def get_rule_frequency(scenario_id: Optional[int]=None):
    raise HTTPException(404, "Reactive mode tidak menggunakan orchestrator rules.")

@app.get("/results/decision-distribution", tags=["Results"])
def get_decision_distribution(scenario_id: Optional[int]=None):
    raise HTTPException(404, "Reactive mode tidak menggunakan orchestrator rules.")

@app.get("/results/disruptions-per-scenario", tags=["Results"])
def get_disruptions_per_scenario():
    result = []
    for sid in range(1, 101):
        path = os.path.join(OUTPUT_HITL, f"scenario_{sid:03d}", "stock_log.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                df_r = df[df["mode"]=="reactive"] if "mode" in df.columns else df
                cnt = int(len(df_r[df_r["disrupted"] == 1])) if "disrupted" in df_r.columns else 0
                result.append({"scenario_id": sid, "disrupted_count": cnt})
            except Exception as e:
                result.append({"scenario_id": sid, "disrupted_count": 0, "error": str(e)})
        else:
            result.append({"scenario_id": sid, "disrupted_count": 0})
    return _make_response({"scenarios": result})

# ═══════════════════════════════════════════════════════════════════
# HITL — HELPER
# ═══════════════════════════════════════════════════════════════════
def _run_one_mode(scenario: dict, mode: str, seed: int, csv_ldr, verbose: bool,
                  use_custom_rules: bool = False) -> dict:
    """Jalankan satu skenario reactive, simpan ke subfolder, return dict hasil."""
    import traceback as _tb
    sid = scenario["scenario_id"]
    results_this, stock_dfs, event_dfs, hitl_dfs = {}, [], [], []

    if mode != "reactive":
        raise HTTPException(400, f"Mode '{mode}' tidak tersedia. Hanya 'reactive' yang didukung.")

    try:
        rm, rs = run_reactive_scenario(scenario, csv_loader=csv_ldr,
                                        verbose=verbose, rng_seed=seed + sid,
                                        use_custom_rules=use_custom_rules)
        rm["mode"] = "reactive"
        rs = rs.copy(); rs["scenario_id"] = sid; rs["mode"] = "reactive"
        results_this["reactive"] = rm; stock_dfs.append(rs)
    except Exception as exc:
        raise HTTPException(500, f"S{sid:03d} mode=reactive: {str(exc)}\n{_tb.format_exc()}")

    save_scenario_outputs(sid=sid, modes=["reactive"], results_this=results_this,
        stock_this=stock_dfs, events_this=event_dfs, hitl_this=hitl_dfs,
        output_dir=OUTPUT_HITL)

    metrics_df = pd.DataFrame(list(results_this.values()))
    upsert_csv(os.path.join(OUTPUT_HITL, "scenario_metrics_3mode.csv"),
               metrics_df, ["scenario_id", "mode"])

    mv = results_this["reactive"]
    sd = stock_dfs[0] if stock_dfs else pd.DataFrame()
    return {"mode": "reactive", "metrics": _metrics_clean(mv),
            "stock_log": _df_records(sd), "event_log": [], "hitl_log": [],
            "saved_dir": os.path.join(OUTPUT_HITL, f"scenario_{sid:03d}")}

# ═══════════════════════════════════════════════════════════════════
# HITL — SCENARIOS (100 skenario dari hitl/scenarios_100.json)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/scenarios", tags=["HITL"])
def hitl_get_all_scenarios(
    severity:       Optional[str] = Query(None, description="low|medium|high|crisis"),
    disruption_type:Optional[str] = Query(None),
    page:     int = Query(1,  ge=1),
    page_size:int = Query(20, ge=1, le=100),
):
    """Daftar 100 skenario. Filter: severity, disruption_type. Paginasi: page/page_size."""
    sc = HITL_SCENARIOS
    if severity:        sc = [s for s in sc if s.get("severity")        == severity]
    if disruption_type: sc = [s for s in sc if s.get("disruption_type") == disruption_type]
    total = len(sc)
    paged = sc[(page-1)*page_size: page*page_size]
    return _make_response({"total": total, "page": page, "page_size": page_size,
        "scenarios": [{"scenario_id": s["scenario_id"],
            "disruption_type": s["disruption_type"], "subtype": s.get("subtype",""),
            "severity": s["severity"], "seed_node": s["seed_node"],
            "cascade_depth": s.get("cascade_depth", len(s.get("cascade_path",[]))),
            "description": s["description"], "duration_hours": s["duration_hours"],
            "cascade_path": s.get("cascade_path",[]), "recovery_path": s.get("recovery_path",[]),
            "start_datetime": s["start_datetime"], "n_events": len(s.get("events",[]))}
        for s in paged]})

@app.get("/hitl/scenarios/meta/severity-distribution", tags=["HITL"])
def hitl_severity_distribution():
    from collections import Counter
    return _make_response(dict(Counter(s.get("severity","?") for s in HITL_SCENARIOS)))

@app.get("/hitl/scenarios/meta/type-distribution", tags=["HITL"])
def hitl_type_distribution():
    from collections import Counter
    return _make_response(dict(Counter(s.get("disruption_type","?") for s in HITL_SCENARIOS)))

@app.get("/hitl/scenarios/{scenario_id}", tags=["HITL"])
def hitl_get_scenario(scenario_id: int):
    """Detail lengkap satu skenario beserta semua event-nya."""
    s = get_scenario_hitl(scenario_id, json_path=_SCENARIOS_JSON)
    if s is None: raise HTTPException(404, f"Skenario {scenario_id} tidak ditemukan.")
    return s

@app.get("/hitl/scenarios/{scenario_id}/events", tags=["HITL"])
def hitl_get_scenario_events(scenario_id: int):
    """Disruption schedule (events) dari satu skenario."""
    s = get_scenario_hitl(scenario_id, json_path=_SCENARIOS_JSON)
    if s is None: raise HTTPException(404, f"Skenario {scenario_id} tidak ditemukan.")
    return {"scenario_id": scenario_id, "events": s.get("events", [])}

# ═══════════════════════════════════════════════════════════════════
# HITL — MANAGER PROFILES (stub)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/manager-profiles", tags=["HITL"])
def hitl_get_manager_profiles():
    return {}

@app.get("/hitl/manager-profiles/{tier}", tags=["HITL"])
def hitl_get_manager_profile(tier: str):
    raise HTTPException(404, "Manager profiles tidak tersedia di reactive mode.")

# ═══════════════════════════════════════════════════════════════════
# HITL — SIMULATION
# ═══════════════════════════════════════════════════════════════════
@app.post("/hitl/simulate/scenario", tags=["HITL"])
def hitl_simulate_scenario(req: RunHITLRequest):
    """
    Jalankan satu skenario. Hanya mode `reactive` yang tersedia.
    Output → `hitl/output_3mode/scenario_{id:03d}/`
    """
    if req.mode not in ("reactive",):
        raise HTTPException(400, f"Mode '{req.mode}' tidak tersedia. Hanya 'reactive' yang didukung.")
    s = get_scenario_hitl(req.scenario_id, json_path=_SCENARIOS_JSON)
    if s is None: raise HTTPException(404, f"Skenario {req.scenario_id} tidak ditemukan.")
    ldr    = _csv_loader()
    result = _run_one_mode(s, "reactive", req.rng_seed, ldr, req.verbose,
                           use_custom_rules=req.use_custom_rules)
    rebuild_combined_csvs(OUTPUT_HITL)
    return _make_response({"scenario_id": req.scenario_id, "mode": "reactive",
                           "results": [result], "comparison": None})

@app.post("/hitl/simulate/batch", tags=["HITL"])
def hitl_simulate_batch(req: RunAllHITLRequest):
    """
    Jalankan batch skenario reactive. `scenario_ids=null` artinya semua 100.
    """
    if req.mode not in ("reactive",):
        raise HTTPException(400, f"Mode '{req.mode}' tidak tersedia. Hanya 'reactive' yang didukung.")
    if req.scenario_ids:
        target = [s for s in HITL_SCENARIOS if s["scenario_id"] in req.scenario_ids]
        if not target: raise HTTPException(404, "Tidak ada skenario yang cocok.")
    else:
        target = HITL_SCENARIOS
    ldr = _csv_loader()
    out = []
    for scenario in target:
        r = _run_one_mode(scenario, "reactive", req.rng_seed, ldr, req.verbose,
                          use_custom_rules=req.use_custom_rules)
        out.append({"scenario_id": scenario["scenario_id"],
                    "modes": [{"mode": "reactive", "metrics": r["metrics"],
                               "saved_dir": r["saved_dir"]}]})
    rebuild_combined_csvs(OUTPUT_HITL)
    return _make_response({"total_scenarios": len(out), "modes": ["reactive"], "results": out})

# ═══════════════════════════════════════════════════════════════════
# HITL — RESULTS (dari output_3mode/)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/results/metrics", tags=["HITL"])
def hitl_get_metrics(mode: Optional[str]=Query(None, description="reactive"),
                     severity: Optional[str]=Query(None),
                     scenario_id: Optional[int]=Query(None)):
    """Metrics dari scenario_metrics_3mode.csv. Filter: mode, severity, scenario_id."""
    df = pd.read_csv(_check_hitl_csv("scenario_metrics_3mode.csv"))
    if mode:                    df = df[df["mode"]        == mode]
    if severity:                df = df[df["severity"]    == severity]
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    return _make_response(_df_records(df))

@app.get("/hitl/results/comparison", tags=["HITL"])
def hitl_get_comparison():
    raise HTTPException(404, "Comparison tidak tersedia — hanya mode reactive yang berjalan.")

@app.get("/hitl/results/summary", tags=["HITL"])
def hitl_get_summary(mode: str=Query(..., description="reactive")):
    """Statistik (mean, std, CI 95%) dari summary_{mode}.csv."""
    if mode != "reactive":
        raise HTTPException(400, "Hanya mode 'reactive' yang tersedia.")
    path = os.path.join(OUTPUT_HITL, "summary_reactive.csv")
    if not os.path.exists(path):
        # Hitung dari metrics yang ada
        metrics_path = os.path.join(OUTPUT_HITL, "scenario_metrics_3mode.csv")
        if not os.path.exists(metrics_path):
            raise HTTPException(404, "Belum ada data. Jalankan simulasi dulu.")
        df = pd.read_csv(metrics_path)
        df = df[df["mode"] == "reactive"]
        s  = summary_statistics_hitl(df.to_dict("records"))
        s.to_csv(path)
    df = pd.read_csv(path, index_col=0)
    return _make_response(_df_records(df.reset_index()))

@app.get("/hitl/results/hitl-log", tags=["HITL"])
def hitl_get_decision_log(
    scenario_id: Optional[int]=Query(None),
    tier:        Optional[str]=Query(None),
    decision:    Optional[str]=Query(None),
    limit:       int=Query(500, ge=1, le=50000)):
    """Reactive mode tidak menghasilkan HITL decision log."""
    return _make_response([])

@app.get("/hitl/results/hitl-log/stats", tags=["HITL"])
def hitl_decision_stats(scenario_id: Optional[int]=Query(None)):
    return _make_response({"info": "Reactive mode tidak menghasilkan HITL decision log."})

@app.get("/hitl/results/stock-log", tags=["HITL"])
def hitl_get_stock_log(scenario_id: Optional[int]=Query(None),
                       mode: Optional[str]=Query(None, description="reactive"),
                       node_type: Optional[str]=Query(None),
                       limit: int=Query(500, ge=1, le=50000)):
    """Stock log dari stock_log_all.csv."""
    df = pd.read_csv(_check_hitl_csv("stock_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if mode:                    df = df[df["mode"]        == mode]
    if node_type:               df = df[df["node_type"]   == node_type]
    return _make_response(_df_records(df.head(limit)))

@app.get("/hitl/results/event-log", tags=["HITL"])
def hitl_get_event_log(scenario_id: Optional[int]=Query(None),
                       mode: Optional[str]=Query(None),
                       rule_id: Optional[str]=Query(None),
                       limit: int=Query(500, ge=1, le=50000)):
    """Reactive mode tidak menghasilkan coordinator event log."""
    return _make_response([])

@app.get("/hitl/results/sar-by-severity", tags=["HITL"])
def hitl_sar_by_severity():
    """SAR rata-rata per severity untuk mode reactive."""
    df  = pd.read_csv(_check_hitl_csv("scenario_metrics_3mode.csv"))
    df  = df[df["mode"] == "reactive"]
    col = "Stock Availability Rate (%)"
    rows= []
    for sev in ["low","medium","high","crisis"]:
        sub = df[df["severity"]==sev][col].dropna()
        if len(sub) > 0:
            rows.append({"severity": sev, "mode": "reactive", "n": len(sub),
                         "mean_SAR": round(float(sub.mean()),3),
                         "std_SAR":  round(float(sub.std()), 3)})
    return _make_response(rows)

@app.post("/hitl/results/rebuild", tags=["HITL"])
def hitl_rebuild_combined():
    """Rebuild file gabungan dari subfolder."""
    rebuild_combined_csvs(OUTPUT_HITL)
    files = [f for f in os.listdir(OUTPUT_HITL)
             if f.endswith(".csv") and os.path.isfile(os.path.join(OUTPUT_HITL, f))]
    return _make_response({"status": "rebuilt", "files": sorted(files)})

# ═══════════════════════════════════════════════════════════════════
# HITL — CSV FILES (download & browse output_3mode/)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/csv/list", tags=["HITL"])
def hitl_list_csv():
    if not os.path.exists(OUTPUT_HITL):
        return {"output_dir": OUTPUT_HITL, "combined_files": [], "scenario_dirs": {}}
    root_files = [f for f in os.listdir(OUTPUT_HITL)
                  if f.endswith(".csv") and os.path.isfile(os.path.join(OUTPUT_HITL, f))]
    scen_dirs  = {}
    for entry in sorted(os.listdir(OUTPUT_HITL)):
        d = os.path.join(OUTPUT_HITL, entry)
        if os.path.isdir(d) and entry.startswith("scenario_"):
            csvs = [f for f in os.listdir(d) if f.endswith(".csv")]
            if csvs: scen_dirs[entry] = csvs
    return {"output_dir": OUTPUT_HITL, "combined_files": root_files, "scenario_dirs": scen_dirs}

@app.get("/hitl/csv/download/{filename}", tags=["HITL"])
def hitl_download_csv(filename: str):
    if "/" in filename or ".." in filename: raise HTTPException(400, "Nama file tidak valid.")
    if not filename.endswith(".csv"):       raise HTTPException(400, "Hanya .csv.")
    return FileResponse(_check_hitl_csv(filename), filename=filename, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.get("/hitl/csv/scenario/{scenario_id}/{filename}", tags=["HITL"])
def hitl_download_scenario_csv(scenario_id: int, filename: str):
    if ".." in filename or "/" in filename: raise HTTPException(400, "Nama file tidak valid.")
    d = os.path.join(OUTPUT_HITL, f"scenario_{scenario_id:03d}")
    if not os.path.isdir(d): raise HTTPException(404, f"Skenario {scenario_id} belum dijalankan.")
    path = os.path.join(d, filename)
    if not os.path.exists(path): raise HTTPException(404, f"File '{filename}' tidak ditemukan.")
    dl = f"s{scenario_id:03d}_{filename}"
    return FileResponse(path, filename=dl, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{dl}"'})

@app.get("/hitl/csv/scenario/{scenario_id}/json/{datatype}", tags=["HITL"])
def hitl_get_scenario_json(scenario_id: int, datatype: str):
    allowed = {"metrics": "metrics.csv", "stock_log": "stock_log.csv",
               "event_log": "event_log.csv", "hitl_decision_log": "hitl_decision_log.csv"}
    if datatype not in allowed:
        raise HTTPException(400, f"datatype harus: {list(allowed.keys())}")
    d = os.path.join(OUTPUT_HITL, f"scenario_{scenario_id:03d}")
    if not os.path.isdir(d): raise HTTPException(404, f"Skenario {scenario_id} belum dijalankan.")
    path = os.path.join(d, allowed[datatype])
    if not os.path.exists(path): raise HTTPException(404, f"Data '{datatype}' tidak tersedia.")
    df = pd.read_csv(path)
    return _make_response({"scenario_id": scenario_id, "datatype": datatype,
                           "rows": len(df), "data": _df_records(df)})


# ═══════════════════════════════════════════════════════════════════
# REACTIVE RULES — GET default / GET custom / PUT custom / DELETE custom
# ═══════════════════════════════════════════════════════════════════

_DEFAULT_RULES_PATH = os.path.join(HITL_DIR, "default_rules.json")
_CUSTOM_RULES_PATH  = os.path.join(HITL_DIR, "custom_rules.json")

VALID_TIERS = {"supplier", "farm", "slaughterhouse", "wholesaler", "retail"}


def _read_rules_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)


def _extract_rules_for_api(raw: dict) -> dict:
    """Return only numeric fields (strip _comment/_note keys)."""
    reorder = {}
    for tier in ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"]:
        entry = raw.get("reorder_policy", {}).get(tier, {})
        reorder[tier] = {
            "threshold_ratio"  : float(entry.get("threshold_ratio",   0.40)),
            "reorder_qty_ratio": float(entry.get("reorder_qty_ratio", 0.30)),
        }
    interval_raw = raw.get("restock_interval", {})
    return {
        "reorder_policy": reorder,
        "restock_interval": {
            "wholesaler": int(interval_raw.get("wholesaler", 8)),
            "retail"    : int(interval_raw.get("retail",     4)),
        },
        "fixed_disruption_factor": float(raw.get("fixed_disruption_factor", 0.35)),
    }


@app.get("/hitl/rules/default", tags=["Reactive Rules"])
def get_default_rules():
    """
    Kembalikan rule bawaan (default_rules.json) — read-only, tidak bisa diubah.
    Nilai ini selalu digunakan ketika `use_custom_rules=false` saat simulasi.
    """
    if not os.path.exists(_DEFAULT_RULES_PATH):
        raise HTTPException(500, "default_rules.json tidak ditemukan di server.")
    raw = _read_rules_json(_DEFAULT_RULES_PATH)
    return _make_response({
        "source"    : "default",
        "read_only" : True,
        "rules"     : _extract_rules_for_api(raw),
    })


@app.get("/hitl/rules/custom", tags=["Reactive Rules"])
def get_custom_rules():
    """
    Kembalikan rule custom aktif.
    - Jika custom_rules.json belum ada, kembalikan rule default sebagai base.
    - Field `is_custom` menunjukkan apakah user sudah menyimpan custom rules.
    """
    if not os.path.exists(_CUSTOM_RULES_PATH):
        # Belum ada custom → kembalikan defaults sebagai starting point
        raw = _read_rules_json(_DEFAULT_RULES_PATH)
        return _make_response({
            "source"   : "default_fallback",
            "is_custom": False,
            "rules"    : _extract_rules_for_api(raw),
        })
    raw = _read_rules_json(_CUSTOM_RULES_PATH)
    return _make_response({
        "source"   : "custom",
        "is_custom": True,
        "rules"    : _extract_rules_for_api(raw),
    })


@app.post("/hitl/rules/custom", tags=["Reactive Rules"])
def save_custom_rules(payload: ReactiveRulesPayload):
    """
    Simpan / update custom rules — bebas kirim 1 field, beberapa, atau semua sekaligus.
    Field yang tidak dikirim tidak berubah; selalu merge dengan state sebelumnya
    (atau default jika custom belum pernah disimpan).

    **Contoh — ubah 1 field di 1 tier:**
    ```json
    { "reorder_policy": { "retail": { "threshold_ratio": 0.25 } } }
    ```

    **Contoh — ubah 2 tier sekaligus:**
    ```json
    {
      "reorder_policy": {
        "farm":     { "threshold_ratio": 0.60 },
        "supplier": { "reorder_qty_ratio": 0.40 }
      }
    }
    ```

    **Contoh — ubah interval + disruption factor saja:**
    ```json
    { "restock_interval": { "wholesaler": 10 }, "fixed_disruption_factor": 0.50 }
    ```

    **Contoh — update semua sekaligus:**
    ```json
    {
      "reorder_policy": {
        "supplier":       { "threshold_ratio": 0.40, "reorder_qty_ratio": 0.30 },
        "farm":           { "threshold_ratio": 0.55, "reorder_qty_ratio": 0.25 },
        "slaughterhouse": { "threshold_ratio": 0.45, "reorder_qty_ratio": 0.25 },
        "wholesaler":     { "threshold_ratio": 0.38, "reorder_qty_ratio": 0.30 },
        "retail":         { "threshold_ratio": 0.30, "reorder_qty_ratio": 0.35 }
      },
      "restock_interval": { "wholesaler": 8, "retail": 4 },
      "fixed_disruption_factor": 0.35
    }
    ```
    """
    # Validasi nama tier
    if payload.reorder_policy is not None:
        extra_tiers = set(payload.reorder_policy.keys()) - VALID_TIERS
        if extra_tiers:
            raise HTTPException(422, f"Tier tidak dikenal: {sorted(extra_tiers)}")

    # Baca state saat ini (custom jika ada, fallback ke default)
    if os.path.exists(_CUSTOM_RULES_PATH):
        current = _read_rules_json(_CUSTOM_RULES_PATH)
    else:
        current = _read_rules_json(_DEFAULT_RULES_PATH)
    current_rules = _extract_rules_for_api(current)

    # Merge reorder_policy — hanya tier & field yang dikirim
    if payload.reorder_policy is not None:
        for tier, pol in payload.reorder_policy.items():
            existing = current_rules["reorder_policy"].setdefault(tier, {
                "threshold_ratio": 0.40, "reorder_qty_ratio": 0.30
            })
            if pol.threshold_ratio is not None:
                existing["threshold_ratio"] = pol.threshold_ratio
            if pol.reorder_qty_ratio is not None:
                existing["reorder_qty_ratio"] = pol.reorder_qty_ratio

    # Merge restock_interval
    if payload.restock_interval is not None:
        if payload.restock_interval.wholesaler is not None:
            current_rules["restock_interval"]["wholesaler"] = payload.restock_interval.wholesaler
        if payload.restock_interval.retail is not None:
            current_rules["restock_interval"]["retail"] = payload.restock_interval.retail

    # Merge fixed_disruption_factor
    if payload.fixed_disruption_factor is not None:
        current_rules["fixed_disruption_factor"] = payload.fixed_disruption_factor

    # Simpan ke custom_rules.json
    to_save = {
        "_comment": "User-defined custom rules. Merges over default_rules.json at runtime.",
        "reorder_policy": {
            tier: {
                "threshold_ratio"  : pol["threshold_ratio"],
                "reorder_qty_ratio": pol["reorder_qty_ratio"],
            }
            for tier, pol in current_rules["reorder_policy"].items()
        },
        "restock_interval": current_rules["restock_interval"],
        "fixed_disruption_factor": current_rules["fixed_disruption_factor"],
    }

    try:
        with open(_CUSTOM_RULES_PATH, "w", encoding="utf-8") as f:
            _json.dump(to_save, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        raise HTTPException(500, f"Gagal menyimpan custom_rules.json: {exc}")

    return _make_response({
        "status" : "saved",
        "source" : "custom",
        "rules"  : current_rules,
    })


@app.delete("/hitl/rules/custom", tags=["Reactive Rules"])
def delete_custom_rules():
    """
    Hapus custom_rules.json — simulasi selanjutnya otomatis kembali ke rule default.
    """
    if not os.path.exists(_CUSTOM_RULES_PATH):
        return _make_response({"status": "not_found",
                               "message": "custom_rules.json tidak ada, tidak ada yang dihapus."})
    try:
        os.remove(_CUSTOM_RULES_PATH)
    except Exception as exc:
        raise HTTPException(500, f"Gagal menghapus custom_rules.json: {exc}")
    return _make_response({"status": "deleted",
                           "message": "custom_rules.json berhasil dihapus. "
                                      "Simulasi akan menggunakan rule default."})


@app.get("/hitl/rules/effective", tags=["Reactive Rules"])
def get_effective_rules(use_custom: bool = Query(False,
        description="True = tampilkan merged custom+default; False = tampilkan default saja")):
    """
    Tampilkan rules efektif yang akan dipakai saat simulasi.
    Berguna untuk preview sebelum menjalankan simulasi.
    """
    try:
        rules = _rb.load_rules(use_custom=use_custom)
    except Exception as exc:
        raise HTTPException(500, f"Gagal load rules: {exc}")
    return _make_response({
        "use_custom": use_custom,
        "source"    : "custom_merged" if use_custom and os.path.exists(_CUSTOM_RULES_PATH)
                      else "default",
        "rules"     : rules,
    })


@app.get("/dashboard/tiers", tags=["Dashboard"])
def dashboard_tiers(use_custom: bool = Query(False, description="True = pakai custom rules jika ada")):
    """
    Kembalikan daftar 5 tier (supplier, farm, slaughterhouse, wholesaler, retail)
    beserta `meta`, `variables`, nilai aturan (`reorder_policy`) dan penjelasan dari
    `default_rules.json`. Jika `use_custom=true` dan `custom_rules.json` ada, nilai
    numerik akan mencerminkan merge custom+default.
    """
    # Baca default notes
    try:
        default_raw = _read_rules_json(_DEFAULT_RULES_PATH)
    except Exception:
        default_raw = {}

    # Load effective numeric rules (merged when use_custom True)
    try:
        effective = _rb.load_rules(use_custom=use_custom)
    except Exception:
        # fallback ke extractor jika load_rules bermasalah
        effective = _extract_rules_for_api(default_raw)

    tiers = []
    for tier in ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"]:
        meta = AGENT_DATABASE.get(tier, {}).get("meta", {})
        vars_raw = AGENT_DATABASE.get(tier, {}).get("variables", {})
        variables = {k: {"default": v["default"], "unit": v["unit"], "description": v.get("description","")}
                     for k, v in vars_raw.items()}
        rule_vals = effective.get("reorder_policy", {}).get(tier, {})
        note = default_raw.get("reorder_policy", {}).get(tier, {}).get("_note", "")
        # Provide both legacy 'rules' and frontend-friendly 'rule' with 'explanation'
        tiers.append({
            "tier": tier,
            "meta": meta,
            "variables": variables,
            "rules": {**rule_vals, "note": note},
            "rule": {
                "threshold_ratio": rule_vals.get("threshold_ratio"),
                "reorder_qty_ratio": rule_vals.get("reorder_qty_ratio"),
                "explanation": note,
            }
        })

    restock_note = default_raw.get("restock_interval", {}).get("_note", "")
    restock_interval = {
        "wholesaler": effective.get("restock_interval", {}).get("wholesaler"),
        "retail":     effective.get("restock_interval", {}).get("retail"),
        "note": restock_note,
    }

    fixed_note = default_raw.get("_disruption_note", "")
    fixed_disruption = {
        "value": effective.get("fixed_disruption_factor", default_raw.get("fixed_disruption_factor")),
        "note": fixed_note,
    }

    source = "custom_merged" if use_custom and os.path.exists(_CUSTOM_RULES_PATH) else "default"
    return _make_response({"source": source, "total_tiers": len(tiers), "tiers": tiers,
                           "restock_interval": restock_interval,
                           "fixed_disruption_factor": fixed_disruption})
