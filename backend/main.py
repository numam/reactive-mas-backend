"""
FastAPI Backend — MAS Poultry Supply Chain Resilience v2.0
"""
import sys, os, importlib.util, json as _json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

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

# ─────────────────────────── V1 MODULES ─────────────────────────────────
_adb  = _imp("agent_database",       MAS_DIR, "01_agent_database.py")
_trig = _imp("disruption_triggers",  MAS_DIR, "02_disruption_triggers.py")
_orch = _imp("orchestrator_rules",   MAS_DIR, "03_orchestrator_rules.py")
_scen = _imp("disruption_scenarios", MAS_DIR, "04_disruption_scenarios.py")
_sim  = _imp("main_simulation",      MAS_DIR, "08_main_simulation.py")

AGENT_DATABASE        = _adb.AGENT_DATABASE
init_node_state       = _adb.init_node_state
ORCHESTRATOR_RULES    = _orch.ORCHESTRATOR_RULES
PATTERN_TO_RULE       = _orch.PATTERN_TO_RULE
DISRUPTION_SCENARIOS  = _scen.DISRUPTION_SCENARIOS
run_scenario_v1       = _sim.run_scenario
save_scenario_results = _sim.save_scenario_results
summary_statistics_v1 = _sim.summary_statistics
CHAIN_ORDER           = _sim.CHAIN_ORDER

# ─────────────────────────── HITL MODULES ───────────────────────────────
# Pastikan HITL_DIR ada di sys.path agar modul hitl/ bisa saling import
if HITL_DIR not in sys.path:
    sys.path.insert(0, HITL_DIR)

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

os.makedirs(OUTPUT_DIR,  exist_ok=True)
os.makedirs(OUTPUT_HITL, exist_ok=True)

_SCENARIOS_JSON = os.path.join(HITL_DIR, "scenarios_100.json")
_sl.reset_cache()
HITL_SCENARIOS = load_scenarios_hitl(json_path=_SCENARIOS_JSON, fallback=True)

def _csv_loader():
    return CSVDataLoaderHITL(data_dir=HITL_DIR)

