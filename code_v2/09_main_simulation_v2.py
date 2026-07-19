"""
╔══════════════════════════════════════════════════════════════════════════╗
║  FILE 09 — MAIN SIMULATION v2 (FINAL)                                  ║
║  MAS + HitL + Avian Influenza | Poultry Supply Chain Resilience        ║
║                                                                          ║
║  Perbaikan dari v1:                                                      ║
║  [M1] Initial state diambil dari CSV data normal (bukan default schema) ║
║  [M2] db_changes konsisten dengan variabel referensi (M2 fixed di 04b) ║
║  [M3] Recovery baseline mengacu rata-rata historis CSV normal           ║
║                                                                          ║
║  Mode:                                                                   ║
║    --mode autonomous  : MAS tanpa HitL                                  ║
║    --mode hitl        : MAS + Advisory HitL probabilistik               ║
║    --mode both        : jalankan keduanya + comparison (default)        ║
║                                                                          ║
║  Penggunaan:                                                             ║
║    python 09_main_simulation_v2.py                                      ║
║    python 09_main_simulation_v2.py --scenario 3 --mode hitl --verbose   ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_database            import AGENT_DATABASE, init_node_state, get_monitoring_interval
from disruption_triggers       import check_disruption, check_recovery
from orchestrator_rules        import ORCHESTRATOR_RULES, PATTERN_TO_RULE, apply_instructions
from disruption_scenarios_ai   import AI_OUTBREAK_SCENARIOS, get_disruption_schedule
from hitl_module               import HitLEngine, MANAGER_PROFILES

# ════════════════════════════════════════════════════════════════════════════
# KONSTANTA
# ════════════════════════════════════════════════════════════════════════════

CHAIN_ORDER  = ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"]
TICK_MINUTES = 15
TICK_HOURS   = TICK_MINUTES / 60

# Kolom DB yang dipetakan dari CSV ke init state
CSV_TO_DB_COLUMNS = {
    "supplier"      : ["available_supply","capacity","lead_time","shipment_status",
                       "price_index","supplier_reliability"],
    "farm"          : ["live_inventory","production_capacity","planned_capacity",
                       "growth_status","mortality_rate","outgoing_orders",
                       "feed_stock","expected_daily_feed","disease_alert"],
    "slaughterhouse": ["input_inventory","processing_capacity","max_capacity",
                       "queue_length","processing_delay","output_stock","max_output",
                       "equipment_status","hygiene_compliance","worker_availability"],
    "wholesaler"    : ["inventory_level","capacity","reorder_point","shipment_status",
                       "distribution_capacity","pending_shipments",
                       "delivery_schedule","incoming_orders"],
    "retail"        : ["retail_inventory","capacity","safety_stock","sales_rate",
                       "expected_sales_rate","shortage_duration","demand_estimate",
                       "reorder_request","stockout_flag"],
}


# ════════════════════════════════════════════════════════════════════════════
# [M1+M3] CSV DATA LOADER
# ════════════════════════════════════════════════════════════════════════════

class CSVDataLoader:
    """
    [M1] Mengambil initial state dari CSV data normal (bukan default schema).
    [M3] Menghitung recovery baseline dari rata-rata historis CSV.
    """

    def __init__(self, data_dir: str = "."):
        self._cache       : dict[str, pd.DataFrame] = {}
        self._baselines   : dict[str, dict]          = {}
        self._data_dir    = data_dir
        self._load_all()

    def _load_all(self):
        for tier in CHAIN_ORDER:
            path = os.path.join(self._data_dir, f"data_normal_{tier}.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                self._cache[tier] = df
                # Hitung baseline mean per kolom numerik
                num_cols = df.select_dtypes(include="number").columns
                num_cols = [c for c in num_cols
                            if c not in ("disrupted","disease_alert",
                                         "stockout_flag","above_safety_stock")]
                self._baselines[tier] = df[num_cols].mean().to_dict()

    def get_initial_state(self, tier: str,
                          rng: Optional[np.random.Generator] = None) -> dict:
        """
        [M1] Ambil 1 baris random dari CSV sebagai initial state.
        Fallback ke schema default jika CSV tidak tersedia.
        """
        if tier not in self._cache or self._cache[tier].empty:
            return init_node_state(tier)

        df  = self._cache[tier]
        idx = int(rng.integers(0, len(df))) if rng else 0
        row = df.iloc[idx]

        # Ambil kolom yang relevan untuk DB state
        db_cols   = CSV_TO_DB_COLUMNS.get(tier, [])
        schema    = AGENT_DATABASE[tier]["variables"]
        state     = init_node_state(tier)   # mulai dari default

        for col in db_cols:
            if col in row.index and col in schema:
                val = row[col]
                # Konversi type yang sesuai
                if isinstance(val, float) and np.isnan(val):
                    continue
                state[col] = val

        # Pastikan disrupted=0 (kondisi normal)
        state.pop("disrupted", None)
        return state

    def get_recovery_threshold(self, tier: str, variable: str,
                               default_ratio: float = 0.75) -> Optional[float]:
        """
        [M3] Recovery threshold berbasis baseline historis CSV.
        Lebih realistis daripada threshold statis.
        Gunakan 75% dari rata-rata historis sebagai batas recovery.
        """
        if tier in self._baselines and variable in self._baselines[tier]:
            baseline_mean = self._baselines[tier][variable]
            return round(baseline_mean * default_ratio, 2)
        return None

    def get_baselines(self, tier: str) -> dict:
        return self._baselines.get(tier, {})


# ════════════════════════════════════════════════════════════════════════════
# NODE AGENT
# ════════════════════════════════════════════════════════════════════════════

class NodeAgent:
    def __init__(self, node_type: str, node_id: str, db_state: dict):
        self.node_type = node_type
        self.node_id   = node_id
        self.db_state  = dict(db_state)
        self.disrupted = 0

    @property
    def interval_ticks(self) -> int:
        return max(1, int(get_monitoring_interval(self.node_type) / TICK_HOURS))

    def should_scan(self, tick: int) -> bool:
        return tick % self.interval_ticks == 0

    def scan(self, tick: int, current_time: datetime,
             verbose: bool = False) -> Optional[dict]:
        """
        Scan DB lokal sesuai interval monitoring.
        Hanya kirim report ke coordinator jika ada perubahan status disrupsi.
        """
        if not self.should_scan(tick):
            return None

        if self.disrupted == 0:
            result = check_disruption(self.node_type, self.db_state)
            if result["disrupted"] == 1:
                self.disrupted = 1
                if verbose:
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"⚠  {self.node_id} DISRUPTED — {result['event_types']}")
                return {
                    "type"        : "DisruptionReport",
                    "node_id"     : self.node_id,
                    "node_type"   : self.node_type,
                    "timestamp"   : current_time,
                    "disrupted"   : 1,
                    "triggered_by": result["triggered_by"],
                    "event_types" : result["event_types"],
                    "db_snapshot" : dict(self.db_state),
                }

        elif self.disrupted == 1:
            if check_recovery(self.node_type, self.db_state):
                self.disrupted = 0
                if verbose:
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"✓  {self.node_id} RECOVERED")
                return {
                    "type"       : "RecoveryReport",
                    "node_id"    : self.node_id,
                    "node_type"  : self.node_type,
                    "timestamp"  : current_time,
                    "disrupted"  : 0,
                    "db_snapshot": dict(self.db_state),
                }
        return None

    def apply_instruction(self, instructions: list):
        """Eksekusi instruksi dari Coordinating Agent."""
        updated, _ = apply_instructions(self.node_type, self.db_state, instructions)
        self.db_state = updated

    def consume_demand(self):
        """Simulasi konsumsi/demand per tick — berbasis nilai DB aktual."""
        nt = self.node_type

        if nt == "retail":
            sr      = self.db_state.get("sales_rate", 10)
            sold    = sr * TICK_HOURS * np.random.uniform(0.85, 1.15)
            inv     = max(0.0, self.db_state.get("retail_inventory", 90) - sold)
            ss      = self.db_state.get("safety_stock", 30)
            self.db_state["retail_inventory"] = round(inv, 2)
            self.db_state["stockout_flag"]    = 1 if inv <= 0 else 0
            if inv < ss:
                self.db_state["shortage_duration"] = round(
                    self.db_state.get("shortage_duration", 0) + TICK_HOURS, 2)
            else:
                self.db_state["shortage_duration"] = 0.0

        elif nt == "wholesaler":
            demand = np.random.uniform(8, 16) * TICK_HOURS
            self.db_state["inventory_level"] = round(
                max(0.0, self.db_state.get("inventory_level", 200) - demand), 2)

        elif nt == "slaughterhouse":
            proc = self.db_state.get("processing_capacity", 500)
            out  = self.db_state.get("output_stock", 300)
            add  = proc * TICK_HOURS * np.random.uniform(0.8, 1.0) * 0.15
            self.db_state["output_stock"] = round(
                min(self.db_state.get("max_output", 400), out + add), 2)

        elif nt == "farm":
            daily = self.db_state.get("expected_daily_feed", 80)
            self.db_state["feed_stock"] = round(
                max(0.0, self.db_state.get("feed_stock", 500)
                    - daily * TICK_HOURS * np.random.uniform(0.95, 1.05)), 2)

        elif nt == "supplier":
            self.db_state["available_supply"] = round(
                max(0.0, self.db_state.get("available_supply", 1000)
                    - np.random.uniform(2, 8) * TICK_HOURS), 2)

    def inject_disruption(self, db_changes: dict):
        """
        Injeksi perubahan DB sesuai event skenario.
        Langsung evaluasi status disrupsi setelah injeksi.
        """
        self.db_state.update(db_changes)
        result = check_disruption(self.node_type, self.db_state)
        if result["disrupted"] == 1:
            self.disrupted = 1
        if check_recovery(self.node_type, self.db_state):
            self.disrupted = 0


# ════════════════════════════════════════════════════════════════════════════
# COORDINATING AGENT
# ════════════════════════════════════════════════════════════════════════════

class CoordinatingAgent:
    def __init__(self):
        self.agent_status     = {t: 0 for t in CHAIN_ORDER}
        self.event_log        = []
        self.action_log       = []
        self.disruption_start = None
        self.recovery_time    = None
        self._log_id          = 1

    @property
    def global_pattern(self) -> tuple:
        return tuple(self.agent_status[t] for t in CHAIN_ORDER)

    def _match_rule(self):
        rule_id = PATTERN_TO_RULE.get(self.global_pattern, "R1")
        return rule_id, ORCHESTRATOR_RULES[rule_id]

    def receive_report(self, report: dict, agents: dict,
                       verbose: bool = False) -> list:
        node_type = report["node_type"]
        ts        = report["timestamp"]

        self.agent_status[node_type] = report["disrupted"]

        if report["disrupted"] == 1 and self.disruption_start is None:
            self.disruption_start = ts

        rule_id, rule = self._match_rule()

        if rule_id == "R1" and self.disruption_start and not self.recovery_time:
            self.recovery_time = ts

        self.event_log.append({
            "log_id"               : f"L{self._log_id:03d}",
            "timestamp"            : ts.strftime("%Y-%m-%d %H:%M"),
            "supplier"             : self.agent_status["supplier"],
            "farm"                 : self.agent_status["farm"],
            "slaughterhouse"       : self.agent_status["slaughterhouse"],
            "wholesaler"           : self.agent_status["wholesaler"],
            "retail"               : self.agent_status["retail"],
            "matched_rule"         : rule_id,
            "orchestrator_decision": rule["decision"],
            "urgency_level"        : rule["urgency"],
            "justification"        : rule["justification"],
            "report_type"          : report["type"],
        })
        self._log_id += 1

        if verbose:
            print(f"    [{ts.strftime('%H:%M')}] 🧠 {rule_id} | "
                  f"{rule['decision']} | {rule['urgency']}")

        signals = []
        for tier, instructions in rule["instructions"].items():
            if instructions and tier in agents:
                signals.append({
                    "target_node" : agents[tier].node_id,
                    "target_type" : tier,
                    "rule_id"     : rule_id,
                    "urgency"     : rule["urgency"],
                    "instructions": instructions,
                    "timestamp"   : ts,
                })
        return signals


# ════════════════════════════════════════════════════════════════════════════
# METRICS CALCULATOR
# ════════════════════════════════════════════════════════════════════════════

def calculate_metrics(stock_log: list, coordinator: CoordinatingAgent,
                      scenario: dict,
                      hitl_engine: Optional[HitLEngine] = None,
                      csv_loader : Optional[CSVDataLoader] = None) -> dict:
    df     = pd.DataFrame(stock_log)
    retail = df[df["node_type"] == "retail"].copy() if not df.empty else pd.DataFrame()

    # [M3] Gunakan baseline dari CSV untuk SAR threshold
    if csv_loader:
        baseline_inv = csv_loader.get_baselines("retail").get("retail_inventory", 90)
        sar_threshold = baseline_inv * 0.75   # 75% dari rata-rata historis
    else:
        sar_threshold = AGENT_DATABASE["retail"]["variables"]["safety_stock"]["default"]

    SAR = (retail["retail_inventory"] >= sar_threshold).mean() * 100 \
        if len(retail) else 0.0

    # TTR
    TTR = None
    if coordinator.disruption_start and coordinator.recovery_time:
        TTR = (coordinator.recovery_time
               - coordinator.disruption_start).total_seconds() / 3600

    # SOD, SOF
    flags = retail["stockout_flag"].values if "stockout_flag" in retail.columns \
        else np.zeros(len(retail))
    SOD = float(flags.sum()) * TICK_HOURS
    SOF = int(np.sum((flags[1:] == 1) & (flags[:-1] == 0)))

    min_stock = float(retail["retail_inventory"].min()) if len(retail) else 0.0
    max_ttr   = scenario.get("duration_hours", 96)
    RSI       = round(1 - TTR / max_ttr, 4) if TTR is not None else None

    metrics = {
        "scenario_id"                  : scenario["scenario_id"],
        "disruption_type"              : scenario["disruption_type"],
        "subtype"                      : scenario.get("subtype", ""),
        "severity"                     : scenario["severity"],
        "seed_node"                    : scenario["seed_node"],
        "cascade_depth"                : len(scenario.get("cascade_path", [])),
        "SAR_threshold_used"           : round(sar_threshold, 2),
        "Stock Availability Rate (%)"  : round(SAR, 3),
        "Time to Recovery (hours)"     : round(TTR, 2) if TTR else None,
        "Stockout Duration (hours)"    : round(SOD, 2),
        "Stockout Frequency"           : SOF,
        "Min Stock During Disruption"  : round(min_stock, 2),
        "Recovery Speed Index"         : RSI,
        "Total Coordinator Events"     : len(coordinator.event_log),
        "Disruption Start"             : coordinator.disruption_start.strftime(
                                          "%Y-%m-%d %H:%M") if coordinator.disruption_start else None,
        "Recovery Time"                : coordinator.recovery_time.strftime(
                                          "%Y-%m-%d %H:%M") if coordinator.recovery_time else None,
    }

    if hitl_engine:
        s = hitl_engine.get_summary()
        metrics.update({
            "HitL_Accept_Rate_%"     : s.get("accept_rate_%"),
            "HitL_Modify_Rate_%"     : s.get("modify_rate_%"),
            "HitL_Override_Rate_%"   : s.get("override_rate_%"),
            "HitL_Mean_HRT_hours"    : s.get("mean_HRT_hours"),
            "HitL_Modify_Factor"     : s.get("mean_modification_factor"),
        })

    return metrics


# ════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE
# ════════════════════════════════════════════════════════════════════════════

def run_scenario(scenario: dict, mode: str = "autonomous",
                 csv_loader: Optional[CSVDataLoader] = None,
                 verbose: bool = False,
                 rng_seed: Optional[int] = None):
    """
    Jalankan satu skenario end-to-end.
    mode: "autonomous" | "hitl"
    """
    np.random.seed(rng_seed)
    rng         = np.random.default_rng(rng_seed)
    start_dt    = datetime.strptime(scenario["start_datetime"], "%Y-%m-%d %H:%M")
    total_ticks = int(scenario["duration_hours"] / TICK_HOURS)

    if verbose:
        print(f"\n{'═'*65}")
        print(f"  S{scenario['scenario_id']:02d} | {scenario.get('subtype','')} "
              f"| {scenario['severity']} | mode={mode.upper()}")
        print(f"  {scenario['description'][:75]}...")
        print(f"{'═'*65}")

    # ── [M1] Inisialisasi dari CSV atau default ────────────────────────
    agents = {}
    for tier in CHAIN_ORDER:
        if csv_loader:
            db_state = csv_loader.get_initial_state(tier, rng)
        else:
            db_state = init_node_state(tier)
        agents[tier] = NodeAgent(
            node_type=tier,
            node_id  =AGENT_DATABASE[tier]["meta"]["node_id"],
            db_state =db_state,
        )

    coordinator = CoordinatingAgent()
    hitl        = HitLEngine(rng_seed=rng_seed) if mode == "hitl" else None

    # Disruption schedule → tick map
    schedule    = get_disruption_schedule(scenario["scenario_id"])
    disrupt_map = {}
    for ev in schedule:
        tk = int(ev["at_hour"] / TICK_HOURS)
        disrupt_map.setdefault(tk, []).append(ev)

    stock_log = []

    # ════════════════════════════════════════════════════════════════
    # MAIN SIMULATION LOOP
    # ════════════════════════════════════════════════════════════════
    for tick in range(total_ticks):
        current_time = start_dt + timedelta(minutes=TICK_MINUTES * tick)

        # Step 1: Injeksi disrupsi sesuai jadwal
        if tick in disrupt_map:
            for ev in disrupt_map[tick]:
                agents[ev["node"]].inject_disruption(ev.get("db_changes", {}))
                if verbose:
                    status = "DISRUPTED" if ev["disrupted"] else "RECOVERING"
                    print(f"\n  [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"📌 {ev.get('event_id','')} {ev['node'].upper()} {status}")
                    print(f"     {ev.get('description','')[:80]}")

        # Step 2: Konsumsi demand setiap tier
        for agent in agents.values():
            agent.consume_demand()

        # Step 3: Setiap agent scan DB lokal
        reports = []
        for agent in agents.values():
            r = agent.scan(tick, current_time, verbose)
            if r:
                reports.append(r)

        # Step 4: Coordinator proses reports → generate signals
        signals = []
        for report in reports:
            signals.extend(coordinator.receive_report(report, agents, verbose))

        # Step 5: HitL atau autonomous eksekusi instruksi
        for signal in signals:
            tier         = signal["target_type"]
            instructions = signal.get("instructions", [])
            if not instructions or tier not in agents:
                continue

            if mode == "hitl" and hitl:
                dec = hitl.process_signal(
                    signal, tick=tick,
                    timestamp=current_time.strftime("%Y-%m-%d %H:%M"),
                    urgency=signal.get("urgency", "normal"),
                )
                final_instructions = dec.final_instructions
                if verbose and dec.decision != "accept":
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"👤 {tier}: {dec.decision.upper()} "
                          f"factor={dec.modification_factor:.2f} "
                          f"HRT={dec.response_time:.2f}h")
            else:
                final_instructions = instructions

            agents[tier].apply_instruction(final_instructions)

        # Step 6: Catat stock log per tick
        for tier, agent in agents.items():
            entry = {
                "tick"     : tick,
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M"),
                "node_id"  : agent.node_id,
                "node_type": tier,
                "disrupted": agent.disrupted,
            }
            if tier == "retail":
                entry.update({
                    "retail_inventory" : agent.db_state.get("retail_inventory"),
                    "safety_stock"     : agent.db_state.get("safety_stock"),
                    "stockout_flag"    : agent.db_state.get("stockout_flag", 0),
                    "shortage_duration": agent.db_state.get("shortage_duration", 0),
                    "sales_rate"       : agent.db_state.get("sales_rate"),
                    "reorder_request"  : agent.db_state.get("reorder_request", 0),
                })
            elif tier == "wholesaler":
                entry["inventory_level"]  = agent.db_state.get("inventory_level")
                entry["pending_shipments"]= agent.db_state.get("pending_shipments")
            elif tier == "farm":
                entry["production_capacity"] = agent.db_state.get("production_capacity")
                entry["mortality_rate"]      = agent.db_state.get("mortality_rate")
                entry["feed_stock"]          = agent.db_state.get("feed_stock")
            elif tier == "slaughterhouse":
                entry["processing_capacity"] = agent.db_state.get("processing_capacity")
                entry["output_stock"]        = agent.db_state.get("output_stock")
            elif tier == "supplier":
                entry["available_supply"] = agent.db_state.get("available_supply")
            stock_log.append(entry)

    # ── Hitung metrik ──────────────────────────────────────────────
    metrics  = calculate_metrics(stock_log, coordinator, scenario, hitl, csv_loader)
    stock_df = pd.DataFrame(stock_log)
    event_df = pd.DataFrame(coordinator.event_log)
    hitl_df  = hitl.get_log_df() if hitl else pd.DataFrame()

    if verbose:
        print(f"\n  ── Metrics ({mode.upper()}) ──")
        for k, v in metrics.items():
            if k not in ("scenario_id","disruption_type","subtype","seed_node"):
                print(f"    {k:<38}: {v}")

    return metrics, stock_df, event_df, hitl_df


# ════════════════════════════════════════════════════════════════════════════
# SUMMARY & COMPARISON
# ════════════════════════════════════════════════════════════════════════════

def summary_statistics(all_metrics: list) -> pd.DataFrame:
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
        rows.append({"Metric": col, "N": n,
                     "Mean": round(mean,3), "Std": round(std,3),
                     "Min": round(data.min(),3), "Max": round(data.max(),3),
                     "CI_95_Lo": round(ci[0],3), "CI_95_Hi": round(ci[1],3)})
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


def compare_modes(auto_metrics: list, hitl_metrics: list) -> pd.DataFrame:
    higher_better = {"Stock Availability Rate (%)","Recovery Speed Index"}
    cols = ["Stock Availability Rate (%)","Time to Recovery (hours)",
            "Stockout Duration (hours)","Stockout Frequency","Recovery Speed Index"]
    df_a, df_h = pd.DataFrame(auto_metrics), pd.DataFrame(hitl_metrics)
    rows = []
    for col in cols:
        if col not in df_a.columns or col not in df_h.columns:
            continue
        a, h = df_a[col].dropna().mean(), df_h[col].dropna().mean()
        delta     = h - a
        delta_pct = (delta / a * 100) if a != 0 else 0
        better    = "HitL" if (col in higher_better and h > a) or \
                              (col not in higher_better and h < a) else "Autonomous"
        rows.append({"Metric": col,
                     "Autonomous": round(a,3), "HitL": round(h,3),
                     "Delta": round(delta,3), "Delta_%": round(delta_pct,2),
                     "Better": better})
    return pd.DataFrame(rows).set_index("Metric") if rows else pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# SAVE SCENARIO RESULTS
# ════════════════════════════════════════════════════════════════════════════

def save_scenario_results_v2(
    scenario_id : int,
    mode        : str,
    metrics     : dict,
    stock_df    : pd.DataFrame,
    event_df    : pd.DataFrame,
    hitl_df     : pd.DataFrame,
    output_dir  : str = "./output_v2",
) -> dict:
    """
    Simpan hasil satu run (scenario + mode) ke subfolder tersendiri.
    Rebuild file gabungan dari semua subfolder tanpa menimpa data lain.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Subfolder per scenario+mode
    folder_name = f"scenario_{scenario_id:02d}_{mode}"
    scen_dir    = os.path.join(output_dir, folder_name)
    os.makedirs(scen_dir, exist_ok=True)

    s_df = stock_df.copy(); s_df["scenario_id"] = scenario_id; s_df["mode"] = mode
    e_df = event_df.copy(); e_df["scenario_id"] = scenario_id; e_df["mode"] = mode

    s_df.to_csv(os.path.join(scen_dir, "stock_log.csv"),  index=False)
    e_df.to_csv(os.path.join(scen_dir, "event_log.csv"),  index=False)

    m_row = {k: v for k, v in metrics.items() if k != "Rules Triggered"}
    m_row["mode"] = mode
    pd.DataFrame([m_row]).to_csv(os.path.join(scen_dir, "metrics.csv"), index=False)

    if not hitl_df.empty:
        h_df = hitl_df.copy(); h_df["scenario_id"] = scenario_id; h_df["mode"] = mode
        h_df.to_csv(os.path.join(scen_dir, "hitl_decision_log.csv"), index=False)

    saved = {"scenario_dir": scen_dir}

    # 2. Rebuild combined files
    all_m, all_s, all_e, all_h = [], [], [], []

    for entry in sorted(os.listdir(output_dir)):
        d = os.path.join(output_dir, entry)
        if not (os.path.isdir(d) and entry.startswith("scenario_")):
            continue
        for fname, target in [("metrics.csv", all_m), ("stock_log.csv", all_s),
                               ("event_log.csv", all_e)]:
            p = os.path.join(d, fname)
            if os.path.exists(p):
                target.append(pd.read_csv(p))
        hp = os.path.join(d, "hitl_decision_log.csv")
        if os.path.exists(hp):
            all_h.append(pd.read_csv(hp))

    if all_m:
        cm = pd.concat(all_m, ignore_index=True)
        if "scenario_id" in cm.columns and "mode" in cm.columns:
            cm = cm.drop_duplicates(subset=["scenario_id","mode"], keep="last")
            cm = cm.sort_values(["scenario_id","mode"]).reset_index(drop=True)
        cm.to_csv(os.path.join(output_dir, "scenario_metrics.csv"), index=False)
        saved["scenario_metrics"] = os.path.join(output_dir, "scenario_metrics.csv")

        # Rebuild summaries
        for m_mode in ["autonomous", "hitl"]:
            subset = cm[cm["mode"] == m_mode].to_dict(orient="records") if "mode" in cm.columns else []
            if len(subset) >= 2:
                try:
                    s = summary_statistics(subset)
                    if not s.empty:
                        p = os.path.join(output_dir, f"summary_{m_mode}.csv")
                        s.to_csv(p)
                        saved[f"summary_{m_mode}"] = p
                except Exception:
                    pass

        # Rebuild comparison
        if "mode" in cm.columns:
            auto_list = cm[cm["mode"]=="autonomous"].to_dict(orient="records")
            hitl_list = cm[cm["mode"]=="hitl"].to_dict(orient="records")
            if auto_list and hitl_list:
                try:
                    comp = compare_modes(auto_list, hitl_list)
                    if not comp.empty:
                        p = os.path.join(output_dir, "comparison_auto_vs_hitl.csv")
                        comp.to_csv(p)
                        saved["comparison"] = p
                except Exception:
                    pass

    if all_s:
        pd.concat(all_s, ignore_index=True).to_csv(
            os.path.join(output_dir, "stock_log_all.csv"), index=False)
        saved["stock_log_all"] = os.path.join(output_dir, "stock_log_all.csv")

    if all_e:
        pd.concat(all_e, ignore_index=True).to_csv(
            os.path.join(output_dir, "event_log_all.csv"), index=False)
        saved["event_log_all"] = os.path.join(output_dir, "event_log_all.csv")

    if all_h:
        pd.concat(all_h, ignore_index=True).to_csv(
            os.path.join(output_dir, "hitl_decision_log.csv"), index=False)
        saved["hitl_decision_log"] = os.path.join(output_dir, "hitl_decision_log.csv")

    return saved


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MAS + HitL — Avian Influenza Poultry Supply Chain")
    parser.add_argument("--scenario",   type=int, default=None,
                        help="Nomor skenario (default: semua)")
    parser.add_argument("--mode",       choices=["autonomous","hitl","both"],
                        default="both")
    parser.add_argument("--verbose",    action="store_true")
    parser.add_argument("--output-dir", type=str, default="./output_v2")
    parser.add_argument("--data-dir",   type=str, default=".",
                        help="Folder berisi data_normal_*.csv")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    np.random.seed(args.seed)

    # [M1+M3] Load CSV data normal
    csv_loader = CSVDataLoader(data_dir=args.data_dir)
    loaded = list(csv_loader._cache.keys())
    print(f"  CSV loaded: {loaded if loaded else 'NONE — using schema defaults'}")

    scenarios = ([s for s in AI_OUTBREAK_SCENARIOS
                  if s["scenario_id"] == args.scenario]
                 if args.scenario else AI_OUTBREAK_SCENARIOS)
    if not scenarios:
        print(f"ERROR: Skenario {args.scenario} tidak ditemukan.")
        sys.exit(1)

    modes = ["autonomous","hitl"] if args.mode == "both" else [args.mode]

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  MAS + HitL — Avian Influenza | Poultry Supply Chain        ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"  Skenario : {len(scenarios)} | Mode: {args.mode.upper()} | Seed: {args.seed}")
    print(f"  [M1] Initial state dari CSV: {'YES' if loaded else 'NO (default)'}")
    print(f"  [M3] Recovery baseline dari CSV: {'YES' if loaded else 'NO (static)'}")
    print("╚══════════════════════════════════════════════════════════════╝")

    results   = {"autonomous": [], "hitl": []}

    for scenario in scenarios:
        for mode in modes:
            label = f"[S{scenario['scenario_id']:02d}|{mode.upper()}]"
            print(f"\n{label} {scenario.get('subtype','')} | "
                  f"{scenario['severity']} ...",
                  end=" " if not args.verbose else "\n")

            metrics, stock_df, event_df, hitl_df = run_scenario(
                scenario, mode=mode,
                csv_loader=csv_loader,
                verbose=args.verbose,
                rng_seed=args.seed + scenario["scenario_id"],
            )

            # NEW — save immediately, no buffering
            metrics["mode"] = mode
            saved = save_scenario_results_v2(
                scenario_id = scenario["scenario_id"],
                mode        = mode,
                metrics     = metrics,
                stock_df    = stock_df,
                event_df    = event_df,
                hitl_df     = hitl_df,
                output_dir  = args.output_dir,
            )
            results[mode].append(metrics)
            if not args.verbose:
                print(f"    ✓ Disimpan: {saved['scenario_dir']}")

            if not args.verbose:
                sar = metrics.get("Stock Availability Rate (%)", "N/A")
                ttr = metrics.get("Time to Recovery (hours)", "N/A")
                sod = metrics.get("Stockout Duration (hours)", "N/A")
                print(f"SAR={sar}% | TTR={ttr}h | SOD={sod}h")

    # Print summary from saved files
    print(f"\n{'═'*65}")
    print("  HASIL TERSIMPAN DI:")
    for f in ["scenario_metrics.csv","stock_log_all.csv","event_log_all.csv",
              "hitl_decision_log.csv","summary_autonomous.csv","summary_hitl.csv",
              "comparison_auto_vs_hitl.csv"]:
        p = os.path.join(args.output_dir, f)
        if os.path.exists(p):
            print(f"  ✓ {p}")


if __name__ == "__main__":
    main()
