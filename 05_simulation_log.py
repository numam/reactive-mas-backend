"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 05 — SIMULATION LOG (CONTOH OUTPUT)                            ║
║  MAS Poultry Supply Chain                                            ║
║  Contoh log output simulasi dari Skenario 4 (Full Crisis)            ║
║  Format identik dengan output fungsi run_simulation()                ║
╚══════════════════════════════════════════════════════════════════════╝

Kolom log:
  log_id               : ID unik log entry
  timestamp            : waktu kejadian (YYYY-MM-DD HH:MM)
  supplier/farm/...    : status biner node (0/1)
  matched_rule         : rule ID yang aktif
  orchestrator_decision: keputusan orchestrator
  coordination_actions : instruksi yang dikirim ke node
  affected_agents      : node yang menerima instruksi
  affected_attributes  : atribut DB yang diubah
  urgency_level        : normal / high / crisis
  system_trend         : stabil / stagnan / memburuk / membaik
  recovery_progress    : none / monitoring / partial / ongoing / completed
  justification        : alasan keputusan
"""

import pandas as pd

SIMULATION_LOG = [
    # ── FASE 1: Kondisi Normal ────────────────────────────────────────
    {
        "log_id"               : "L001",
        "timestamp"            : "2026-02-15 06:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R1",
        "orchestrator_decision": "Not Disruption",
        "coordination_actions" : "Update global_summary_state only",
        "affected_agents"      : "–",
        "affected_attributes"  : "–",
        "urgency_level"        : "normal",
        "system_trend"         : "stabil",
        "recovery_progress"    : "none",
        "justification"        : "Tidak ada entitas yang mengalami gangguan",
    },
    {
        "log_id"               : "L002",
        "timestamp"            : "2026-02-15 09:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R1",
        "orchestrator_decision": "Not Disruption",
        "coordination_actions" : "Update global_summary_state only",
        "affected_agents"      : "–",
        "affected_attributes"  : "–",
        "urgency_level"        : "normal",
        "system_trend"         : "stabil",
        "recovery_progress"    : "none",
        "justification"        : "Tidak ada entitas yang mengalami gangguan",
    },
    # ── FASE 2: Onset Disrupsi di Supplier ───────────────────────────
    {
        "log_id"               : "L003",
        "timestamp"            : "2026-02-15 12:00",
        "supplier"             : 1, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R2",
        "orchestrator_decision": "Potential Disruption",
        "coordination_actions" : "Increase update frequency; Farm & Wholesaler early warning",
        "affected_agents"      : "Farm, Wholesaler",
        "affected_attributes"  : "production_capacity, inventory_level",
        "urgency_level"        : "normal",
        "system_trend"         : "stagnan",
        "recovery_progress"    : "monitoring",
        "justification"        : "Gangguan tunggal di Supplier berpotensi menjalar ke downstream",
    },
    {
        "log_id"               : "L004",
        "timestamp"            : "2026-02-15 18:00",
        "supplier"             : 1, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R2",
        "orchestrator_decision": "Potential Disruption",
        "coordination_actions" : "Increase update frequency; Farm & Wholesaler early warning",
        "affected_agents"      : "Farm, Wholesaler",
        "affected_attributes"  : "production_capacity, inventory_level",
        "urgency_level"        : "normal",
        "system_trend"         : "stagnan",
        "recovery_progress"    : "monitoring",
        "justification"        : "Gangguan tunggal di Supplier berpotensi menjalar ke downstream",
    },
    # ── FASE 3: Eskalasi ke Farm ──────────────────────────────────────
    {
        "log_id"               : "L005",
        "timestamp"            : "2026-02-16 00:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R3",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Adjust outgoing_orders; prioritize retail allocation",
        "affected_agents"      : "Farm, Wholesaler",
        "affected_attributes"  : "outgoing_orders, allocation_plan",
        "urgency_level"        : "high",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "not started",
        "justification"        : "Gangguan berurutan di Supplier dan Farm mengancam produksi",
    },
    {
        "log_id"               : "L006",
        "timestamp"            : "2026-02-16 06:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R3",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Adjust outgoing_orders; prioritize retail allocation",
        "affected_agents"      : "Farm, Wholesaler",
        "affected_attributes"  : "outgoing_orders, allocation_plan",
        "urgency_level"        : "high",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "not started",
        "justification"        : "Gangguan berurutan di Supplier dan Farm mengancam produksi",
    },
    # ── FASE 4: Eskalasi ke Slaughterhouse (Crisis) ───────────────────
    {
        "log_id"               : "L007",
        "timestamp"            : "2026-02-16 12:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 1, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R11",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Global coordination mode; hanya Retail kritis dipenuhi",
        "affected_agents"      : "All upstream agents",
        "affected_attributes"  : "all upstream attributes",
        "urgency_level"        : "crisis",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "not started",
        "justification"        : "Mayoritas entitas upstream terganggu secara bersamaan",
    },
    {
        "log_id"               : "L008",
        "timestamp"            : "2026-02-16 18:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 1, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R11",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Global coordination mode; hanya Retail kritis dipenuhi",
        "affected_agents"      : "All upstream agents",
        "affected_attributes"  : "all upstream attributes",
        "urgency_level"        : "crisis",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "not started",
        "justification"        : "Mayoritas entitas upstream terganggu secara bersamaan",
    },
    # ── FASE 5: Eskalasi ke Wholesaler (R16) ──────────────────────────
    {
        "log_id"               : "L009",
        "timestamp"            : "2026-02-17 00:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 1, "wholesaler": 1, "retail": 0,
        "matched_rule"         : "R16",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Full upstream coordination; lindungi Retail dari dampak cascading",
        "affected_agents"      : "Supplier, Farm, Slaughterhouse, Wholesaler",
        "affected_attributes"  : "all upstream attributes, inventory_level",
        "urgency_level"        : "crisis",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "not started",
        "justification"        : "Gangguan 4 node upstream — Retail satu-satunya yang perlu dilindungi",
    },
    # ── FASE 6: Full Crisis (R15) ─────────────────────────────────────
    {
        "log_id"               : "L010",
        "timestamp"            : "2026-02-17 08:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 1, "wholesaler": 1, "retail": 1,
        "matched_rule"         : "R15",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Full crisis mode; semua keputusan dibatasi coordination_messages",
        "affected_agents"      : "All agents",
        "affected_attributes"  : "all critical attributes",
        "urgency_level"        : "crisis",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "ongoing",
        "justification"        : "Gangguan menyeluruh pada seluruh rantai pasok",
    },
    {
        "log_id"               : "L011",
        "timestamp"            : "2026-02-17 14:00",
        "supplier"             : 1, "farm": 1, "slaughterhouse": 1, "wholesaler": 1, "retail": 1,
        "matched_rule"         : "R15",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Full crisis mode; semua keputusan dibatasi coordination_messages",
        "affected_agents"      : "All agents",
        "affected_attributes"  : "all critical attributes",
        "urgency_level"        : "crisis",
        "system_trend"         : "memburuk",
        "recovery_progress"    : "ongoing",
        "justification"        : "Gangguan menyeluruh pada seluruh rantai pasok",
    },
    # ── FASE 7: Recovery Bertahap ─────────────────────────────────────
    {
        "log_id"               : "L012",
        "timestamp"            : "2026-02-17 18:00",
        "supplier"             : 0, "farm": 1, "slaughterhouse": 1, "wholesaler": 1, "retail": 1,
        "matched_rule"         : "R17",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Prioritaskan aliran ke Retail; batasi permintaan non-kritis Farm",
        "affected_agents"      : "Farm, Slaughterhouse, Wholesaler, Retail",
        "affected_attributes"  : "production_capacity, processing_delay, inventory_level, reorder_request",
        "urgency_level"        : "crisis",
        "system_trend"         : "membaik",
        "recovery_progress"    : "partial",
        "justification"        : "Supplier pulih; mid-chain hingga downstream masih terganggu",
    },
    {
        "log_id"               : "L013",
        "timestamp"            : "2026-02-18 04:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 1, "wholesaler": 1, "retail": 1,
        "matched_rule"         : "R18",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Proteksi Retail; bypass Slaughterhouse jika memungkinkan",
        "affected_agents"      : "Slaughterhouse, Wholesaler, Retail",
        "affected_attributes"  : "processing_delay, delivery_schedule, retail_inventory",
        "urgency_level"        : "high",
        "system_trend"         : "membaik",
        "recovery_progress"    : "partial",
        "justification"        : "Supplier & Farm pulih; RPH, Wholesaler, Retail masih terganggu",
    },
    {
        "log_id"               : "L014",
        "timestamp"            : "2026-02-18 12:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 1, "retail": 1,
        "matched_rule"         : "R9",
        "orchestrator_decision": "Disruption",
        "coordination_actions" : "Cap reorder_request Retail; prioritize inventory_level",
        "affected_agents"      : "Retail, Wholesaler",
        "affected_attributes"  : "reorder_request, inventory_level",
        "urgency_level"        : "high",
        "system_trend"         : "membaik",
        "recovery_progress"    : "partial",
        "justification"        : "RPH pulih; Wholesaler dan Retail masih terganggu",
    },
    {
        "log_id"               : "L015",
        "timestamp"            : "2026-02-18 18:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 1,
        "matched_rule"         : "R14",
        "orchestrator_decision": "Potential Disruption",
        "coordination_actions" : "Request demand_observation update dari Retail",
        "affected_agents"      : "Retail",
        "affected_attributes"  : "demand_observation, reorder_request",
        "urgency_level"        : "normal",
        "system_trend"         : "membaik",
        "recovery_progress"    : "partial",
        "justification"        : "Wholesaler pulih; hanya Retail yang masih terganggu",
    },
    # ── FASE 8: Sistem Pulih Penuh ────────────────────────────────────
    {
        "log_id"               : "L016",
        "timestamp"            : "2026-02-19 00:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R1",
        "orchestrator_decision": "Not Disruption",
        "coordination_actions" : "Update global_summary_state only; relax coordination flags",
        "affected_agents"      : "–",
        "affected_attributes"  : "–",
        "urgency_level"        : "normal",
        "system_trend"         : "membaik",
        "recovery_progress"    : "completed",
        "justification"        : "Seluruh rantai pasok kembali normal",
    },
    {
        "log_id"               : "L017",
        "timestamp"            : "2026-02-19 06:00",
        "supplier"             : 0, "farm": 0, "slaughterhouse": 0, "wholesaler": 0, "retail": 0,
        "matched_rule"         : "R1",
        "orchestrator_decision": "Not Disruption",
        "coordination_actions" : "Update global_summary_state only",
        "affected_agents"      : "–",
        "affected_attributes"  : "–",
        "urgency_level"        : "normal",
        "system_trend"         : "stabil",
        "recovery_progress"    : "completed",
        "justification"        : "Sistem stabil pasca pemulihan penuh",
    },
]


def get_log_dataframe() -> pd.DataFrame:
    """Kembalikan log sebagai Pandas DataFrame."""
    return pd.DataFrame(SIMULATION_LOG)


def get_log_summary(df: pd.DataFrame) -> dict:
    """Ringkasan statistik dari log simulasi."""
    return {
        "total_entries"       : len(df),
        "disruption_duration" : len(df[df["matched_rule"] != "R1"]),
        "crisis_ticks"        : len(df[df["urgency_level"] == "crisis"]),
        "rules_triggered"     : df["matched_rule"].value_counts().to_dict(),
        "peak_urgency"        : "crisis" if "crisis" in df["urgency_level"].values else "high",
        "recovery_completed"  : "completed" in df["recovery_progress"].values,
    }


if __name__ == "__main__":
    df = get_log_dataframe()
    summary = get_log_summary(df)

    print("=== SIMULATION LOG — Skenario 4: Full Crisis ===\n")
    cols = ["log_id","timestamp","supplier","farm","slaughterhouse",
            "wholesaler","retail","matched_rule","urgency_level",
            "system_trend","recovery_progress"]
    print(df[cols].to_string(index=False))

    print("\n=== LOG SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k:<25}: {v}")
