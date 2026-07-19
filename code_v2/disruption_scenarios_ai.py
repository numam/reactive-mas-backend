"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 04b — AVIAN INFLUENZA DISRUPTION SCENARIOS (FINAL)            ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  5 skenario cascade — dikalibrasi data wabah AI Indonesia            ║
║                                                                      ║
║  Catatan penting:                                                    ║
║  - DB normal (CSV) dipakai sebagai initial state simulasi            ║
║  - db_changes hanya mengubah nilai spesifik saat event terjadi      ║
║  - Variabel referensi (max_capacity, planned_capacity) WAJIB         ║
║    disertakan jika diubah agar trigger rules konsisten               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

AI_OUTBREAK_SCENARIOS = [

    # ══════════════════════════════════════════════════════════════════
    # AI-01 | H5N1 LOKAL | severity=medium | cascade: Farm→Slaughter
    # Rules: R4 → R5 → R6 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"    : 1,
        "disruption_type": "AVIAN_INFLUENZA",
        "subtype"        : "H5N1_LOCAL",
        "severity"       : "medium",
        "seed_node"      : "farm",
        "description"    : "Wabah H5N1 lokal pada 2 kandang. Mortality melonjak, produksi turun 45%. Cascade ke RPH.",
        "duration_hours" : 72,
        "cascade_path"   : ["farm","slaughterhouse"],
        "recovery_path"  : ["farm","slaughterhouse"],
        "start_datetime" : "2026-03-01 06:00",
        "events": [
            {
                "event_id": "E001", "at_hour": 6,
                "timestamp": "2026-03-01 12:00",
                "node": "farm", "disrupted": 1, "event_type": "onset",
                "pattern_after": [0,1,0,0,0], "rule_triggered": "R4",
                "db_changes": {
                    # Variabel yang berubah akibat wabah
                    "mortality_rate"     : 0.12,   # > threshold 0.08 → trigger FAR-T2
                    "disease_alert"      : 1,       # trigger FAR-T4
                    "production_capacity": 440,     # 55% dari planned 800 → trigger FAR-T1
                    "planned_capacity"   : 800,     # referensi tetap
                    "outgoing_orders"    : 280,     # dikurangi sesuai kapasitas
                    "growth_status"      : "stunted",
                    "live_inventory"     : 440,
                },
                "description": "Konfirmasi H5N1 pada 2 kandang. Mortality 12%. Produksi turun ke 440 ekor (55%). Zona waspada."
            },
            {
                "event_id": "E002", "at_hour": 18,
                "timestamp": "2026-03-02 00:00",
                "node": "slaughterhouse", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [0,1,1,0,0], "rule_triggered": "R5",
                "db_changes": {
                    "processing_capacity": 230,     # 46% dari max 500 → trigger SLH-T1
                    "max_capacity"       : 500,     # referensi wajib disertakan
                    "input_inventory"    : 180,
                    "queue_length"       : 25,
                    "processing_delay"   : 3,       # < threshold 4, belum trigger
                    "output_stock"       : 140,     # 35% dari max_output 400
                    "max_output"         : 400,     # referensi wajib
                    "equipment_status"   : "operational",
                    "worker_availability": 0.88,
                },
                "description": "RPH kekurangan pasokan. Kapasitas 46%. Processing delay 3 jam. Output stock 140 kg."
            },
            {
                "event_id": "E003", "at_hour": 48,
                "timestamp": "2026-03-03 06:00",
                "node": "farm", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,1,0,0], "rule_triggered": "R6",
                "db_changes": {
                    "mortality_rate"     : 0.035,   # < recovery threshold 0.04 ✓
                    "disease_alert"      : 0,       # cleared ✓
                    "production_capacity": 650,     # 81% dari 800, > recovery 75% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 420,
                    "growth_status"      : "normal",
                    "live_inventory"     : 640,
                },
                "description": "Karantina parsial dicabut. PCR negatif. Farm 81% kapasitas. Mortality 3.5%."
            },
            {
                "event_id": "E004", "at_hour": 60,
                "timestamp": "2026-03-03 18:00",
                "node": "slaughterhouse", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                "db_changes": {
                    "processing_capacity": 460,     # 92% > recovery threshold 70% ✓
                    "max_capacity"       : 500,
                    "processing_delay"   : 0.5,     # < recovery threshold 2 ✓
                    "output_stock"       : 290,     # 73% > recovery threshold 50% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "operational",
                    "worker_availability": 0.92,    # > recovery threshold 0.80 ✓
                    "input_inventory"    : 370,
                    "queue_length"       : 48,
                },
                "description": "RPH beroperasi 92% kapasitas. Output stock 290 kg. Sistem stabil."
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # AI-02 | H5N1 MENYEBAR | severity=high | cascade: Farm→SH→WS
    # Rules: R4 → R5 → R7 → R5 → R8 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"    : 2,
        "disruption_type": "AVIAN_INFLUENZA",
        "subtype"        : "H5N1_SPREADING",
        "severity"       : "high",
        "seed_node"      : "farm",
        "description"    : "Wabah H5N1 menyebar ke 5 kandang. Depopulasi massal. Wholesaler mulai kritis. Retail terancam.",
        "duration_hours" : 96,
        "cascade_path"   : ["farm","slaughterhouse","wholesaler"],
        "recovery_path"  : ["farm","slaughterhouse","wholesaler"],
        "start_datetime" : "2026-03-10 06:00",
        "events": [
            {
                "event_id": "E001", "at_hour": 4,
                "timestamp": "2026-03-10 10:00",
                "node": "farm", "disrupted": 1, "event_type": "onset",
                "pattern_after": [0,1,0,0,0], "rule_triggered": "R4",
                "db_changes": {
                    "mortality_rate"     : 0.22,    # >> threshold 0.08 ✓
                    "disease_alert"      : 1,
                    "production_capacity": 240,     # 30% dari 800 ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 100,
                    "growth_status"      : "stunted",
                    "live_inventory"     : 240,
                    "feed_stock"         : 480,
                    "expected_daily_feed": 80,
                },
                "description": "H5N1 HPAI pada 5 kandang. Mortality 22%. Depopulasi 560 ekor. Zona merah radius 3 km."
            },
            {
                "event_id": "E002", "at_hour": 16,
                "timestamp": "2026-03-10 22:00",
                "node": "slaughterhouse", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [0,1,1,0,0], "rule_triggered": "R5",
                "db_changes": {
                    "processing_capacity": 150,     # 30% dari 500 → << threshold 50% ✓
                    "max_capacity"       : 500,
                    "input_inventory"    : 80,
                    "queue_length"       : 15,
                    "processing_delay"   : 6,       # > threshold 4 ✓
                    "output_stock"       : 90,      # 22.5% dari 400 → < threshold 30% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "partial",
                    "worker_availability": 0.80,
                },
                "description": "RPH embargo zona merah. Input 80 ekor. Kapasitas 30%. Delay 6 jam. Output 90 kg."
            },
            {
                "event_id": "E003", "at_hour": 30,
                "timestamp": "2026-03-11 12:00",
                "node": "wholesaler", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [0,1,1,1,0], "rule_triggered": "R7",
                "db_changes": {
                    "inventory_level"    : 65,      # 22% dari 300 → < threshold 30% ✓
                    "capacity"           : 300,
                    "pending_shipments"  : 72,      # > threshold 50 ✓
                    "delivery_schedule"  : "delayed",
                    "shipment_status"    : "delayed",
                    "incoming_orders"    : 210,
                    "distribution_capacity": 300,
                    "reorder_point"      : 90,
                },
                "description": "Wholesaler 65 kg (22% kapasitas). Pending 72 kg. Delivery delayed."
            },
            {
                "event_id": "E004", "at_hour": 60,
                "timestamp": "2026-03-12 18:00",
                "node": "farm", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,1,1,0], "rule_triggered": "R7",
                "db_changes": {
                    "mortality_rate"     : 0.038,   # < recovery 0.04 ✓
                    "disease_alert"      : 0,
                    "production_capacity": 620,     # 77.5% > recovery 75% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 380,
                    "growth_status"      : "normal",
                    "live_inventory"     : 610,
                },
                "description": "Depopulasi selesai. Repopulasi DOC zona hijau. Farm 77.5% kapasitas."
            },
            {
                "event_id": "E005", "at_hour": 72,
                "timestamp": "2026-03-13 06:00",
                "node": "slaughterhouse", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,1,0], "rule_triggered": "R8",
                "db_changes": {
                    "processing_capacity": 385,     # 77% > recovery 70% ✓
                    "max_capacity"       : 500,
                    "processing_delay"   : 1.5,     # < recovery 2 ✓
                    "output_stock"       : 215,     # 54% > recovery 50% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "operational",
                    "worker_availability": 0.88,    # > recovery 0.80 ✓
                    "input_inventory"    : 340,
                    "queue_length"       : 52,
                },
                "description": "Embargo dicabut. RPH 77% kapasitas. Output 215 kg."
            },
            {
                "event_id": "E006", "at_hour": 84,
                "timestamp": "2026-03-13 18:00",
                "node": "wholesaler", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                "db_changes": {
                    "inventory_level"    : 158,     # 53% > recovery 50% ✓
                    "capacity"           : 300,
                    "pending_shipments"  : 14,      # < recovery 20 ✓
                    "delivery_schedule"  : "normal",
                    "shipment_status"    : "on_time",
                    "incoming_orders"    : 148,
                    "distribution_capacity": 300,
                },
                "description": "Wholesaler 158 kg (53%). Backlog selesai. Distribusi normal."
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # AI-03 | H5N1 REGIONAL CRISIS | severity=crisis | Full chain
    # Rules: R4→R3→R11→R16→R15→R17→R18→R9→R14→R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"    : 3,
        "disruption_type": "AVIAN_INFLUENZA",
        "subtype"        : "H5N1_REGIONAL_CRISIS",
        "severity"       : "crisis",
        "seed_node"      : "farm",
        "description"    : "Wabah H5N1 regional. Cascade ke seluruh rantai. Retail stockout. Full crisis mode aktif.",
        "duration_hours" : 120,
        "cascade_path"   : ["farm","supplier","slaughterhouse","wholesaler","retail"],
        "recovery_path"  : ["supplier","farm","slaughterhouse","wholesaler","retail"],
        "start_datetime" : "2026-04-01 06:00",
        "events": [
            {
                "event_id": "E001", "at_hour": 6,
                "timestamp": "2026-04-01 12:00",
                "node": "farm", "disrupted": 1, "event_type": "onset",
                "pattern_after": [0,1,0,0,0], "rule_triggered": "R4",
                "db_changes": {
                    "mortality_rate"     : 0.35,
                    "disease_alert"      : 1,
                    "production_capacity": 120,     # 15% dari 800 ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 60,
                    "growth_status"      : "stunted",
                    "live_inventory"     : 200,
                    "feed_stock"         : 460,
                    "expected_daily_feed": 80,
                },
                "description": "HPAI H5N1 clade 2.3.4.4b. Mortality 35%. Depopulasi massal 680 ekor."
            },
            {
                "event_id": "E002", "at_hour": 14,
                "timestamp": "2026-04-01 20:00",
                "node": "supplier", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,0,0,0], "rule_triggered": "R3",
                "db_changes": {
                    "available_supply"   : 220,     # 22% dari 1000 → < threshold 30% ✓
                    "capacity"           : 1000,
                    "lead_time"          : 7,       # > threshold 4 ✓
                    "shipment_status"    : "delayed",
                    "supplier_reliability": 0.45,   # < threshold 0.60 ✓
                    "price_index"        : 1.20,
                },
                "description": "Embargo DOC regional. Supplier kehilangan 78% kapasitas. Lead time 7 hari."
            },
            {
                "event_id": "E003", "at_hour": 24,
                "timestamp": "2026-04-02 06:00",
                "node": "slaughterhouse", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,1,0,0], "rule_triggered": "R11",
                "db_changes": {
                    "processing_capacity": 80,      # 16% dari 500 ✓
                    "max_capacity"       : 500,
                    "input_inventory"    : 40,
                    "queue_length"       : 8,
                    "processing_delay"   : 10,      # >> threshold 4 ✓
                    "output_stock"       : 45,      # 11% dari 400 ✓
                    "max_output"         : 400,
                    "equipment_status"   : "partial",
                    "worker_availability": 0.55,    # < threshold 0.60 ✓
                },
                "description": "RPH ditutup Satgas AI. 45% pekerja dikarantina. Kapasitas 16%."
            },
            {
                "event_id": "E004", "at_hour": 36,
                "timestamp": "2026-04-02 18:00",
                "node": "wholesaler", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,1,1,0], "rule_triggered": "R16",
                "db_changes": {
                    "inventory_level"    : 28,      # 9% dari 300 ✓
                    "capacity"           : 300,
                    "pending_shipments"  : 95,      # >> threshold 50 ✓
                    "delivery_schedule"  : "delayed",
                    "shipment_status"    : "delayed",
                    "incoming_orders"    : 280,
                    "distribution_capacity": 300,
                    "reorder_point"      : 90,
                },
                "description": "Wholesaler hampir habis (28 kg, 9%). Panic buying: incoming 280 kg."
            },
            {
                "event_id": "E005", "at_hour": 48,
                "timestamp": "2026-04-03 06:00",
                "node": "retail", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,1,1,1], "rule_triggered": "R15",
                "db_changes": {
                    "retail_inventory"   : 4,       # << safety_stock 30 ✓
                    "capacity"           : 150,
                    "safety_stock"       : 30,
                    "stockout_flag"      : 1,       # trigger RET-T2 ✓
                    "shortage_duration"  : 5,       # > threshold 2 ✓
                    "sales_rate"         : 22,      # 220% expected → > 150% ✓
                    "expected_sales_rate": 10,
                    "reorder_request"    : 120,
                    "demand_estimate"    : 110,
                },
                "description": "Retail stockout (4 kg). Panic buying: sales 22 kg/jam. Full crisis."
            },
            {
                "event_id": "E006", "at_hour": 66,
                "timestamp": "2026-04-03 24:00",
                "node": "supplier", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,1,1,1,1], "rule_triggered": "R17",
                "db_changes": {
                    "available_supply"   : 680,     # 68% > recovery 50% ✓
                    "capacity"           : 1000,
                    "lead_time"          : 2.8,     # < recovery 3 ✓
                    "shipment_status"    : "on_time",
                    "supplier_reliability": 0.78,   # > recovery 0.75 ✓
                    "price_index"        : 1.15,    # < recovery 1.25 ✓
                },
                "description": "Jalur darurat dibuka. Embargo parsial dicabut. Supplier kirim 680 unit."
            },
            {
                "event_id": "E007", "at_hour": 78,
                "timestamp": "2026-04-04 12:00",
                "node": "farm", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,1,1,1], "rule_triggered": "R18",
                "db_changes": {
                    "mortality_rate"     : 0.038,   # < recovery 0.04 ✓
                    "disease_alert"      : 0,
                    "production_capacity": 610,     # 76% > recovery 75% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 370,
                    "growth_status"      : "normal",
                    "live_inventory"     : 600,
                    "feed_stock"         : 430,
                    "expected_daily_feed": 80,
                },
                "description": "Desinfeksi selesai. Repopulasi DOC zona hijau. Farm 76% kapasitas."
            },
            {
                "event_id": "E008", "at_hour": 90,
                "timestamp": "2026-04-05 00:00",
                "node": "slaughterhouse", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,1,1], "rule_triggered": "R9",
                "db_changes": {
                    "processing_capacity": 370,     # 74% > recovery 70% ✓
                    "max_capacity"       : 500,
                    "processing_delay"   : 1.8,     # < recovery 2 ✓
                    "output_stock"       : 210,     # 52.5% > recovery 50% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "operational",
                    "worker_availability": 0.82,    # > recovery 0.80 ✓
                    "input_inventory"    : 310,
                    "queue_length"       : 55,
                },
                "description": "RPH dibuka kembali pasca sterilisasi. Kapasitas 74%. Pekerja 82%."
            },
            {
                "event_id": "E009", "at_hour": 102,
                "timestamp": "2026-04-05 12:00",
                "node": "wholesaler", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,1], "rule_triggered": "R14",
                "db_changes": {
                    "inventory_level"    : 162,     # 54% > recovery 50% ✓
                    "capacity"           : 300,
                    "pending_shipments"  : 16,      # < recovery 20 ✓
                    "delivery_schedule"  : "normal",
                    "shipment_status"    : "on_time",
                    "incoming_orders"    : 145,
                    "distribution_capacity": 300,
                },
                "description": "Wholesaler 162 kg (54%). Distribusi ke Retail normal kembali."
            },
            {
                "event_id": "E010", "at_hour": 114,
                "timestamp": "2026-04-06 00:00",
                "node": "retail", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                "db_changes": {
                    "retail_inventory"   : 68,      # 45% > recovery 40% ✓
                    "capacity"           : 150,
                    "safety_stock"       : 30,
                    "stockout_flag"      : 0,       # cleared ✓
                    "shortage_duration"  : 0,       # cleared ✓
                    "sales_rate"         : 10.5,    # < 1.20 × 10 = 12 ✓
                    "expected_sales_rate": 10,
                    "reorder_request"    : 0,
                    "demand_estimate"    : 88,
                },
                "description": "Retail 68 kg (45%). Stockout cleared. Sistem stabil penuh."
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # AI-04 | H9N2 MILD | severity=low | Farm saja, pulih cepat
    # Rules: R4 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"    : 4,
        "disruption_type": "AVIAN_INFLUENZA",
        "subtype"        : "H9N2_MILD",
        "severity"       : "low",
        "seed_node"      : "farm",
        "description"    : "Wabah H9N2 LPAI pada 1 kandang. Mortality rendah. Tidak cascade. Pulih cepat 30 jam.",
        "duration_hours" : 48,
        "cascade_path"   : ["farm"],
        "recovery_path"  : ["farm"],
        "start_datetime" : "2026-05-15 08:00",
        "events": [
            {
                "event_id": "E001", "at_hour": 8,
                "timestamp": "2026-05-15 16:00",
                "node": "farm", "disrupted": 1, "event_type": "onset",
                "pattern_after": [0,1,0,0,0], "rule_triggered": "R4",
                "db_changes": {
                    "mortality_rate"     : 0.09,    # sedikit > threshold 0.08 ✓
                    "disease_alert"      : 1,
                    "production_capacity": 520,     # 65% dari 800 > 60% threshold
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 350,
                    "growth_status"      : "slow",
                    "live_inventory"     : 520,
                    "feed_stock"         : 470,
                    "expected_daily_feed": 80,
                },
                "description": "H9N2 LPAI pada 1 kandang. Mortality 9%. Vaksinasi darurat dilakukan."
            },
            {
                "event_id": "E002", "at_hour": 30,
                "timestamp": "2026-05-16 14:00",
                "node": "farm", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                "db_changes": {
                    "mortality_rate"     : 0.032,   # < recovery 0.04 ✓
                    "disease_alert"      : 0,
                    "production_capacity": 745,     # 93% > recovery 75% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 472,
                    "growth_status"      : "normal",
                    "live_inventory"     : 740,
                    "feed_stock"         : 448,
                    "expected_daily_feed": 80,
                },
                "description": "Vaksinasi berhasil. Mortality 3.2%. Farm 93% kapasitas. Sistem normal."
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # AI-05 | EMBARGO TRIGGERED | severity=high | Supplier→Farm→SH
    # Rules: R2 → R3 → R11 → R5 → R6 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"    : 5,
        "disruption_type": "AVIAN_INFLUENZA",
        "subtype"        : "EMBARGO_TRIGGERED",
        "severity"       : "high",
        "seed_node"      : "supplier",
        "description"    : "Embargo DOC regional. Supplier → Farm (kekurangan pakan/DOC) → RPH kekurangan pasokan.",
        "duration_hours" : 96,
        "cascade_path"   : ["supplier","farm","slaughterhouse"],
        "recovery_path"  : ["supplier","farm","slaughterhouse"],
        "start_datetime" : "2026-06-01 06:00",
        "events": [
            {
                "event_id": "E001", "at_hour": 6,
                "timestamp": "2026-06-01 12:00",
                "node": "supplier", "disrupted": 1, "event_type": "onset",
                "pattern_after": [1,0,0,0,0], "rule_triggered": "R2",
                "db_changes": {
                    "available_supply"   : 180,     # 18% dari 1000 → < threshold 30% ✓
                    "capacity"           : 1000,
                    "lead_time"          : 8,       # > threshold 4 ✓
                    "shipment_status"    : "delayed",
                    "supplier_reliability": 0.38,   # < threshold 0.60 ✓
                    "price_index"        : 1.10,
                },
                "description": "SK Embargo DOC regional. Supplier 82% kapasitas hilang. Lead time 8 hari."
            },
            {
                "event_id": "E002", "at_hour": 20,
                "timestamp": "2026-06-02 02:00",
                "node": "farm", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,0,0,0], "rule_triggered": "R3",
                "db_changes": {
                    "mortality_rate"     : 0.025,   # normal, tapi produksi drop karena DOC
                    "disease_alert"      : 0,
                    "production_capacity": 380,     # 47.5% dari 800 → < threshold 60% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 220,
                    "growth_status"      : "slow",
                    "live_inventory"     : 380,
                    "feed_stock"         : 185,     # 185/80 = 2.3 hari → < threshold 3 hari ✓
                    "expected_daily_feed": 80,
                },
                "description": "Farm tidak bisa repopulasi DOC. Produksi 47.5%. Pakan kritis (2.3 hari)."
            },
            {
                "event_id": "E003", "at_hour": 34,
                "timestamp": "2026-06-02 16:00",
                "node": "slaughterhouse", "disrupted": 1, "event_type": "escalation",
                "pattern_after": [1,1,1,0,0], "rule_triggered": "R11",
                "db_changes": {
                    "processing_capacity": 190,     # 38% dari 500 → < threshold 50% ✓
                    "max_capacity"       : 500,
                    "input_inventory"    : 150,
                    "queue_length"       : 22,
                    "processing_delay"   : 5,       # > threshold 4 ✓
                    "output_stock"       : 115,     # 28.75% dari 400 → < threshold 30% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "operational",
                    "worker_availability": 0.88,
                },
                "description": "Pasokan Farm menurun. RPH 38% kapasitas. Delay 5 jam. Output 115 kg."
            },
            {
                "event_id": "E004", "at_hour": 58,
                "timestamp": "2026-06-03 16:00",
                "node": "supplier", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,1,1,0,0], "rule_triggered": "R5",
                "db_changes": {
                    "available_supply"   : 720,     # 72% > recovery 50% ✓
                    "capacity"           : 1000,
                    "lead_time"          : 2.5,     # < recovery 3 ✓
                    "shipment_status"    : "on_time",
                    "supplier_reliability": 0.82,   # > recovery 0.75 ✓
                    "price_index"        : 1.05,    # < recovery 1.25 ✓
                },
                "description": "PTUN batalkan SK embargo. Distribusi DOC dari provinsi lain diizinkan."
            },
            {
                "event_id": "E005", "at_hour": 72,
                "timestamp": "2026-06-04 06:00",
                "node": "farm", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,1,0,0], "rule_triggered": "R6",
                "db_changes": {
                    "mortality_rate"     : 0.024,
                    "disease_alert"      : 0,
                    "production_capacity": 660,     # 82.5% > recovery 75% ✓
                    "planned_capacity"   : 800,
                    "outgoing_orders"    : 420,
                    "growth_status"      : "normal",
                    "live_inventory"     : 650,
                    "feed_stock"         : 425,     # 425/80 = 5.3 hari > recovery 5 hari ✓
                    "expected_daily_feed": 80,
                },
                "description": "DOC baru tiba. Repopulasi dimulai. Farm 82.5% kapasitas. Pakan 5.3 hari."
            },
            {
                "event_id": "E006", "at_hour": 84,
                "timestamp": "2026-06-04 18:00",
                "node": "slaughterhouse", "disrupted": 0, "event_type": "recovery",
                "pattern_after": [0,0,0,0,0], "rule_triggered": "R1",
                "db_changes": {
                    "processing_capacity": 380,     # 76% > recovery 70% ✓
                    "max_capacity"       : 500,
                    "processing_delay"   : 1.2,     # < recovery 2 ✓
                    "output_stock"       : 215,     # 53.75% > recovery 50% ✓
                    "max_output"         : 400,
                    "equipment_status"   : "operational",
                    "worker_availability": 0.90,    # > recovery 0.80 ✓
                    "input_inventory"    : 345,
                    "queue_length"       : 46,
                },
                "description": "RPH 76% kapasitas. Output 215 kg. Sistem rantai pasok stabil."
            },
        ],
    },
]