def _read_csv_safe(filepath: str) -> pd.DataFrame:
    """
    Baca CSV dengan auto-detect separator (koma atau titik-koma).
    Mencegah ParserError jika file lama menggunakan sep=';'.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline()
    sep = ";" if header.count(";") > header.count(",") else ","
    return pd.read_csv(filepath, sep=sep)

def upsert_csv(filepath: str, new_df: pd.DataFrame, dedup_keys: list):
    """
    Update file CSV gabungan secara aman.
    - Jika file belum ada: simpan langsung.
    - Jika sudah ada: baca existing, hapus baris dengan key yang sama
      (scenario_id+mode combination), ganti dengan data baru, lalu simpan.
    Pendekatan ini aman untuk re-run dan tidak menyebabkan file membesar.
    """
    if not os.path.exists(filepath):
        new_df.to_csv(filepath, index=False)
        return

    try:
        existing = _read_csv_safe(filepath)
    except Exception:
        # File corrupt — buang dan tulis ulang
        new_df.to_csv(filepath, index=False)
        return
    keys_present = [k for k in dedup_keys if k in existing.columns and k in new_df.columns]

    if keys_present:
        # Bangun mask: hapus baris di existing yang key-nya ada di new_df
        new_keys = new_df[keys_present].drop_duplicates()
        # Merge untuk menandai baris yang akan dihapus
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
    """
    Rebuild semua file gabungan dari scratch berdasarkan subfolder.
    Dipanggil setelah batch run selesai untuk memastikan konsistensi.
    """
    all_m, all_s, all_e, all_h = [], [], [], []
    for entry in sorted(os.listdir(output_dir)):
        d = os.path.join(output_dir, entry)
        if not (os.path.isdir(d) and entry.startswith("scenario_")):
            continue
        for fname, target in [("metrics.csv", all_m), ("stock_log.csv", all_s),
                               ("event_log.csv", all_e)]:
            p = os.path.join(d, fname)
            if os.path.exists(p):
                try:
                    target.append(_read_csv_safe(p))
                except Exception:
                    pass
        hp = os.path.join(d, "hitl_decision_log.csv")
        if os.path.exists(hp):
            try:
                all_h.append(_read_csv_safe(hp))
            except Exception:
                pass

    if all_m:
        cm = pd.concat(all_m, ignore_index=True)
        if "scenario_id" in cm.columns and "mode" in cm.columns:
            cm = cm.drop_duplicates(subset=["scenario_id","mode"], keep="last")
            cm = cm.sort_values(["scenario_id","mode"], ignore_index=True)
        cm.to_csv(os.path.join(output_dir, "scenario_metrics_3mode.csv"), index=False)

    if all_s:
        pd.concat(all_s, ignore_index=True).to_csv(
            os.path.join(output_dir, "stock_log_all.csv"), index=False)
    if all_e:
        pd.concat(all_e, ignore_index=True).to_csv(
            os.path.join(output_dir, "event_log_all.csv"), index=False)
    if all_h:
        pd.concat(all_h, ignore_index=True).to_csv(
            os.path.join(output_dir, "hitl_decision_log.csv"), index=False)

# ─────────────────────────── APP SETUP ──────────────────────────────────
app = FastAPI(
    title="MAS Poultry Supply Chain API",
    description="Backend MAS + HITL simulasi ketahanan rantai pasok unggas",
    version="2.0.0", docs_url="/docs", redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

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
    scenario_id: int  = Field(..., ge=1, le=100, description="ID skenario (1-100)")
    mode:        str  = Field("all", description="reactive|autonomous|hitl|all")
    verbose:     bool = Field(False)
    rng_seed:    int  = Field(42)

class RunAllHITLRequest(BaseModel):
    mode:         str             = Field("all", description="reactive|autonomous|hitl|all")
    verbose:      bool            = Field(False)
    rng_seed:     int             = Field(42)
    scenario_ids: Optional[List[int]] = Field(None, description="None = semua 100 skenario")

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
# ORCHESTRATOR RULES
# ═══════════════════════════════════════════════════════════════════
@app.get("/rules", tags=["Orchestrator Rules"])
def get_all_rules():
    return [{"rule_id": rid, "pattern": list(rule["pattern"]),
             "decision": rule["decision"], "urgency": rule["urgency"],
             "justification": rule["justification"],
             "nodes_affected": [t for t, i in rule["instructions"].items() if i]}
            for rid, rule in ORCHESTRATOR_RULES.items()]

@app.get("/rules/{rule_id}", tags=["Orchestrator Rules"])
def get_rule(rule_id: str):
    if rule_id not in ORCHESTRATOR_RULES:
        raise HTTPException(404, f"Rule '{rule_id}' tidak ditemukan.")
    rule = ORCHESTRATOR_RULES[rule_id]
    return {"rule_id": rule_id, "pattern": list(rule["pattern"]),
            "decision": rule["decision"], "urgency": rule["urgency"],
            "justification": rule["justification"], "instructions": rule["instructions"]}

@app.get("/match-rule", tags=["Orchestrator Rules"])
def match_rule(supplier: int=Query(0), farm: int=Query(0),
               slaughterhouse: int=Query(0), wholesaler: int=Query(0), retail: int=Query(0)):
    pattern = (supplier, farm, slaughterhouse, wholesaler, retail)
    rule_id = PATTERN_TO_RULE.get(pattern, "R1")
    rule    = ORCHESTRATOR_RULES[rule_id]
    return {"pattern": pattern, "rule_id": rule_id, "decision": rule["decision"],
            "urgency": rule["urgency"], "justification": rule["justification"],
            "instructions": rule["instructions"]}

# ═══════════════════════════════════════════════════════════════════
# SCENARIOS (v1 — 5 skenario)
# ═══════════════════════════════════════════════════════════════════
@app.get("/scenarios", tags=["Scenarios"])
def get_all_scenarios():
    return [{"scenario_id": s["scenario_id"], "disruption_type": s["disruption_type"],
             "severity": s["severity"], "seed_node": s["seed_node"],
             "description": s["description"], "duration_hours": s["duration_hours"],
             "cascade_path": s["cascade_path"], "recovery_path": s["recovery_path"],
             "start_datetime": s["start_datetime"], "n_events": len(s["events"])}
            for s in DISRUPTION_SCENARIOS]

@app.get("/scenarios/{scenario_id}", tags=["Scenarios"])
def get_scenario(scenario_id: int):
    for s in DISRUPTION_SCENARIOS:
        if s["scenario_id"] == scenario_id: return s
    raise HTTPException(404, f"Skenario {scenario_id} tidak ditemukan.")

@app.get("/scenarios/{scenario_id}/events", tags=["Scenarios"])
def get_scenario_events(scenario_id: int):
    for s in DISRUPTION_SCENARIOS:
        if s["scenario_id"] == scenario_id:
            return {"scenario_id": scenario_id, "events": s["events"]}
    raise HTTPException(404, f"Skenario {scenario_id} tidak ditemukan.")

# ═══════════════════════════════════════════════════════════════════
# SIMULATION v1 (5 skenario, auto-save CSV)
# ═══════════════════════════════════════════════════════════════════
@app.post("/simulate/scenario", tags=["Simulation"])
def simulate_scenario(req: RunSimulationRequest):
    """Jalankan simulasi satu skenario v1. Hasil disimpan ke output/scenario_{id}/."""
    sc = [s for s in DISRUPTION_SCENARIOS if s["scenario_id"] == req.scenario_id]
    if not sc: raise HTTPException(404, f"Skenario {req.scenario_id} tidak ditemukan.")
    try:
        metrics, stock_df, event_df = run_scenario_v1(sc[0], verbose=req.verbose)
    except Exception as exc:
        import traceback
        raise HTTPException(500, f"Simulasi gagal: {str(exc)}\n{traceback.format_exc()}")
    saved = save_scenario_results(scenario_id=req.scenario_id, metrics=metrics,
                                   stock_df=stock_df, event_df=event_df, output_dir=OUTPUT_DIR)
    return _make_response({"scenario_id": req.scenario_id,
                           "metrics": _metrics_clean(metrics),
                           "rules_triggered": _safe(metrics.get("Rules Triggered", {})),
                           "stock_log": _df_records(stock_df),
                           "event_log": _df_records(event_df),
                           "saved_files": saved})

@app.post("/simulate/all", tags=["Simulation"])
def simulate_all_scenarios(req: RunAllScenariosRequest):
    """Jalankan semua 5 skenario v1."""
    all_results, all_metrics = [], []
    for scenario in DISRUPTION_SCENARIOS:
        try:
            metrics, stock_df, event_df = run_scenario_v1(scenario, verbose=req.verbose)
        except Exception as exc:
            import traceback
            raise HTTPException(500, f"Skenario {scenario['scenario_id']} gagal: {str(exc)}\n{traceback.format_exc()}")
        saved = save_scenario_results(scenario_id=scenario["scenario_id"], metrics=metrics,
                                       stock_df=stock_df, event_df=event_df, output_dir=OUTPUT_DIR)
        all_metrics.append(metrics)
        all_results.append({"scenario_id": scenario["scenario_id"],
                             "metrics": _metrics_clean(metrics),
                             "rules_triggered": _safe(metrics.get("Rules Triggered", {})),
                             "stock_log": _df_records(stock_df),
                             "event_log": _df_records(event_df),
                             "saved_files": saved})
    summary_df = summary_statistics_v1(all_metrics)
    return _make_response({"scenarios": all_results,
                           "summary": _df_records(summary_df.reset_index()) if not summary_df.empty else []})

@app.post("/simulate/custom", tags=["Simulation"])
def simulate_custom(req: ManualDisruptionRequest):
    """Simulasi kustom (what-if). Tidak disimpan ke CSV."""
    custom = {"scenario_id": 99, "disruption_type": "CUSTOM", "severity": "custom",
              "seed_node": "custom", "description": "Custom via API",
              "duration_hours": req.duration_hours, "cascade_path": [], "recovery_path": [],
              "start_datetime": req.start_datetime,
              "events": [{"event_id": f"CE{i+1:03d}", "at_hour": ev["at_hour"],
                          "timestamp": req.start_datetime, "node": ev["node"],
                          "disrupted": ev.get("disrupted",1), "event_type": ev.get("event_type","onset"),
                          "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                          "db_changes": ev.get("db_changes",{}), "description": ev.get("description","")}
                         for i, ev in enumerate(req.disruption_hours)]}
    orig = _scen.DISRUPTION_SCENARIOS
    _scen.DISRUPTION_SCENARIOS = [custom]
    _sim.DISRUPTION_SCENARIOS  = [custom]
    try:
        metrics, stock_df, event_df = run_scenario_v1(custom, verbose=False)
    except Exception as exc:
        raise HTTPException(500, f"Simulasi custom gagal: {str(exc)}")
    finally:
        _scen.DISRUPTION_SCENARIOS = orig
        _sim.DISRUPTION_SCENARIOS  = orig
    return _make_response({"scenario_id": 99, "metrics": _metrics_clean(metrics),
                           "stock_log": _df_records(stock_df), "event_log": _df_records(event_df)})

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
# RESULTS v1 (JSON dari CSV yang sudah disimpan)
# ═══════════════════════════════════════════════════════════════════
@app.get("/results/metrics", tags=["Results"])
def get_saved_metrics():
    return _make_response(_df_records(pd.read_csv(_check_csv("scenario_metrics.csv"))))

@app.get("/results/stock-log", tags=["Results"])
def get_stock_log(scenario_id: Optional[int]=None, node_type: Optional[str]=None,
                  limit: int=Query(500, ge=1, le=50000)):
    df = pd.read_csv(_check_csv("stock_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if node_type   is not None: df = df[df["node_type"]   == node_type]
    return _make_response(_df_records(df.head(limit)))

@app.get("/results/event-log", tags=["Results"])
def get_event_log(scenario_id: Optional[int]=None, rule_id: Optional[str]=None,
                  urgency: Optional[str]=None):
    df = pd.read_csv(_check_csv("event_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"]  == scenario_id]
    if rule_id     is not None: df = df[df["matched_rule"]  == rule_id]
    if urgency     is not None: df = df[df["urgency_level"] == urgency]
    return _make_response(_df_records(df))

@app.get("/results/summary", tags=["Results"])
def get_summary_statistics():
    return _make_response(_df_records(pd.read_csv(_check_csv("summary_statistics.csv"))))

@app.get("/results/rule-frequency", tags=["Results"])
def get_rule_frequency(scenario_id: Optional[int]=None):
    df = pd.read_csv(_check_csv("event_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if "matched_rule" not in df.columns: return _make_response([])
    freq = df["matched_rule"].value_counts().reset_index()
    freq.columns = ["rule_id", "count"]
    return _make_response(_df_records(freq))

@app.get("/results/decision-distribution", tags=["Results"])
def get_decision_distribution(scenario_id: Optional[int]=None):
    df = pd.read_csv(_check_csv("event_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if "orchestrator_decision" not in df.columns: return _make_response([])
    dist = df.groupby(["orchestrator_decision","urgency_level"]).size().reset_index(name="count")
    return _make_response(_df_records(dist))

@app.get("/results/disruptions-per-scenario", tags=["Results"])
def get_disruptions_per_scenario():
    result = []
    for sid in range(1, 6):
        path = os.path.join(OUTPUT_DIR, f"scenario_{sid:02d}", "stock_log.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                cnt = int(len(df[df["disrupted"] == 1])) if "disrupted" in df.columns else 0
                result.append({"scenario_id": sid, "disrupted_count": cnt})
            except Exception as e:
                result.append({"scenario_id": sid, "disrupted_count": 0, "error": str(e)})
        else:
            result.append({"scenario_id": sid, "disrupted_count": 0})
    return _make_response({"scenarios": result})

# ═══════════════════════════════════════════════════════════════════
# HITL — HELPER
# ═══════════════════════════════════════════════════════════════════
def _run_one_mode(scenario: dict, mode: str, seed: int, csv_ldr, verbose: bool) -> dict:
    """Jalankan satu skenario+mode, simpan ke subfolder, return dict hasil."""
    import traceback as _tb
    sid = scenario["scenario_id"]
    results_this, stock_dfs, event_dfs, hitl_dfs = {}, [], [], []
    try:
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
    except Exception as exc:
        raise HTTPException(500, f"S{sid:03d} mode={mode}: {str(exc)}\n{_tb.format_exc()}")

    # 1. Simpan ke subfolder per skenario (selalu overwrite)
    save_scenario_outputs(sid=sid, modes=[mode], results_this=results_this,
        stock_this=stock_dfs, events_this=event_dfs, hitl_this=hitl_dfs,
        output_dir=OUTPUT_HITL)

    # 2. Update scenario_metrics_3mode.csv saja (ringan — 1 baris per run)
    metrics_df = pd.DataFrame(list(results_this.values()))
    upsert_csv(os.path.join(OUTPUT_HITL, "scenario_metrics_3mode.csv"),
               metrics_df, ["scenario_id", "mode"])

    # 3. Update hitl_decision_log.csv jika ada (ringan)
    if hitl_dfs:
        hd_df = pd.concat(hitl_dfs, ignore_index=True)
        upsert_csv(os.path.join(OUTPUT_HITL, "hitl_decision_log.csv"),
                   hd_df, ["scenario_id", "tick", "tier"])

    # 4. stock_log_all.csv dan event_log_all.csv TIDAK di-upsert per-run
    #    (terlalu besar — akan di-rebuild via /hitl/results/rebuild atau saat batch selesai)

    mv = list(results_this.values())[0]
    sd = stock_dfs[0] if stock_dfs else pd.DataFrame()
    ed = event_dfs[0] if event_dfs else pd.DataFrame()
    hd = hitl_dfs[0]  if hitl_dfs  else pd.DataFrame()
    return {"mode": mode, "metrics": _metrics_clean(mv),
            "stock_log": _df_records(sd), "event_log": _df_records(ed),
            "hitl_log": _df_records(hd),
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
    """Distribusi jumlah skenario per severity."""
    from collections import Counter
    return _make_response(dict(Counter(s.get("severity","?") for s in HITL_SCENARIOS)))

@app.get("/hitl/scenarios/meta/type-distribution", tags=["HITL"])
def hitl_type_distribution():
    """Distribusi jumlah skenario per disruption_type."""
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
# HITL — MANAGER PROFILES
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/manager-profiles", tags=["HITL"])
def hitl_get_manager_profiles():
    """Profil probabilistik semua manager (accept/modify/override/HRT per tier)."""
    return MANAGER_PROFILES

@app.get("/hitl/manager-profiles/{tier}", tags=["HITL"])
def hitl_get_manager_profile(tier: str):
    """Profil manager satu tier."""
    if tier not in MANAGER_PROFILES:
        raise HTTPException(404, f"Tier '{tier}' tidak valid. Pilihan: {list(MANAGER_PROFILES)}")
    return {"tier": tier, "profile": MANAGER_PROFILES[tier]}

# ═══════════════════════════════════════════════════════════════════
# HITL — SIMULATION
# ═══════════════════════════════════════════════════════════════════
@app.post("/hitl/simulate/scenario", tags=["HITL"])
def hitl_simulate_scenario(req: RunHITLRequest):
    """
    Jalankan satu skenario dalam satu atau lebih mode.
    - `reactive`   : tidak ada koordinasi MAS
    - `autonomous` : MAS penuh tanpa HitL
    - `hitl`       : MAS + Advisory Human-in-the-Loop
    - `all`        : ketiga mode + 3-way comparison

    Output → `hitl/output_3mode/scenario_{id:03d}/`
    """
    valid = ("reactive","autonomous","hitl","all")
    if req.mode not in valid: raise HTTPException(400, f"mode harus: {valid}")
    s = get_scenario_hitl(req.scenario_id, json_path=_SCENARIOS_JSON)
    if s is None: raise HTTPException(404, f"Skenario {req.scenario_id} tidak ditemukan.")
    modes  = ["reactive","autonomous","hitl"] if req.mode == "all" else [req.mode]
    ldr    = _csv_loader()
    results= [_run_one_mode(s, m, req.rng_seed, ldr, req.verbose) for m in modes]

    # Rebuild file gabungan besar setelah run selesai
    rebuild_combined_csvs(OUTPUT_HITL)

    comparison = None
    if req.mode == "all" and len(results) == 3:
        try:
            comp = three_way_comparison([results[0]["metrics"]],
                                        [results[1]["metrics"]],
                                        [results[2]["metrics"]])
            comparison = _df_records(comp.reset_index()) if not comp.empty else []
        except Exception: comparison = []
    return _make_response({"scenario_id": req.scenario_id, "mode": req.mode,
                           "results": results, "comparison": comparison})

@app.post("/hitl/simulate/batch", tags=["HITL"])
def hitl_simulate_batch(req: RunAllHITLRequest):
    """
    Jalankan batch skenario. `scenario_ids=null` artinya semua 100.
    Response hanya berisi metrics (tanpa stock_log) untuk efisiensi.
    Setelah semua selesai, file gabungan (stock_log_all, event_log_all)
    di-rebuild dari subfolder secara otomatis.
    """
    valid = ("reactive","autonomous","hitl","all")
    if req.mode not in valid: raise HTTPException(400, f"mode harus: {valid}")
    if req.scenario_ids:
        target = [s for s in HITL_SCENARIOS if s["scenario_id"] in req.scenario_ids]
        if not target: raise HTTPException(404, "Tidak ada skenario yang cocok.")
    else:
        target = HITL_SCENARIOS
    modes = ["reactive","autonomous","hitl"] if req.mode == "all" else [req.mode]
    ldr   = _csv_loader()
    out   = []
    for scenario in target:
        scen_out = {"scenario_id": scenario["scenario_id"], "modes": []}
        for mode in modes:
            r = _run_one_mode(scenario, mode, req.rng_seed, ldr, req.verbose)
            scen_out["modes"].append({"mode": mode, "metrics": r["metrics"],
                                       "saved_dir": r["saved_dir"]})
        out.append(scen_out)

    # Rebuild file gabungan besar dari subfolder setelah semua selesai
    rebuild_combined_csvs(OUTPUT_HITL)

    return _make_response({"total_scenarios": len(out), "modes": modes, "results": out})

# ═══════════════════════════════════════════════════════════════════
# HITL — RESULTS (dari output_3mode/)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/results/metrics", tags=["HITL"])
def hitl_get_metrics(mode: Optional[str]=Query(None, description="reactive|autonomous|hitl"),
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
    """3-way comparison: Reactive vs Autonomous vs HITL (mean, delta%, p-value, signifikansi)."""
    df = pd.read_csv(_check_hitl_csv("comparison_3mode.csv"), index_col=0)
    return _make_response(_df_records(df.reset_index()))

@app.get("/hitl/results/summary", tags=["HITL"])
def hitl_get_summary(mode: str=Query(..., description="reactive|autonomous|hitl")):
    """Statistik (mean, std, CI 95%) dari summary_{mode}.csv."""
    if mode not in ("reactive","autonomous","hitl"):
        raise HTTPException(400, "mode harus: reactive | autonomous | hitl")
    df = pd.read_csv(_check_hitl_csv(f"summary_{mode}.csv"), index_col=0)
    return _make_response(_df_records(df.reset_index()))

@app.get("/hitl/results/hitl-log", tags=["HITL"])
def hitl_get_decision_log(
    scenario_id: Optional[int]=Query(None),
    tier:        Optional[str]=Query(None, description="supplier|farm|slaughterhouse|wholesaler|retail"),
    decision:    Optional[str]=Query(None, description="accept|modify|override|timeout"),
    limit:       int=Query(500, ge=1, le=50000)):
    """Log keputusan manager HITL dari hitl_decision_log.csv."""
    df = pd.read_csv(_check_hitl_csv("hitl_decision_log.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if tier:                    df = df[df["tier"]        == tier]
    if decision:                df = df[df["decision"]    == decision]
    return _make_response(_df_records(df.head(limit)))

@app.get("/hitl/results/hitl-log/stats", tags=["HITL"])
def hitl_decision_stats(scenario_id: Optional[int]=Query(None)):
    """Statistik agregat keputusan HITL: rate per decision-type, HRT, per tier."""
    df = pd.read_csv(_check_hitl_csv("hitl_decision_log.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if df.empty: return _make_response({"error": "Tidak ada data."})
    total = len(df)
    out = {"total_decisions": total,
           "accept_rate_%":   round(len(df[df.decision=="accept"])   / total * 100, 2),
           "modify_rate_%":   round(len(df[df.decision=="modify"])   / total * 100, 2),
           "override_rate_%": round(len(df[df.decision=="override"]) / total * 100, 2),
           "timeout_rate_%":  round(len(df[df.decision=="timeout"])  / total * 100, 2),
           "mean_HRT_hours":  round(float(df["response_time"].mean()), 3),
           "mean_modification_factor": round(float(df["modification_factor"].mean()), 3)}
    per_tier = {}
    for tier, grp in df.groupby("tier"):
        n = len(grp)
        per_tier[tier] = {"n": n,
            "accept_%":       round(len(grp[grp.decision=="accept"])   / n * 100, 2),
            "modify_%":       round(len(grp[grp.decision=="modify"])   / n * 100, 2),
            "override_%":     round(len(grp[grp.decision=="override"]) / n * 100, 2),
            "mean_HRT":       round(float(grp["response_time"].mean()), 3),
            "mean_mod_factor":round(float(grp["modification_factor"].mean()), 3)}
    out["per_tier"] = per_tier
    return _make_response(out)

@app.get("/hitl/results/stock-log", tags=["HITL"])
def hitl_get_stock_log(scenario_id: Optional[int]=Query(None),
                       mode: Optional[str]=Query(None, description="reactive|autonomous|hitl"),
                       node_type: Optional[str]=Query(None),
                       limit: int=Query(500, ge=1, le=50000)):
    """Stock log dari stock_log_all.csv. Filter: scenario_id, mode, node_type."""
    df = pd.read_csv(_check_hitl_csv("stock_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if mode:                    df = df[df["mode"]        == mode]
    if node_type:               df = df[df["node_type"]   == node_type]
    return _make_response(_df_records(df.head(limit)))

@app.get("/hitl/results/event-log", tags=["HITL"])
def hitl_get_event_log(scenario_id: Optional[int]=Query(None),
                       mode: Optional[str]=Query(None, description="autonomous|hitl"),
                       rule_id: Optional[str]=Query(None),
                       limit: int=Query(500, ge=1, le=50000)):
    """Event log coordinator dari event_log_all.csv. Reactive tidak punya event log."""
    df = pd.read_csv(_check_hitl_csv("event_log_all.csv"))
    if scenario_id is not None: df = df[df["scenario_id"] == scenario_id]
    if mode:                    df = df[df["mode"]        == mode]
    if rule_id:                 df = df[df["matched_rule"]== rule_id]
    return _make_response(_df_records(df.head(limit)))

@app.get("/hitl/results/sar-by-severity", tags=["HITL"])
def hitl_sar_by_severity():
    """SAR rata-rata per severity × mode. Berguna untuk bar chart 3-mode."""
    df  = pd.read_csv(_check_hitl_csv("scenario_metrics_3mode.csv"))
    col = "Stock Availability Rate (%)"
    rows= []
    for sev in ["low","medium","high","crisis"]:
        for mode in ["reactive","autonomous","hitl"]:
            sub = df[(df["severity"]==sev) & (df["mode"]==mode)][col].dropna()
            if len(sub) > 0:
                rows.append({"severity": sev, "mode": mode, "n": len(sub),
                             "mean_SAR": round(float(sub.mean()),3),
                             "std_SAR":  round(float(sub.std()), 3)})
    return _make_response(rows)

@app.post("/hitl/results/rebuild", tags=["HITL"])
def hitl_rebuild_combined():
    """
    Rebuild file gabungan (stock_log_all.csv, event_log_all.csv, dll)
    dari scratch berdasarkan seluruh subfolder yang ada.
    Panggil ini setelah batch run selesai atau jika data tidak konsisten.
    """
    rebuild_combined_csvs(OUTPUT_HITL)
    files = [f for f in os.listdir(OUTPUT_HITL)
             if f.endswith(".csv") and os.path.isfile(os.path.join(OUTPUT_HITL, f))]
    return _make_response({"status": "rebuilt", "files": sorted(files)})

# ═══════════════════════════════════════════════════════════════════
# HITL — CSV FILES (download & browse output_3mode/)
# ═══════════════════════════════════════════════════════════════════
@app.get("/hitl/csv/list", tags=["HITL"])
def hitl_list_csv():
    """Daftar file CSV di hitl/output_3mode/ (gabungan + subfolder per skenario)."""
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
    """
    Download file CSV gabungan dari output_3mode/.
    Pilihan: scenario_metrics_3mode.csv, stock_log_all.csv, event_log_all.csv,
    hitl_decision_log.csv, summary_reactive.csv, summary_autonomous.csv,
    summary_hitl.csv, comparison_3mode.csv
    """
    if "/" in filename or ".." in filename: raise HTTPException(400, "Nama file tidak valid.")
    if not filename.endswith(".csv"):       raise HTTPException(400, "Hanya .csv.")
    return FileResponse(_check_hitl_csv(filename), filename=filename, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.get("/hitl/csv/scenario/{scenario_id}/{filename}", tags=["HITL"])
def hitl_download_scenario_csv(scenario_id: int, filename: str):
    """Download CSV dari subfolder satu skenario: metrics|stock_log|event_log|hitl_decision_log"""
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
    """Ambil CSV skenario sebagai JSON. datatype: metrics|stock_log|event_log|hitl_decision_log"""
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
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
