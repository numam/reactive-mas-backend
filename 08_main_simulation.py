"""
╔══════════════════════════════════════════════════════════════════════════╗
║  MAIN SIMULATION — MAS Poultry Supply Chain Resilience                  ║
║  Program utama yang mengintegrasikan semua komponen sistem               ║
║                                                                          ║
║  Alur:                                                                   ║
║    Init normal → Scan periodik → Disrupsi terdeteksi →                  ║
║    Lapor ke Coordinator → Match rule → Kirim instruksi →                ║
║    Tier eksekusi → Scan recovery → Lapor pulih → Ukur metrik            ║
╚══════════════════════════════════════════════════════════════════════════╝

Penggunaan:
    python main_simulation.py                    # jalankan semua skenario
    python main_simulation.py --scenario 1       # skenario tertentu
    python main_simulation.py --scenario 1 --verbose  # dengan detail log
"""

import sys
import os
import argparse
import importlib.util
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from scipy import stats

# ── Import komponen dari file-file yang sudah ada ────────────────────────────
# Menambahkan direktori saat ini ke sys.path untuk import lokal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import dengan nama file yang benar (prefix 01_, 02_, dll)
import importlib.util

# Fungsi helper untuk import modul dari file dengan nama custom
def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Dapatkan path direktori script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Import dari file-file dengan prefix
agent_database_module = import_module_from_file(
    "agent_database", 
    os.path.join(script_dir, "01_agent_database.py")
)
disruption_triggers_module = import_module_from_file(
    "disruption_triggers", 
    os.path.join(script_dir, "02_disruption_triggers.py")
)
orchestrator_rules_module = import_module_from_file(
    "orchestrator_rules", 
    os.path.join(script_dir, "03_orchestrator_rules.py")
)
disruption_scenarios_module = import_module_from_file(
    "disruption_scenarios", 
    os.path.join(script_dir, "04_disruption_scenarios.py")
)

# Extract yang diperlukan
AGENT_DATABASE = agent_database_module.AGENT_DATABASE
init_node_state = agent_database_module.init_node_state
get_monitoring_interval = agent_database_module.get_monitoring_interval

check_disruption = disruption_triggers_module.check_disruption
check_recovery = disruption_triggers_module.check_recovery

ORCHESTRATOR_RULES = orchestrator_rules_module.ORCHESTRATOR_RULES
PATTERN_TO_RULE = orchestrator_rules_module.PATTERN_TO_RULE
apply_instructions = orchestrator_rules_module.apply_instructions

DISRUPTION_SCENARIOS = disruption_scenarios_module.DISRUPTION_SCENARIOS
get_disruption_schedule = disruption_scenarios_module.get_disruption_schedule

# ════════════════════════════════════════════════════════════════════════════
# KONSTANTA
# ════════════════════════════════════════════════════════════════════════════

CHAIN_ORDER  = ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"]
TICK_MINUTES = 15          # resolusi simulasi: 15 menit per tick
TICK_HOURS   = TICK_MINUTES / 60