def get_ai_scenario(scenario_id: int) -> dict | None:
    for s in AI_OUTBREAK_SCENARIOS:
        if s["scenario_id"] == scenario_id:
            return s
    return None


def get_disruption_schedule(scenario_id: int) -> list[dict]:
    """Konversi ke format disruption_schedule untuk run_scenario()."""
    scenario = get_ai_scenario(scenario_id)
    if not scenario:
        return []
    return [
        {
            "at_hour"    : e["at_hour"],
            "node"       : e["node"],
            "disrupted"  : e["disrupted"],
            "db_changes" : e.get("db_changes", {}),
            "description": e.get("description", ""),
            "event_id"   : e.get("event_id", ""),
        }
        for e in scenario["events"]
    ]


if __name__ == "__main__":
    print("=== AVIAN INFLUENZA DISRUPTION SCENARIOS ===\n")
    for s in AI_OUTBREAK_SCENARIOS:
        n_onset    = sum(1 for e in s["events"] if e["disrupted"] == 1)
        n_recovery = sum(1 for e in s["events"] if e["disrupted"] == 0)
        print(f"  AI-{s['scenario_id']:02d} | {s['subtype']:<25} | "
              f"severity={s['severity']:<7} | {s['duration_hours']}h | "
              f"onset={n_onset} recovery={n_recovery}")
        print(f"    Cascade : {' → '.join(s['cascade_path'])}")
        print(f"    {s['description'][:88]}")
        print()
