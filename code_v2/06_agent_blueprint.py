"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 06 — AGENT SPECIFICATION / BLUEPRINT (FINAL)                  ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  Spesifikasi lengkap setiap agent: peran, DB, trigger, perilaku     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

AGENT_BLUEPRINTS = {

    # ══════════════════════════════════════════════════════════════════
    # SUPPLIER AGENT
    # ══════════════════════════════════════════════════════════════════
    "supplier_agent": {
        "identity": {
            "agent_id"   : "supplier_1",
            "agent_type" : "SupplierAgent",
            "tier"       : 1,
            "role"       : "Pemasok bahan baku (DOC, pakan, obat-obatan) ke Farm",
            "upstream"   : None,
            "downstream" : "farm_1",
        },
        "sensing": {
            "interval_hours"   : 18,
            "interval_label"   : "12–24 jam",
            "change_character" : "Lambat, strategis",
            "variables_monitored": [
                "available_supply", "lead_time", "price_index",
                "supplier_reliability", "shipment_status",
            ],
        },
        "local_database": {
            "available_supply"    : {"type": "float", "unit": "unit",  "default": 1000},
            "capacity"            : {"type": "float", "unit": "unit",  "default": 1000},
            "lead_time"           : {"type": "float", "unit": "hari",  "default": 2},
            "shipment_status"     : {"type": "str",   "unit": "-",     "default": "on_time"},
            "price_index"         : {"type": "float", "unit": "ratio", "default": 1.0},
            "supplier_reliability": {"type": "float", "unit": "ratio", "default": 1.0},
        },
        "behavior": {
            "normal": [
                "Scan DB lokal setiap 18 jam",
                "Update available_supply berdasarkan konsumsi dan produksi",
                "Tidak mengirim pesan ke Coordinating Agent",
            ],
            "on_disruption_detected": [
                "Evaluasi trigger rules (OR logic)",
                "Set disrupted=1 di DB lokal",
                "Kirim DisruptionReport ke Coordinating Agent",
                "Tunggu instruksi dari Coordinating Agent",
            ],
            "on_instruction_received": [
                "Terima CoordinationSignal dari Coordinating Agent",
                "Eksekusi instruksi: update variabel DB sesuai operasi",
                "Lanjutkan scan periodik",
            ],
            "on_recovery": [
                "Evaluasi recovery conditions (semua harus terpenuhi)",
                "Set disrupted=0 di DB lokal",
                "Kirim RecoveryReport ke Coordinating Agent",
            ],
        },
        "messages": {
            "emit": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
            "receive": [
                "CoordinationSignal{target_node, instructions: [{variable, operation, value, condition}]}",
            ],
        },
        "disruption_triggers": {
            "logic"     : "OR",
            "conditions": [
                "SUP-T1: available_supply < capacity * 0.30",
                "SUP-T2: lead_time > 4 hari",
                "SUP-T3: price_index > 1.50",
                "SUP-T4: supplier_reliability < 0.60",
                "SUP-T5: shipment_status == cancelled",
            ],
        },
        "recovery_conditions": {
            "logic"     : "AND (semua harus terpenuhi)",
            "conditions": [
                "SUP-R1: available_supply >= capacity * 0.50",
                "SUP-R2: lead_time <= 3 hari",
                "SUP-R3: price_index <= 1.25",
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # FARM AGENT
    # ══════════════════════════════════════════════════════════════════
    "farm_agent": {
        "identity": {
            "agent_id"   : "farm_1",
            "agent_type" : "FarmAgent",
            "tier"       : 2,
            "role"       : "Mengelola produksi ayam broiler dan pengiriman ke Slaughterhouse",
            "upstream"   : "supplier_1",
            "downstream" : "slaughterhouse_1",
        },
        "sensing": {
            "interval_hours"   : 9,
            "interval_label"   : "6–12 jam",
            "change_character" : "Biologis, dinamis",
            "variables_monitored": [
                "production_capacity", "mortality_rate", "feed_stock",
                "disease_alert", "growth_status", "live_inventory",
            ],
        },
        "local_database": {
            "live_inventory"      : {"type": "float", "unit": "ekor",  "default": 800},
            "production_capacity" : {"type": "float", "unit": "ekor",  "default": 800},
            "planned_capacity"    : {"type": "float", "unit": "ekor",  "default": 800},
            "growth_status"       : {"type": "str",   "unit": "-",     "default": "normal"},
            "mortality_rate"      : {"type": "float", "unit": "ratio", "default": 0.02},
            "outgoing_orders"     : {"type": "float", "unit": "ekor",  "default": 500},
            "feed_stock"          : {"type": "float", "unit": "kg",    "default": 500},
            "expected_daily_feed" : {"type": "float", "unit": "kg",    "default": 80},
            "disease_alert"       : {"type": "int",   "unit": "bool",  "default": 0},
        },
        "behavior": {
            "normal": [
                "Scan DB lokal setiap 9 jam",
                "Update live_inventory, mortality_rate, feed_stock",
                "Kirim outgoing_orders ke Slaughterhouse sesuai jadwal",
                "Tidak mengirim pesan ke Coordinating Agent",
            ],
            "on_disruption_detected": [
                "Evaluasi trigger rules (OR logic)",
                "Set disrupted=1 di DB lokal",
                "Kirim DisruptionReport ke Coordinating Agent",
                "Tahan/kurangi outgoing_orders sambil menunggu instruksi",
            ],
            "on_instruction_received": [
                "Eksekusi instruksi: sesuaikan outgoing_orders, feed_stock, production_capacity",
                "Update DB lokal sesuai operasi",
                "Lanjutkan scan periodik",
            ],
            "on_recovery": [
                "Cek semua recovery conditions terpenuhi",
                "Set disrupted=0",
                "Kirim RecoveryReport ke Coordinating Agent",
                "Normalkan outgoing_orders",
            ],
        },
        "messages": {
            "emit": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
            "receive": [
                "CoordinationSignal{target_node, instructions: [{variable, operation, value, condition}]}",
            ],
        },
        "disruption_triggers": {
            "logic"     : "OR",
            "conditions": [
                "FAR-T1: production_capacity < planned_capacity * 0.60",
                "FAR-T2: mortality_rate > 0.08",
                "FAR-T3: feed_stock < expected_daily_feed * 3",
                "FAR-T4: disease_alert == 1",
                "FAR-T5: growth_status == stunted",
            ],
        },
        "recovery_conditions": {
            "logic"     : "AND (semua harus terpenuhi)",
            "conditions": [
                "FAR-R1: production_capacity >= planned_capacity * 0.75",
                "FAR-R2: mortality_rate <= 0.04",
                "FAR-R3: disease_alert == 0",
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # SLAUGHTERHOUSE AGENT
    # ══════════════════════════════════════════════════════════════════
    "slaughterhouse_agent": {
        "identity": {
            "agent_id"   : "slaughterhouse_1",
            "agent_type" : "SlaughterhouseAgent",
            "tier"       : 3,
            "role"       : "Memproses ayam dari Farm dan mengirim produk jadi ke Wholesaler",
            "upstream"   : "farm_1",
            "downstream" : "wholesaler_1",
        },
        "sensing": {
            "interval_hours"   : 3,
            "interval_label"   : "2–4 jam",
            "change_character" : "Operasional, time-sensitive",
            "variables_monitored": [
                "processing_capacity", "queue_length", "processing_delay",
                "equipment_status", "worker_availability", "output_stock",
            ],
        },
        "local_database": {
            "input_inventory"    : {"type": "float", "unit": "ekor",  "default": 400},
            "processing_capacity": {"type": "float", "unit": "ekor",  "default": 500},
            "max_capacity"       : {"type": "float", "unit": "ekor",  "default": 500},
            "queue_length"       : {"type": "float", "unit": "ekor",  "default": 50},
            "processing_delay"   : {"type": "float", "unit": "jam",   "default": 0},
            "output_stock"       : {"type": "float", "unit": "kg",    "default": 300},
            "max_output"         : {"type": "float", "unit": "kg",    "default": 400},
            "equipment_status"   : {"type": "str",   "unit": "-",     "default": "operational"},
            "hygiene_compliance" : {"type": "float", "unit": "ratio", "default": 1.0},
            "worker_availability": {"type": "float", "unit": "ratio", "default": 1.0},
        },
        "behavior": {
            "normal": [
                "Scan DB lokal setiap 3 jam",
                "Proses input dari Farm sesuai processing_capacity",
                "Update output_stock dan kirim ke Wholesaler",
                "Tidak mengirim pesan ke Coordinating Agent",
            ],
            "on_disruption_detected": [
                "Evaluasi trigger rules (OR logic)",
                "Set disrupted=1 di DB lokal",
                "Kirim DisruptionReport ke Coordinating Agent",
                "Kurangi processing target, catat processing_delay",
            ],
            "on_instruction_received": [
                "Eksekusi instruksi: sesuaikan processing_capacity, worker_availability",
                "Prioritaskan antrian sesuai instruksi",
                "Update DB lokal",
            ],
            "on_recovery": [
                "Cek semua recovery conditions terpenuhi",
                "Set disrupted=0",
                "Kirim RecoveryReport ke Coordinating Agent",
                "Normalkan jadwal pemrosesan",
            ],
        },
        "messages": {
            "emit": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
            "receive": [
                "CoordinationSignal{target_node, instructions: [{variable, operation, value, condition}]}",
            ],
        },
        "disruption_triggers": {
            "logic"     : "OR",
            "conditions": [
                "SLH-T1: processing_capacity < max_capacity * 0.50",
                "SLH-T2: queue_length > 100 ekor",
                "SLH-T3: processing_delay > 4 jam",
                "SLH-T4: equipment_status == down",
                "SLH-T5: worker_availability < 0.60",
                "SLH-T6: output_stock < max_output * 0.30",
            ],
        },
        "recovery_conditions": {
            "logic"     : "AND (semua harus terpenuhi)",
            "conditions": [
                "SLH-R1: processing_capacity >= max_capacity * 0.70",
                "SLH-R2: processing_delay <= 2 jam",
                "SLH-R3: equipment_status != down",
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # WHOLESALER AGENT
    # ══════════════════════════════════════════════════════════════════
    "wholesaler_agent": {
        "identity": {
            "agent_id"   : "wholesaler_1",
            "agent_type" : "WholesalerAgent",
            "tier"       : 4,
            "role"       : "Mendistribusikan produk dari Slaughterhouse ke Retail",
            "upstream"   : "slaughterhouse_1",
            "downstream" : "retail_1",
        },
        "sensing": {
            "interval_hours"   : 2,
            "interval_label"   : "1–3 jam",
            "change_character" : "Time-sensitive, distribusi kritis",
            "variables_monitored": [
                "inventory_level", "pending_shipments", "incoming_orders",
                "delivery_schedule", "shipment_status",
            ],
        },
        "local_database": {
            "inventory_level"     : {"type": "float", "unit": "kg",  "default": 200},
            "capacity"            : {"type": "float", "unit": "kg",  "default": 300},
            "reorder_point"       : {"type": "float", "unit": "kg",  "default": 90},
            "shipment_status"     : {"type": "str",   "unit": "-",   "default": "on_time"},
            "distribution_capacity":{"type": "float", "unit": "kg",  "default": 300},
            "pending_shipments"   : {"type": "float", "unit": "kg",  "default": 0},
            "delivery_schedule"   : {"type": "str",   "unit": "-",   "default": "normal"},
            "incoming_orders"     : {"type": "float", "unit": "kg",  "default": 150},
        },
        "behavior": {
            "normal": [
                "Scan DB lokal setiap 2 jam",
                "Terima pasokan dari Slaughterhouse, update inventory_level",
                "Distribusikan ke Retail sesuai incoming_orders",
                "Tidak mengirim pesan ke Coordinating Agent",
            ],
            "on_disruption_detected": [
                "Evaluasi trigger rules (OR logic)",
                "Set disrupted=1 di DB lokal",
                "Kirim DisruptionReport ke Coordinating Agent",
                "Prioritaskan distribusi ke Retail kritis",
            ],
            "on_instruction_received": [
                "Eksekusi instruksi: sesuaikan inventory_level, pending_shipments, delivery_schedule",
                "Update DB lokal",
            ],
            "on_recovery": [
                "Cek semua recovery conditions terpenuhi",
                "Set disrupted=0",
                "Kirim RecoveryReport ke Coordinating Agent",
                "Normalkan delivery_schedule",
            ],
        },
        "messages": {
            "emit": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
            "receive": [
                "CoordinationSignal{target_node, instructions: [{variable, operation, value, condition}]}",
            ],
        },
        "disruption_triggers": {
            "logic"     : "OR",
            "conditions": [
                "WHO-T1: inventory_level < capacity * 0.30",
                "WHO-T2: pending_shipments > 50 kg",
                "WHO-T3: incoming_orders > distribution_capacity * 1.20",
                "WHO-T4: delivery_schedule == delayed",
                "WHO-T5: shipment_status == cancelled",
            ],
        },
        "recovery_conditions": {
            "logic"     : "AND (semua harus terpenuhi)",
            "conditions": [
                "WHO-R1: inventory_level >= capacity * 0.50",
                "WHO-R2: pending_shipments <= 20 kg",
                "WHO-R3: delivery_schedule == normal",
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # RETAIL AGENT
    # ══════════════════════════════════════════════════════════════════
    "retail_agent": {
        "identity": {
            "agent_id"   : "retail_1",
            "agent_type" : "RetailAgent",
            "tier"       : 5,
            "role"       : "Menjual produk ke konsumen akhir dan menjaga ketersediaan stok",
            "upstream"   : "wholesaler_1",
            "downstream" : None,
        },
        "sensing": {
            "interval_hours"   : 0.75,
            "interval_label"   : "30–60 menit",
            "change_character" : "Sangat fluktuatif, demand-driven",
            "variables_monitored": [
                "retail_inventory", "sales_rate", "shortage_duration",
                "stockout_flag", "safety_stock",
            ],
        },
        "local_database": {
            "retail_inventory"   : {"type": "float", "unit": "kg",     "default": 90},
            "capacity"           : {"type": "float", "unit": "kg",     "default": 150},
            "safety_stock"       : {"type": "float", "unit": "kg",     "default": 30},
            "sales_rate"         : {"type": "float", "unit": "kg/jam", "default": 10},
            "expected_sales_rate": {"type": "float", "unit": "kg/jam", "default": 10},
            "shortage_duration"  : {"type": "float", "unit": "jam",    "default": 0},
            "demand_estimate"    : {"type": "float", "unit": "kg",     "default": 90},
            "reorder_request"    : {"type": "float", "unit": "kg",     "default": 0},
            "stockout_flag"      : {"type": "int",   "unit": "bool",   "default": 0},
        },
        "behavior": {
            "normal": [
                "Scan DB lokal setiap 45 menit",
                "Update retail_inventory berdasarkan sales_rate",
                "Kirim reorder_request ke Wholesaler jika inventory mendekati safety_stock",
                "Tidak mengirim pesan ke Coordinating Agent",
            ],
            "on_disruption_detected": [
                "Evaluasi trigger rules (OR logic)",
                "Set disrupted=1 di DB lokal",
                "Kirim DisruptionReport ke Coordinating Agent",
                "Update shortage_duration dan stockout_flag",
            ],
            "on_instruction_received": [
                "Eksekusi instruksi: sesuaikan reorder_request, safety_stock, demand_estimate",
                "Update DB lokal",
            ],
            "on_recovery": [
                "Cek semua recovery conditions terpenuhi",
                "Set disrupted=0, shortage_duration=0, stockout_flag=0",
                "Kirim RecoveryReport ke Coordinating Agent",
            ],
        },
        "messages": {
            "emit": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
            "receive": [
                "CoordinationSignal{target_node, instructions: [{variable, operation, value, condition}]}",
            ],
        },
        "disruption_triggers": {
            "logic"     : "OR",
            "conditions": [
                "RET-T1: retail_inventory < safety_stock",
                "RET-T2: stockout_flag == 1",
                "RET-T3: sales_rate > expected_sales_rate * 1.50",
                "RET-T4: shortage_duration > 2 jam",
            ],
        },
        "recovery_conditions": {
            "logic"     : "AND (semua harus terpenuhi)",
            "conditions": [
                "RET-R1: retail_inventory >= capacity * 0.40",
                "RET-R2: stockout_flag == 0",
                "RET-R3: shortage_duration == 0",
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # COORDINATING AGENT (ORCHESTRATOR)
    # ══════════════════════════════════════════════════════════════════
    "coordinating_agent": {
        "identity": {
            "agent_id"   : "coordinator_1",
            "agent_type" : "CoordinatingAgent",
            "tier"       : 0,
            "role"       : "Menerima laporan disrupsi, mencocokkan rule, mengirim instruksi ke tier agent",
            "upstream"   : None,
            "downstream" : None,
            "scope"      : "All tiers (supplier → farm → slaughterhouse → wholesaler → retail)",
        },
        "sensing": {
            "mode"             : "Event-driven",
            "interval_hours"   : None,
            "trigger"          : "Menerima DisruptionReport atau RecoveryReport dari tier agent",
            "change_character" : "Reaktif terhadap event dari tier agent",
        },
        "local_database": {
            "global_pattern"  : {"type": "tuple(int×5)", "description": "(supplier,farm,slaughterhouse,wholesaler,retail) status biner"},
            "agent_status"    : {"type": "dict",         "description": "Status terkini setiap tier agent {node_id: disrupted}"},
            "event_log"       : {"type": "list",         "description": "Log semua DisruptionReport dan RecoveryReport"},
            "action_log"      : {"type": "list",         "description": "Log semua CoordinationSignal yang dikirim"},
            "active_rule"     : {"type": "str",          "description": "Rule ID yang sedang aktif (R1–R18)"},
            "disruption_start": {"type": "datetime",     "description": "Waktu pertama kali ada disrupsi"},
            "recovery_time"   : {"type": "datetime",     "description": "Waktu sistem kembali ke R1 (Not Disruption)"},
        },
        "behavior": {
            "on_disruption_report": [
                "Terima DisruptionReport dari tier agent",
                "Update agent_status[node_id] = 1",
                "Hitung global_pattern baru (tuple 5 elemen)",
                "Cocokkan global_pattern ke 18 rule (PATTERN_TO_RULE lookup)",
                "Catat active_rule dan decision ke event_log",
                "Kirim CoordinationSignal ke tier agent yang terdampak",
            ],
            "on_recovery_report": [
                "Terima RecoveryReport dari tier agent",
                "Update agent_status[node_id] = 0",
                "Hitung global_pattern baru",
                "Cocokkan ke rule → jika R1 (Not Disruption): catat recovery_time",
                "Kirim CoordinationSignal normalisasi ke tier terkait",
            ],
            "rule_matching": [
                "Input : global_pattern = (s, f, sh, w, r) — tuple 5 biner",
                "Proses: lookup PATTERN_TO_RULE dict → rule_id",
                "Output: rule_id, decision, urgency, instructions per tier",
                "Fallback: jika pola tidak ditemukan → R1 (aman)",
            ],
        },
        "messages": {
            "emit": [
                "CoordinationSignal{target_node, rule_id, decision, urgency, instructions: [{variable, operation, value, condition}]}",
            ],
            "receive": [
                "DisruptionReport{node_id, timestamp, disrupted=1, triggered_by, event_types, db_snapshot}",
                "RecoveryReport{node_id, timestamp, disrupted=0, db_snapshot}",
                "StatusUpdate{node_id, timestamp, db_snapshot}",
            ],
        },
        "rule_engine": {
            "total_rules"  : 18,
            "pattern_space": "2^5 = 32 kemungkinan, 18 tercakup",
            "uncovered"    : 14,
            "fallback"     : "R1 (Not Disruption) untuk pola yang tidak tercakup",
            "rule_list"    : [
                "R1 (0,0,0,0,0) Not Disruption",
                "R2 (1,0,0,0,0) Potential — Supplier",
                "R3 (1,1,0,0,0) Disruption — Supplier+Farm",
                "R4 (0,1,0,0,0) Potential — Farm",
                "R5 (0,1,1,0,0) Disruption — Farm+Slaughterhouse",
                "R6 (0,0,1,0,0) Potential — Slaughterhouse",
                "R7 (0,0,1,1,0) Disruption — Slaughterhouse+Wholesaler",
                "R8 (0,0,0,1,0) Potential — Wholesaler",
                "R9 (0,0,0,1,1) Disruption — Wholesaler+Retail",
                "R10(1,0,0,1,0) Disruption — Supplier+Wholesaler",
                "R11(1,1,1,0,0) Crisis — Upstream Triple",
                "R12(0,1,0,1,0) Disruption — Farm+Wholesaler",
                "R13(1,0,0,0,1) Disruption — Supplier+Retail",
                "R14(0,0,0,0,1) Potential — Retail",
                "R15(1,1,1,1,1) Crisis — Full Chain",
                "R16(1,1,1,1,0) Crisis — Upstream Quadruple",
                "R17(0,1,1,1,1) Crisis — Mid-Downstream",
                "R18(0,0,1,1,1) Disruption — Downstream Triple",
            ],
        },
        "performance_metrics": {
            "primary": [
                "Stock Availability Rate (SAR) — % waktu retail_inventory >= safety_stock",
                "Time to Recovery (TTR) — selisih waktu disruption_start ke recovery_time",
                "Stockout Duration (SOD) — total durasi stockout_flag==1",
                "Stockout Frequency (SOF) — jumlah kejadian stockout",
                "Recovery Speed Index (RSI) — 1 - (TTR / max_possible_TTR)",
            ],
            "secondary": [
                "Rule Activation Frequency — frekuensi tiap rule aktif",
                "Cascade Depth — jumlah tier yang terdampak per skenario",
                "Coordination Response Time — selisih DisruptionReport ke CoordinationSignal",
            ],
        },
    },
}


if __name__ == "__main__":
    import json
    print("=== AGENT BLUEPRINT SUMMARY ===\n")
    for agent_key, blueprint in AGENT_BLUEPRINTS.items():
        ident = blueprint["identity"]
        sense = blueprint["sensing"]
        print(f"  [{ident['agent_type']}] — {ident['agent_id']}")
        print(f"  Role     : {ident['role']}")
        print(f"  Tier     : {ident['tier']}")
        interval = sense.get('interval_hours') or sense.get('mode', 'event-driven')
        print(f"  Sensing  : {interval}")
        if "disruption_triggers" in blueprint:
            print(f"  Triggers : {blueprint['disruption_triggers']['logic']} | "
                  f"{len(blueprint['disruption_triggers']['conditions'])} conditions")
        if "recovery_conditions" in blueprint:
            print(f"  Recovery : {blueprint['recovery_conditions']['logic']} | "
                  f"{len(blueprint['recovery_conditions']['conditions'])} conditions")
        print(f"  DB vars  : {list(blueprint['local_database'].keys())}")
        print()
