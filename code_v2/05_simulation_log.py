"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 05 — SIMULATION LOG (CONTOH OUTPUT — FINAL)                   ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  Contoh log dari Skenario AI-03: H5N1 Regional Crisis               ║
║  Mode: Autonomous & HitL Advisory                                   ║
╚══════════════════════════════════════════════════════════════════════╝

Kolom event_log:
  log_id, timestamp, supplier, farm, slaughterhouse, wholesaler, retail,
  matched_rule, orchestrator_decision, urgency_level, justification, report_type

Kolom hitl_decision_log:
  tick, timestamp, tier, rule_id, urgency, decision, response_time,
  modification_factor, n_instructions, rationale
"""

import pandas as pd

# ════════════════════════════════════════════════════════════════════
# CONTOH EVENT LOG — Skenario AI-03 (H5N1 Regional Crisis)
# ════════════════════════════════════════════════════════════════════

SAMPLE_EVENT_LOG = [
    {"log_id":"L001","timestamp":"2026-04-01 06:00","supplier":0,"farm":0,"slaughterhouse":0,"wholesaler":0,"retail":0,"matched_rule":"R1","orchestrator_decision":"Not Disruption","urgency_level":"normal","justification":"Tidak ada entitas yang mengalami gangguan","report_type":"StatusUpdate"},
    {"log_id":"L002","timestamp":"2026-04-01 12:00","supplier":0,"farm":1,"slaughterhouse":0,"wholesaler":0,"retail":0,"matched_rule":"R4","orchestrator_decision":"Potential Disruption","urgency_level":"normal","justification":"Gangguan lokal masih dapat diredam","report_type":"DisruptionReport"},
    {"log_id":"L003","timestamp":"2026-04-01 20:00","supplier":1,"farm":1,"slaughterhouse":0,"wholesaler":0,"retail":0,"matched_rule":"R3","orchestrator_decision":"Disruption","urgency_level":"high","justification":"Gangguan berurutan di hulu dan produksi","report_type":"DisruptionReport"},
    {"log_id":"L004","timestamp":"2026-04-02 06:00","supplier":1,"farm":1,"slaughterhouse":1,"wholesaler":0,"retail":0,"matched_rule":"R11","orchestrator_decision":"Disruption","urgency_level":"crisis","justification":"Mayoritas entitas upstream terganggu","report_type":"DisruptionReport"},
    {"log_id":"L005","timestamp":"2026-04-02 18:00","supplier":1,"farm":1,"slaughterhouse":1,"wholesaler":1,"retail":0,"matched_rule":"R16","orchestrator_decision":"Disruption","urgency_level":"crisis","justification":"4 node upstream terganggu — Retail harus dilindungi","report_type":"DisruptionReport"},
    {"log_id":"L006","timestamp":"2026-04-03 06:00","supplier":1,"farm":1,"slaughterhouse":1,"wholesaler":1,"retail":1,"matched_rule":"R15","orchestrator_decision":"Disruption","urgency_level":"crisis","justification":"Gangguan menyeluruh pada seluruh rantai pasok","report_type":"DisruptionReport"},
    {"log_id":"L007","timestamp":"2026-04-03 24:00","supplier":0,"farm":1,"slaughterhouse":1,"wholesaler":1,"retail":1,"matched_rule":"R17","orchestrator_decision":"Disruption","urgency_level":"crisis","justification":"Gangguan mid-chain hingga downstream","report_type":"RecoveryReport"},
    {"log_id":"L008","timestamp":"2026-04-04 12:00","supplier":0,"farm":0,"slaughterhouse":1,"wholesaler":1,"retail":1,"matched_rule":"R18","orchestrator_decision":"Disruption","urgency_level":"high","justification":"Gangguan downstream mengancam stok Retail","report_type":"RecoveryReport"},
    {"log_id":"L009","timestamp":"2026-04-05 00:00","supplier":0,"farm":0,"slaughterhouse":0,"wholesaler":1,"retail":1,"matched_rule":"R9","orchestrator_decision":"Disruption","urgency_level":"high","justification":"Gangguan distribusi berdampak ke Retail","report_type":"RecoveryReport"},
    {"log_id":"L010","timestamp":"2026-04-05 12:00","supplier":0,"farm":0,"slaughterhouse":0,"wholesaler":0,"retail":1,"matched_rule":"R14","orchestrator_decision":"Potential Disruption","urgency_level":"normal","justification":"Gangguan retail belum menjalar upstream","report_type":"RecoveryReport"},
    {"log_id":"L011","timestamp":"2026-04-06 00:00","supplier":0,"farm":0,"slaughterhouse":0,"wholesaler":0,"retail":0,"matched_rule":"R1","orchestrator_decision":"Not Disruption","urgency_level":"normal","justification":"Seluruh rantai pasok kembali normal","report_type":"RecoveryReport"},
]

# ════════════════════════════════════════════════════════════════════
# CONTOH HITL DECISION LOG — Skenario AI-03, Mode HitL
# ════════════════════════════════════════════════════════════════════

SAMPLE_HITL_LOG = [
    {"tick":96,"timestamp":"2026-04-01 12:00","tier":"farm","rule_id":"R4","urgency":"normal","decision":"accept","response_time":1.42,"modification_factor":1.0,"n_instructions":1,"rationale":"Farm Manager menerima rekomendasi coordinator (R4, urgency=normal)"},
    {"tick":112,"timestamp":"2026-04-01 20:00","tier":"supplier","rule_id":"R3","urgency":"high","decision":"modify","response_time":1.85,"modification_factor":0.88,"n_instructions":2,"rationale":"Procurement Manager memodifikasi instruksi (faktor=0.88) — pendekatan lebih konservatif"},
    {"tick":112,"timestamp":"2026-04-01 20:00","tier":"farm","rule_id":"R3","urgency":"high","decision":"accept","response_time":1.24,"modification_factor":1.0,"n_instructions":2,"rationale":"Farm Manager menerima rekomendasi coordinator (R3, urgency=high)"},
    {"tick":128,"timestamp":"2026-04-02 06:00","tier":"supplier","rule_id":"R11","urgency":"crisis","decision":"accept","response_time":0.98,"modification_factor":1.0,"n_instructions":2,"rationale":"Procurement Manager menerima rekomendasi coordinator (R11, urgency=crisis)"},
    {"tick":128,"timestamp":"2026-04-02 06:00","tier":"farm","rule_id":"R11","urgency":"crisis","decision":"override","response_time":1.11,"modification_factor":0.40,"n_instructions":2,"rationale":"Farm Manager mengganti instruksi (faktor=0.40) — kebijakan lokal diprioritaskan"},
    {"tick":128,"timestamp":"2026-04-02 06:00","tier":"wholesaler","rule_id":"R11","urgency":"crisis","decision":"accept","response_time":0.72,"modification_factor":1.0,"n_instructions":2,"rationale":"Distribution Manager menerima rekomendasi coordinator (R11, urgency=crisis)"},
    {"tick":144,"timestamp":"2026-04-02 18:00","tier":"wholesaler","rule_id":"R16","urgency":"crisis","decision":"modify","response_time":0.95,"modification_factor":0.85,"n_instructions":2,"rationale":"Distribution Manager memodifikasi instruksi (faktor=0.85) — pendekatan lebih konservatif"},
    {"tick":160,"timestamp":"2026-04-03 06:00","tier":"retail","rule_id":"R15","urgency":"crisis","decision":"accept","response_time":0.22,"modification_factor":1.0,"n_instructions":2,"rationale":"Store Manager menerima rekomendasi coordinator (R15, urgency=crisis)"},
    {"tick":160,"timestamp":"2026-04-03 06:00","tier":"wholesaler","rule_id":"R15","urgency":"crisis","decision":"timeout","response_time":1.82,"modification_factor":1.0,"n_instructions":3,"rationale":"Distribution Manager tidak merespons dalam 1.5h → auto-accept"},
]

# ════════════════════════════════════════════════════════════════════
# CONTOH STOCK LOG — Retail tier, Skenario AI-03
# ════════════════════════════════════════════════════════════════════

SAMPLE_STOCK_LOG_RETAIL = [
    {"tick":0,  "timestamp":"2026-04-01 06:00","node_id":"retail_1","node_type":"retail","disrupted":0,"retail_inventory":88.5,"safety_stock":30,"stockout_flag":0,"shortage_duration":0.0,"sales_rate":8.5},
    {"tick":48, "timestamp":"2026-04-01 18:00","node_id":"retail_1","node_type":"retail","disrupted":0,"retail_inventory":72.1,"safety_stock":30,"stockout_flag":0,"shortage_duration":0.0,"sales_rate":11.2},
    {"tick":96, "timestamp":"2026-04-02 06:00","node_id":"retail_1","node_type":"retail","disrupted":0,"retail_inventory":54.8,"safety_stock":30,"stockout_flag":0,"shortage_duration":0.0,"sales_rate":9.8},
    {"tick":160,"timestamp":"2026-04-03 06:00","node_id":"retail_1","node_type":"retail","disrupted":1,"retail_inventory":4.0, "safety_stock":30,"stockout_flag":1,"shortage_duration":5.0, "sales_rate":22.0},
    {"tick":176,"timestamp":"2026-04-03 10:00","node_id":"retail_1","node_type":"retail","disrupted":1,"retail_inventory":0.0, "safety_stock":30,"stockout_flag":1,"shortage_duration":9.0, "sales_rate":20.5},
    {"tick":240,"timestamp":"2026-04-04 00:00","node_id":"retail_1","node_type":"retail","disrupted":1,"retail_inventory":12.3,"safety_stock":30,"stockout_flag":0,"shortage_duration":2.5, "sales_rate":14.2},
    {"tick":320,"timestamp":"2026-04-05 00:00","node_id":"retail_1","node_type":"retail","disrupted":1,"retail_inventory":28.5,"safety_stock":30,"stockout_flag":0,"shortage_duration":0.5, "sales_rate":11.8},
    {"tick":384,"timestamp":"2026-04-06 00:00","node_id":"retail_1","node_type":"retail","disrupted":0,"retail_inventory":68.0,"safety_stock":30,"stockout_flag":0,"shortage_duration":0.0, "sales_rate":10.5},
]

# ════════════════════════════════════════════════════════════════════
# FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def get_event_log_df() -> pd.DataFrame:
    return pd.DataFrame(SAMPLE_EVENT_LOG)

def get_hitl_log_df() -> pd.DataFrame:
    return pd.DataFrame(SAMPLE_HITL_LOG)

def get_stock_log_df() -> pd.DataFrame:
    return pd.DataFrame(SAMPLE_STOCK_LOG_RETAIL)

def get_hitl_summary(df: pd.DataFrame) -> dict:
    total = len(df)
    return {
        "total_decisions"  : total,
        "accept_rate_%"    : round(len(df[df.decision=="accept"])  / total * 100, 1),
        "modify_rate_%"    : round(len(df[df.decision=="modify"])  / total * 100, 1),
        "override_rate_%"  : round(len(df[df.decision=="override"])/ total * 100, 1),
        "timeout_rate_%"   : round(len(df[df.decision=="timeout"]) / total * 100, 1),
        "mean_HRT_hours"   : round(df["response_time"].mean(), 3),
        "mean_mod_factor"  : round(df["modification_factor"].mean(), 3),
    }

if __name__ == "__main__":
    event_df = get_event_log_df()
    hitl_df  = get_hitl_log_df()
    stock_df = get_stock_log_df()

    print("=== SAMPLE EVENT LOG (Skenario AI-03: H5N1 Regional Crisis) ===\n")
    cols = ["log_id","timestamp","supplier","farm","slaughterhouse",
            "wholesaler","retail","matched_rule","urgency_level"]
    print(event_df[cols].to_string(index=False))

    print("\n=== SAMPLE HITL DECISION LOG ===\n")
    hitl_cols = ["timestamp","tier","rule_id","urgency","decision",
                 "response_time","modification_factor","rationale"]
    print(hitl_df[hitl_cols].to_string(index=False))

    print("\n=== HITL SUMMARY ===")
    for k, v in get_hitl_summary(hitl_df).items():
        print(f"  {k:<25}: {v}")

    print("\n=== SAMPLE STOCK LOG (Retail) ===\n")
    print(stock_df.to_string(index=False))