# ════════════════════════════════════════════════════════════════════════════
# 1. NODE AGENT
#    Representasi setiap tier dalam simulasi
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class NodeAgent:
    node_type : str
    node_id   : str
    db_state  : dict
    disrupted : int   = 0      # 0 = normal, 1 = disrupted
    _ticks_since_last_scan: int = 0

    @property
    def interval_ticks(self) -> int:
        """Interval monitoring dalam satuan tick."""
        hours = get_monitoring_interval(self.node_type)
        return max(1, int(hours / TICK_HOURS))

    def should_scan(self, tick: int) -> bool:
        """Apakah waktunya scan di tick ini?"""
        return tick % self.interval_ticks == 0

    def scan(self, tick: int, current_time: datetime, verbose: bool = False) -> Optional[dict]:
        """
        Scan DB lokal. Jika ada disrupsi atau recovery → return report.
        Dalam kondisi normal → return None (tidak kirim pesan ke coordinator).
        """
        if not self.should_scan(tick):
            return None

        # Cek disrupsi onset
        if self.disrupted == 0:
            result = check_disruption(self.node_type, self.db_state)
            if result["disrupted"] == 1:
                self.disrupted = 1
                if verbose:
                    print(f"    [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"⚠  {self.node_id} DISRUPTED — "
                          f"{result['event_types']}")
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

        # Cek recovery
        elif self.disrupted == 1:
            recovered = check_recovery(self.node_type, self.db_state)
            if recovered:
                self.disrupted = 0
                if verbose:
                    print(f"    [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"✓  {self.node_id} RECOVERED")
                return {
                    "type"      : "RecoveryReport",
                    "node_id"   : self.node_id,
                    "node_type" : self.node_type,
                    "timestamp" : current_time,
                    "disrupted" : 0,
                    "db_snapshot": dict(self.db_state),
                }
        return None

    def apply_instruction(self, instructions: list[dict]):
        """Eksekusi instruksi dari Coordinating Agent ke DB lokal."""
        updated, _ = apply_instructions(self.node_type, self.db_state, instructions)
        self.db_state = updated

    def consume_demand(self):
        """Update DB lokal: simulasi konsumsi/demand per tick."""
        nt = self.node_type
        if nt == "retail":
            sr = self.db_state.get("sales_rate", 10)
            sold = sr * TICK_HOURS * np.random.uniform(0.85, 1.15)
            inv  = self.db_state["retail_inventory"]
            new_inv = max(0, inv - sold)
            self.db_state["retail_inventory"] = round(new_inv, 2)
            self.db_state["stockout_flag"]    = 1 if new_inv <= 0 else 0
            if new_inv < self.db_state.get("safety_stock", 30):
                self.db_state["shortage_duration"] = round(
                    self.db_state.get("shortage_duration", 0) + TICK_HOURS, 2)
            else:
                self.db_state["shortage_duration"] = 0.0

        elif nt == "wholesaler":
            demand = np.random.uniform(8, 16) * TICK_HOURS
            self.db_state["inventory_level"] = round(
                max(0, self.db_state["inventory_level"] - demand), 2)

        elif nt == "slaughterhouse":
            proc = self.db_state.get("processing_capacity", 500)
            out  = proc * TICK_HOURS * np.random.uniform(0.8, 1.0)
            self.db_state["output_stock"] = round(
                min(self.db_state.get("max_output", 400),
                    self.db_state.get("output_stock", 300) + out * 0.15), 2)

        elif nt == "farm":
            daily_feed = self.db_state.get("expected_daily_feed", 80)
            consumed   = daily_feed * TICK_HOURS * np.random.uniform(0.95, 1.05)
            self.db_state["feed_stock"] = round(
                max(0, self.db_state.get("feed_stock", 500) - consumed), 2)

        elif nt == "supplier":
            cons = np.random.uniform(2, 8) * TICK_HOURS
            self.db_state["available_supply"] = round(
                max(0, self.db_state.get("available_supply", 1000) - cons), 2)

    def inject_disruption(self, db_changes: dict):
        """Injeksi perubahan DB untuk mensimulasikan disrupsi eksternal."""
        self.db_state.update(db_changes)
        # Paksa evaluasi ulang status disrupsi setelah injeksi
        result = check_disruption(self.node_type, self.db_state)
        if result["disrupted"] == 1:
            self.disrupted = 1
        recovered = check_recovery(self.node_type, self.db_state)
        if recovered:
            self.disrupted = 0


# ════════════════════════════════════════════════════════════════════════════
# 2. COORDINATING AGENT
# ════════════════════════════════════════════════════════════════════════════

class CoordinatingAgent:

    def __init__(self):
        self.agent_status  : dict[str, int]  = {t: 0 for t in CHAIN_ORDER}
        self.event_log     : list[dict]       = []
        self.action_log    : list[dict]       = []
        self.disruption_start: Optional[datetime] = None
        self.recovery_time : Optional[datetime]   = None
        self._log_id       : int = 1

    @property
    def global_pattern(self) -> tuple:
        return tuple(self.agent_status[t] for t in CHAIN_ORDER)

    def _match_rule(self) -> tuple[str, dict]:
        pattern = self.global_pattern
        rule_id = PATTERN_TO_RULE.get(pattern, "R1")
        return rule_id, ORCHESTRATOR_RULES[rule_id]

    def receive_report(self, report: dict, agents: dict[str, "NodeAgent"],
                       verbose: bool = False) -> list[dict]:
        """
        Terima DisruptionReport atau RecoveryReport dari tier agent.
        Return: list CoordinationSignal yang harus dikirim ke tier agent.
        """
        node_type = report["node_type"]
        ts        = report["timestamp"]

        # Update status
        self.agent_status[node_type] = report["disrupted"]

        # Catat waktu awal disrupsi
        if report["disrupted"] == 1 and self.disruption_start is None:
            self.disruption_start = ts

        # Match rule
        rule_id, rule = self._match_rule()

        # Catat recovery jika kembali ke R1
        if rule_id == "R1" and self.disruption_start is not None \
                and self.recovery_time is None:
            self.recovery_time = ts

        # Tentukan event_type dari jenis report
        if report["type"] == "RecoveryReport":
            event_category = "RECOVERY"
        else:
            event_category = "DISRUPTION"

        # Kumpulkan instruksi yang akan dikirim (untuk dicatat di log)
        coordination_actions = []
        for tier, instructions in rule["instructions"].items():
            if instructions and tier in agents:
                coordination_actions.append({
                    "target_node"   : agents[tier].node_id,
                    "target_type"   : tier,
                    "n_instructions": len(instructions),
                    "instructions"  : [
                        {
                            "variable"   : i.get("variable"),
                            "operation"  : i.get("operation"),
                            "value"      : i.get("value"),
                            "description": i.get("description", ""),
                        }
                        for i in instructions
                    ],
                })

        # Buat log entry lengkap
        log_entry = {
            "log_id"               : f"L{self._log_id:03d}",
            "timestamp"            : ts.strftime("%Y-%m-%d %H:%M"),
            "event_category"       : event_category,
            "node_id"              : report.get("node_id", ""),
            "node_type"            : report.get("node_type", ""),
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
            "triggered_by"         : report.get("triggered_by", []),
            "event_types"          : report.get("event_types", []),
            "coordination_actions" : coordination_actions,
            "n_agents_instructed"  : len(coordination_actions),
        }
        self.event_log.append(log_entry)
        self._log_id += 1

        if verbose:
            print(f"    [{ts.strftime('%Y-%m-%d %H:%M')}] "
                  f"🧠 Coordinator → {rule_id} | "
                  f"{rule['decision']} | urgency={rule['urgency']}")

        # Generate CoordinationSignal per tier
        signals = []
        for tier, instructions in rule["instructions"].items():
            if instructions and tier in agents:
                signal = {
                    "target_node" : agents[tier].node_id,
                    "target_type" : tier,
                    "rule_id"     : rule_id,
                    "instructions": instructions,
                    "timestamp"   : ts,
                }
                signals.append(signal)
                self.action_log.append({
                    "timestamp"     : ts.strftime("%Y-%m-%d %H:%M"),
                    "rule_id"       : rule_id,
                    "target"        : tier,
                    "n_instructions": len(instructions),
                })
        return signals


# ════════════════════════════════════════════════════════════════════════════
# 3. METRICS CALCULATOR
# ════════════════════════════════════════════════════════════════════════════

def calculate_metrics(stock_log: list[dict], coordinator: CoordinatingAgent,
                      scenario: dict) -> dict:
    """Hitung semua metrik performa dari hasil simulasi satu skenario."""
    df = pd.DataFrame(stock_log)
    if df.empty:
        return {}

    retail = df[df["node_type"] == "retail"].copy()
    cap    = AGENT_DATABASE["retail"]["variables"]["capacity"]["default"]
    ss     = AGENT_DATABASE["retail"]["variables"]["safety_stock"]["default"]

    # ── Stock Availability Rate (SAR) ────────────────────────────────
    SAR = (retail["retail_inventory"] >= ss).mean() * 100

    # ── Time to Recovery (TTR) ───────────────────────────────────────
    if coordinator.disruption_start and coordinator.recovery_time:
        TTR_hours = (coordinator.recovery_time
                     - coordinator.disruption_start).total_seconds() / 3600
    else:
        TTR_hours = None

    # ── Stockout Duration (SOD) ──────────────────────────────────────
    SOD = retail["stockout_flag"].sum() * TICK_HOURS  # jam

    # ── Stockout Frequency (SOF) ─────────────────────────────────────
    flags = retail["stockout_flag"].values
    SOF   = int(np.sum((flags[1:] == 1) & (flags[:-1] == 0)))

    # ── Min Stock During Disruption ──────────────────────────────────
    min_stock = float(retail["retail_inventory"].min())

    # ── Recovery Speed Index (RSI) ───────────────────────────────────
    max_ttr = scenario.get("duration_hours", 96)
    RSI = round(1 - (TTR_hours / max_ttr), 4) \
        if TTR_hours is not None else None

    # ── Rule activation ──────────────────────────────────────────────
    rule_counts = {}
    for entry in coordinator.event_log:
        rid = entry["matched_rule"]
        rule_counts[rid] = rule_counts.get(rid, 0) + 1

    return {
        "scenario_id"                  : scenario["scenario_id"],
        "disruption_type"              : scenario["disruption_type"],
        "severity"                     : scenario["severity"],
        "seed_node"                    : scenario["seed_node"],
        "Stock Availability Rate (%)"  : round(SAR, 3),
        "Time to Recovery (hours)"     : round(TTR_hours, 2) if TTR_hours else None,
        "Stockout Duration (hours)"    : round(SOD, 2),
        "Stockout Frequency"           : SOF,
        "Min Stock During Disruption"  : round(min_stock, 2),
        "Recovery Speed Index"         : RSI,
        "Total Log Entries"            : len(coordinator.event_log),
        "Rules Triggered"              : rule_counts,
        "Disruption Start"             : coordinator.disruption_start.strftime("%Y-%m-%d %H:%M")
                                         if coordinator.disruption_start else None,
        "Recovery Time"                : coordinator.recovery_time.strftime("%Y-%m-%d %H:%M")
                                         if coordinator.recovery_time else None,
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. SIMULATION ENGINE
#    Menjalankan satu skenario disrupsi end-to-end
# ════════════════════════════════════════════════════════════════════════════

def run_scenario(scenario: dict, verbose: bool = False) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """
    Jalankan satu skenario disrupsi.
    Return: (metrics_dict, stock_log_df, event_log_df)
    """
    start_dt    = datetime.strptime(scenario["start_datetime"], "%Y-%m-%d %H:%M")
    duration_h  = scenario["duration_hours"]
    total_ticks = int(duration_h / TICK_HOURS)

    if verbose:
        print(f"\n{'═'*68}")
        print(f"  Scenario {scenario['scenario_id']:02d} | "
              f"{scenario['disruption_type']} | "
              f"severity={scenario['severity']} | "
              f"seed={scenario['seed_node']}")
        print(f"  {scenario['description']}")
        print(f"  Duration: {duration_h}h | Ticks: {total_ticks} | "
              f"Tick size: {TICK_MINUTES} min")
        print(f"{'═'*68}")

    # ── Inisialisasi agents ───────────────────────────────────────────
    agents = {
        tier: NodeAgent(
            node_type = tier,
            node_id   = AGENT_DATABASE[tier]["meta"]["node_id"],
            db_state  = init_node_state(tier),
        )
        for tier in CHAIN_ORDER
    }
    coordinator = CoordinatingAgent()

    # ── Jadwal disrupsi (konversi at_hour → tick) ─────────────────────
    disruption_schedule = get_disruption_schedule(scenario["scenario_id"])
    disruption_map: dict[int, list[dict]] = {}
    for event in disruption_schedule:
        tick_key = int(event["at_hour"] / TICK_HOURS)
        disruption_map.setdefault(tick_key, []).append(event)

    # ── Log containers ────────────────────────────────────────────────
    stock_log = []

    # ════════════════════════════════════════════════════════════════
    # MAIN SIMULATION LOOP
    # ════════════════════════════════════════════════════════════════
    for tick in range(total_ticks):
        current_time = start_dt + timedelta(minutes=TICK_MINUTES * tick)

        # ── Step 1: Injeksi disrupsi sesuai jadwal ────────────────────
        if tick in disruption_map:
            for event in disruption_map[tick]:
                tier    = event["node"]
                changes = event.get("db_changes", {})
                agents[tier].inject_disruption(changes)

                # Catat injected event ke event_log coordinator
                inj_status = "DISRUPTED" if event["disrupted"] == 1 else "RECOVERING"
                coordinator.event_log.append({
                    "log_id"               : f"INJ{coordinator._log_id:03d}",
                    "timestamp"            : current_time.strftime("%Y-%m-%d %H:%M"),
                    "event_category"       : "INJECTED_EVENT",
                    "node_id"              : AGENT_DATABASE[tier]["meta"]["node_id"],
                    "node_type"            : tier,
                    "supplier"             : coordinator.agent_status["supplier"],
                    "farm"                 : coordinator.agent_status["farm"],
                    "slaughterhouse"       : coordinator.agent_status["slaughterhouse"],
                    "wholesaler"           : coordinator.agent_status["wholesaler"],
                    "retail"               : coordinator.agent_status["retail"],
                    "matched_rule"         : "",
                    "orchestrator_decision": "",
                    "urgency_level"        : "",
                    "justification"        : event.get("description", ""),
                    "report_type"          : f"InjectedEvent_{inj_status}",
                    "triggered_by"         : [],
                    "event_types"          : [event.get("event_type", "")],
                    "coordination_actions" : [],
                    "n_agents_instructed"  : 0,
                    "event_id"             : event.get("event_id", ""),
                    "db_changes"           : changes,
                })
                coordinator._log_id += 1

                if verbose:
                    print(f"\n  [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"📌 EVENT {event.get('event_id','?')} — "
                          f"{tier.upper()} {inj_status}")
                    print(f"     {event.get('description','')}")

        # ── Step 2: Konsumsi demand setiap tier ───────────────────────
        for agent in agents.values():
            agent.consume_demand()

        # ── Step 3: Setiap agent scan kondisi DB lokal ────────────────
        reports = []
        for agent in agents.values():
            report = agent.scan(tick, current_time, verbose)
            if report:
                reports.append(report)

        # ── Step 4: Coordinator proses semua report ───────────────────
        signals = []
        for report in reports:
            new_signals = coordinator.receive_report(report, agents, verbose)
            signals.extend(new_signals)

        # ── Step 5: Tier agent eksekusi instruksi dari coordinator ─────
        for signal in signals:
            tier = signal["target_type"]
            if tier in agents and signal["instructions"]:
                agents[tier].apply_instruction(signal["instructions"])
                if verbose and signal["instructions"]:
                    print(f"    [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"📋 {signal['rule_id']} → {tier}: "
                          f"{len(signal['instructions'])} instruksi diterapkan")

        # ── Step 6: Catat stock log per tick (retail fokus) ───────────
        for tier, agent in agents.items():
            entry = {
                "tick"           : tick,
                "timestamp"      : current_time.strftime("%Y-%m-%d %H:%M"),
                "node_id"        : agent.node_id,
                "node_type"      : tier,
                "disrupted"      : agent.disrupted,
            }
            # Tambahkan variabel utama per tier
            if tier == "retail":
                entry.update({
                    "retail_inventory" : agent.db_state.get("retail_inventory"),
                    "safety_stock"     : agent.db_state.get("safety_stock"),
                    "stockout_flag"    : agent.db_state.get("stockout_flag"),
                    "shortage_duration": agent.db_state.get("shortage_duration"),
                    "sales_rate"       : agent.db_state.get("sales_rate"),
                    "reorder_request"  : agent.db_state.get("reorder_request"),
                })
            elif tier == "wholesaler":
                entry["inventory_level"] = agent.db_state.get("inventory_level")
                entry["pending_shipments"] = agent.db_state.get("pending_shipments")
            elif tier == "farm":
                entry["production_capacity"] = agent.db_state.get("production_capacity")
                entry["feed_stock"]          = agent.db_state.get("feed_stock")
            elif tier == "slaughterhouse":
                entry["processing_capacity"] = agent.db_state.get("processing_capacity")
                entry["output_stock"]        = agent.db_state.get("output_stock")
            elif tier == "supplier":
                entry["available_supply"] = agent.db_state.get("available_supply")
            stock_log.append(entry)

    # ── Hitung metrik ─────────────────────────────────────────────────
    metrics   = calculate_metrics(stock_log, coordinator, scenario)
    stock_df  = pd.DataFrame(stock_log)

    # Sort event_log berdasarkan timestamp (injected + report events bercampur)
    event_df  = pd.DataFrame(coordinator.event_log)
    if not event_df.empty and "timestamp" in event_df.columns:
        event_df = event_df.sort_values("timestamp").reset_index(drop=True)

    if verbose:
        print(f"\n  {'─'*68}")
        print(f"  HASIL SKENARIO {scenario['scenario_id']:02d}:")
        for k, v in metrics.items():
            if k not in ("Rules Triggered", "scenario_id"):
                print(f"    {k:<35}: {v}")
        print(f"  {'─'*68}")

    return metrics, stock_df, event_df


# ════════════════════════════════════════════════════════════════════════════
# 5. CSV PERSISTENCE  — simpan tiap skenario, gabungkan tanpa overwrite
# ════════════════════════════════════════════════════════════════════════════

def save_scenario_results(
    scenario_id : int,
    metrics     : dict,
    stock_df    : pd.DataFrame,
    event_df    : pd.DataFrame,
    output_dir  : str = "./output",
) -> dict:
    """
    Simpan hasil satu skenario ke CSV tanpa menimpa data skenario lain.

    Strategi:
      • Setiap skenario punya subfolder  output/scenario_<id>/
        yang berisi stock_log.csv dan event_log.csv khusus skenario itu.
      • File gabungan (scenario_metrics.csv, stock_log_all.csv,
        event_log_all.csv, summary_statistics.csv) di-rebuild dari
        seluruh subfolder yang ada → tidak ada data yang hilang.

    Return dict path file yang disimpan.
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Subfolder per skenario ────────────────────────────────────
    scen_dir = os.path.join(output_dir, f"scenario_{scenario_id:02d}")
    os.makedirs(scen_dir, exist_ok=True)

    # Tambahkan kolom scenario_id jika belum ada
    stock_df  = stock_df.copy()
    event_df  = event_df.copy()
    stock_df["scenario_id"] = scenario_id
    event_df["scenario_id"] = scenario_id

    stock_path = os.path.join(scen_dir, "stock_log.csv")
    event_path = os.path.join(scen_dir, "event_log.csv")
    stock_df.to_csv(stock_path, index=False)
    event_df.to_csv(event_path, index=False)

    # Simpan metrics skenario ini sebagai JSON-friendly CSV satu baris
    m_row = {k: v for k, v in metrics.items() if k != "Rules Triggered"}
    pd.DataFrame([m_row]).to_csv(os.path.join(scen_dir, "metrics.csv"), index=False)

    # ── 2. Rebuild file gabungan dari semua subfolder yang ada ────────
    all_metrics_rows = []
    all_stocks       = []
    all_events       = []

    for entry in sorted(os.listdir(output_dir)):
        sdir = os.path.join(output_dir, entry)
        if not (os.path.isdir(sdir) and entry.startswith("scenario_")):
            continue
        m_file = os.path.join(sdir, "metrics.csv")
        s_file = os.path.join(sdir, "stock_log.csv")
        e_file = os.path.join(sdir, "event_log.csv")
        if os.path.exists(m_file):
            all_metrics_rows.append(pd.read_csv(m_file))
        if os.path.exists(s_file):
            all_stocks.append(pd.read_csv(s_file))
        if os.path.exists(e_file):
            all_events.append(pd.read_csv(e_file))

    saved = {"scenario_dir": scen_dir}

    if all_metrics_rows:
        combined_metrics = pd.concat(all_metrics_rows, ignore_index=True)
        # Deduplikasi: satu baris per scenario_id (ambil yang terbaru)
        if "scenario_id" in combined_metrics.columns:
            combined_metrics = (combined_metrics
                                .drop_duplicates(subset=["scenario_id"], keep="last")
                                .sort_values("scenario_id")
                                .reset_index(drop=True))
        p = os.path.join(output_dir, "scenario_metrics.csv")
        combined_metrics.to_csv(p, index=False)
        saved["scenario_metrics"] = p

    if all_stocks:
        combined_stock = pd.concat(all_stocks, ignore_index=True)
        p = os.path.join(output_dir, "stock_log_all.csv")
        combined_stock.to_csv(p, index=False)
        saved["stock_log_all"] = p

    if all_events:
        combined_events = pd.concat(all_events, ignore_index=True)
        p = os.path.join(output_dir, "event_log_all.csv")
        combined_events.to_csv(p, index=False)
        saved["event_log_all"] = p

    # ── 3. Rebuild summary statistics ────────────────────────────────
    if all_metrics_rows:
        metrics_list = combined_metrics.to_dict(orient="records")
        try:
            summary = summary_statistics(metrics_list)
            if not summary.empty:
                p = os.path.join(output_dir, "summary_statistics.csv")
                summary.to_csv(p)
                saved["summary_statistics"] = p
        except Exception:
            pass  # summary butuh ≥2 skenario untuk CI; skip jika gagal

    return saved


# ════════════════════════════════════════════════════════════════════════════
# 6. SUMMARY STATISTICS
# ════════════════════════════════════════════════════════════════════════════

def summary_statistics(all_metrics: list[dict]) -> pd.DataFrame:
    """Ringkasan statistik dari semua skenario (mean, std, CI 95%)."""
    numeric_cols = [
        "Stock Availability Rate (%)",
        "Time to Recovery (hours)",
        "Stockout Duration (hours)",
        "Stockout Frequency",
        "Min Stock During Disruption",
        "Recovery Speed Index",
    ]
    rows = []
    df_m = pd.DataFrame(all_metrics)
    for col in numeric_cols:
        if col not in df_m.columns:
            continue
        data = df_m[col].dropna()
        if len(data) < 2:
            continue
        n    = len(data)
        mean = data.mean()
        std  = data.std()
        se   = stats.sem(data)
        ci   = stats.t.interval(0.95, df=n-1, loc=mean, scale=se)
        rows.append({
            "Metric"    : col,
            "N"         : n,
            "Mean"      : round(mean, 3),
            "Std Dev"   : round(std,  3),
            "Min"       : round(data.min(), 3),
            "Max"       : round(data.max(), 3),
            "CI 95% Lo" : round(ci[0], 3),
            "CI 95% Hi" : round(ci[1], 3),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("Metric")


# ════════════════════════════════════════════════════════════════════════════
# 6. MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MAS Poultry Supply Chain Resilience Simulation")
    parser.add_argument("--scenario", type=int, default=None,
                        help="Nomor skenario tertentu (default: semua)")
    parser.add_argument("--verbose",  action="store_true",
                        help="Tampilkan detail log per tick")
    parser.add_argument("--output-dir", type=str, default="./output",
                        help="Direktori output (default: ./output)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Pilih skenario
    if args.scenario is not None:
        scenarios = [s for s in DISRUPTION_SCENARIOS
                     if s["scenario_id"] == args.scenario]
        if not scenarios:
            print(f"ERROR: Skenario {args.scenario} tidak ditemukan.")
            print(f"Tersedia: {[s['scenario_id'] for s in DISRUPTION_SCENARIOS]}")
            sys.exit(1)
    else:
        scenarios = DISRUPTION_SCENARIOS

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  MAS Poultry Supply Chain Resilience Simulation              ║")
    print("║  Stock Availability & Speed Recovery Under Disruption        ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"  Skenario    : {len(scenarios)}")
    print(f"  Tick size   : {TICK_MINUTES} menit")
    print(f"  Output dir  : {args.output_dir}")
    print(f"  Verbose     : {args.verbose}")
    print("╚══════════════════════════════════════════════════════════════╝")

    all_metrics  = []
    all_stock    = []
    all_events   = []

    for i, scenario in enumerate(scenarios):
        print(f"\n[{i+1}/{len(scenarios)}] Running scenario "
              f"{scenario['scenario_id']} — {scenario['disruption_type']} "
              f"({scenario['severity']}) seed={scenario['seed_node']} ...",
              end=" " if not args.verbose else "\n")

        metrics, stock_df, event_df = run_scenario(scenario, verbose=args.verbose)

        # ── Simpan per-skenario (tidak overwrite) ───────────────────
        saved = save_scenario_results(
            scenario_id = scenario["scenario_id"],
            metrics     = metrics,
            stock_df    = stock_df,
            event_df    = event_df,
            output_dir  = args.output_dir,
        )

        all_metrics.append(metrics)
        all_stock.append(stock_df)
        all_events.append(event_df)

        if not args.verbose:
            sar  = metrics.get("Stock Availability Rate (%)", "N/A")
            ttr  = metrics.get("Time to Recovery (hours)",   "N/A")
            sod  = metrics.get("Stockout Duration (hours)",  "N/A")
            print(f"SAR={sar}% | TTR={ttr}h | SOD={sod}h")
        print(f"    ✓ Disimpan: {saved['scenario_dir']}")

    # ── Tampilkan ringkasan ───────────────────────────────────────────
    print("\n" + "═"*68)
    print("  MENYIMPAN HASIL...")
    print(f"  ✓ {os.path.join(args.output_dir, 'scenario_metrics.csv')}")
    print(f"  ✓ {os.path.join(args.output_dir, 'stock_log_all.csv')}")
    print(f"  ✓ {os.path.join(args.output_dir, 'event_log_all.csv')}")
    print(f"  ✓ {os.path.join(args.output_dir, 'summary_statistics.csv')}")

    # ── Tampilkan ringkasan dari file gabungan ────────────────────────
    summary_path   = os.path.join(args.output_dir, "summary_statistics.csv")
    event_all_path = os.path.join(args.output_dir, "event_log_all.csv")

    print("\n" + "═"*68)
    print("  RINGKASAN STATISTIK (semua skenario)")
    print("═"*68)
    if os.path.exists(summary_path):
        summary_df = pd.read_csv(summary_path, index_col=0)
        print(summary_df.to_string())
    else:
        print("  (belum tersedia — jalankan minimal 2 skenario)")

    if os.path.exists(event_all_path):
        event_all_df = pd.read_csv(event_all_path)

        print("\n" + "═"*68)
        print("  DISTRIBUSI KEPUTUSAN ORCHESTRATOR")
        print("═"*68)
        if "orchestrator_decision" in event_all_df.columns:
            dist = event_all_df.groupby(
                ["orchestrator_decision", "urgency_level"]
            ).size().reset_index(name="count")
            print(dist.to_string(index=False))

        print("\n" + "═"*68)
        print("  RULE ACTIVATION FREQUENCY")
        print("═"*68)
        if "matched_rule" in event_all_df.columns:
            rule_freq = event_all_df["matched_rule"].value_counts().reset_index()
            rule_freq.columns = ["Rule", "Count"]
            print(rule_freq.to_string(index=False))

    print(f"\n  Simulasi selesai. Output tersimpan di: {args.output_dir}/")
    print("═"*68)


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
