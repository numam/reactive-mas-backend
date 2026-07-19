"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 04 — DISRUPTION SCENARIOS                                      ║
║  MAS Poultry Supply Chain                                            ║
║  Contoh skenario disrupsi cascade yang valid (18 pola rule)          ║
║  Setiap skenario: onset bertahap → eskalasi → recovery               ║
╚══════════════════════════════════════════════════════════════════════╝

Format event:
  at_hour   : jam sejak simulasi dimulai (float)
  node      : nama node yang berubah status
  disrupted : 0 (pulih) atau 1 (terdisrupsi)
  event_type: onset / escalation / recovery
  pattern_after: pola biner setelah event ini
  rule_triggered: rule ID yang aktif setelah event
  description : deskripsi realistis kejadian
"""

DISRUPTION_SCENARIOS = [

    # ══════════════════════════════════════════════════════════════════
    # SKENARIO 1 — DISEASE (Wabah Avian Influenza di Farm)
    # Cascade: Farm → Slaughterhouse → recovery bertahap
    # Rules aktif: R4 → R5 → R6 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"   : 1,
        "disruption_type": "DISEASE",
        "severity"      : "high",
        "seed_node"     : "farm",
        "description"   : "Wabah Avian Influenza H5N1 menyerang Farm, menyebabkan penurunan produksi drastis yang berdampak ke Slaughterhouse.",
        "duration_hours": 72,
        "cascade_path"  : ["farm", "slaughterhouse"],
        "recovery_path" : ["farm", "slaughterhouse"],
        "start_datetime": "2026-01-28 06:00",
        "events": [
            {
                "event_id"     : "E001",
                "at_hour"      : 6,
                "timestamp"    : "2026-01-28 12:00",
                "node"         : "farm",
                "disrupted"    : 1,
                "event_type"   : "onset",
                "pattern_after": [0, 1, 0, 0, 0],
                "rule_triggered": "R4",
                "db_changes"   : {"mortality_rate": 0.12, "disease_alert": 1, "production_capacity": 320},
                "description"  : "Ditemukan kasus AI H5N1 pada 3 kandang. Mortality rate melonjak ke 12%. Produksi turun ke 320 ekor (40% dari rencana).",
            },
            {
                "event_id"     : "E002",
                "at_hour"      : 18,
                "timestamp"    : "2026-01-29 00:00",
                "node"         : "slaughterhouse",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [0, 1, 1, 0, 0],
                "rule_triggered": "R5",
                "db_changes"   : {"processing_capacity": 200, "queue_length": 20, "processing_delay": 6},
                "description"  : "Pasokan ayam dari Farm turun drastis. RPH hanya beroperasi 40% kapasitas. Processing delay bertambah 6 jam.",
            },
            {
                "event_id"     : "E003",
                "at_hour"      : 48,
                "timestamp"    : "2026-01-30 06:00",
                "node"         : "farm",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 1, 0, 0],
                "rule_triggered": "R6",
                "db_changes"   : {"mortality_rate": 0.03, "disease_alert": 0, "production_capacity": 700},
                "description"  : "Karantina dicabut. Hasil uji negatif. Produksi Farm pulih ke 700 ekor (87%).",
            },
            {
                "event_id"     : "E004",
                "at_hour"      : 60,
                "timestamp"    : "2026-01-30 18:00",
                "node"         : "slaughterhouse",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 0],
                "rule_triggered": "R1",
                "db_changes"   : {"processing_capacity": 500, "processing_delay": 0, "queue_length": 50},
                "description"  : "Pasokan dari Farm kembali normal. RPH beroperasi penuh. Sistem stabil.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # SKENARIO 2 — LOGISTICS (Gangguan Logistik Wholesaler ke Retail)
    # Cascade: Wholesaler → Retail → recovery bertahap
    # Rules aktif: R8 → R9 → R14 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"   : 2,
        "disruption_type": "LOGISTICS",
        "severity"      : "medium",
        "seed_node"     : "wholesaler",
        "description"   : "Gangguan jalan akibat banjir menghalangi distribusi dari Wholesaler ke Retail, menyebabkan kekurangan stok di Retail.",
        "duration_hours": 48,
        "cascade_path"  : ["wholesaler", "retail"],
        "recovery_path" : ["wholesaler", "retail"],
        "start_datetime": "2026-02-03 08:00",
        "events": [
            {
                "event_id"     : "E001",
                "at_hour"      : 4,
                "timestamp"    : "2026-02-03 12:00",
                "node"         : "wholesaler",
                "disrupted"    : 1,
                "event_type"   : "onset",
                "pattern_after": [0, 0, 0, 1, 0],
                "rule_triggered": "R8",
                "db_changes"   : {"delivery_schedule": "delayed", "pending_shipments": 80},
                "description"  : "Banjir memutus akses jalan utama distribusi. Pending shipments menumpuk hingga 80 kg. Delivery schedule delayed.",
            },
            {
                "event_id"     : "E002",
                "at_hour"      : 10,
                "timestamp"    : "2026-02-03 18:00",
                "node"         : "retail",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [0, 0, 0, 1, 1],
                "rule_triggered": "R9",
                "db_changes"   : {"retail_inventory": 20, "shortage_duration": 3, "stockout_flag": 0},
                "description"  : "Stok Retail turun ke 20 kg, di bawah safety stock 30 kg. Shortage sudah berlangsung 3 jam.",
            },
            {
                "event_id"     : "E003",
                "at_hour"      : 28,
                "timestamp"    : "2026-02-04 12:00",
                "node"         : "wholesaler",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 1],
                "rule_triggered": "R14",
                "db_changes"   : {"delivery_schedule": "normal", "pending_shipments": 10},
                "description"  : "Jalan alternatif dibuka. Wholesaler melanjutkan pengiriman. Backlog mulai berkurang.",
            },
            {
                "event_id"     : "E004",
                "at_hour"      : 36,
                "timestamp"    : "2026-02-04 20:00",
                "node"         : "retail",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 0],
                "rule_triggered": "R1",
                "db_changes"   : {"retail_inventory": 75, "shortage_duration": 0, "stockout_flag": 0},
                "description"  : "Stok Retail terisi kembali ke 75 kg. Sistem kembali normal.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # SKENARIO 3 — PRICE SHOCK (Kenaikan Harga Pakan di Supplier)
    # Cascade: Supplier → (Wholesaler lateral) → recovery
    # Rules aktif: R2 → R10 → R2 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"   : 3,
        "disruption_type": "PRICE",
        "severity"      : "medium",
        "seed_node"     : "supplier",
        "description"   : "Kenaikan harga jagung global menyebabkan price_index bahan baku naik drastis di Supplier, berdampak ke tekanan distribusi Wholesaler.",
        "duration_hours": 60,
        "cascade_path"  : ["supplier", "wholesaler"],
        "recovery_path" : ["wholesaler", "supplier"],
        "start_datetime": "2026-02-10 06:00",
        "events": [
            {
                "event_id"     : "E001",
                "at_hour"      : 6,
                "timestamp"    : "2026-02-10 12:00",
                "node"         : "supplier",
                "disrupted"    : 1,
                "event_type"   : "onset",
                "pattern_after": [1, 0, 0, 0, 0],
                "rule_triggered": "R2",
                "db_changes"   : {"price_index": 1.75, "available_supply": 600, "lead_time": 3},
                "description"  : "Harga jagung naik 75% dari normal. Price index mencapai 1.75. Supplier mengurangi pasokan ke 600 unit.",
            },
            {
                "event_id"     : "E002",
                "at_hour"      : 18,
                "timestamp"    : "2026-02-11 00:00",
                "node"         : "wholesaler",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [1, 0, 0, 1, 0],
                "rule_triggered": "R10",
                "db_changes"   : {"inventory_level": 70, "pending_shipments": 60, "delivery_schedule": "delayed"},
                "description"  : "Tekanan harga mempengaruhi volume pasokan ke Wholesaler. Inventory turun ke 70 kg. Pending shipments 60 kg.",
            },
            {
                "event_id"     : "E003",
                "at_hour"      : 36,
                "timestamp"    : "2026-02-11 18:00",
                "node"         : "wholesaler",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [1, 0, 0, 0, 0],
                "rule_triggered": "R2",
                "db_changes"   : {"inventory_level": 120, "pending_shipments": 15, "delivery_schedule": "normal"},
                "description"  : "Wholesaler berhasil mengamankan pasokan alternatif. Inventory pulih ke 120 kg.",
            },
            {
                "event_id"     : "E004",
                "at_hour"      : 54,
                "timestamp"    : "2026-02-12 12:00",
                "node"         : "supplier",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 0],
                "rule_triggered": "R1",
                "db_changes"   : {"price_index": 1.15, "available_supply": 900, "lead_time": 2},
                "description"  : "Harga bahan baku mulai stabil (price_index turun ke 1.15). Pasokan Supplier kembali normal.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # SKENARIO 4 — COMBINED / CRISIS (Full Chain Disruption)
    # Cascade: Supplier → Farm → Slaughterhouse → Wholesaler → Retail
    # Rules aktif: R2→R3→R11→R16→R15→R16→R11→R3→R2→R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"   : 4,
        "disruption_type": "COMBINED",
        "severity"      : "crisis",
        "seed_node"     : "supplier",
        "description"   : "Kombinasi wabah penyakit dan gangguan logistik menyebabkan disrupsi menyeluruh pada seluruh rantai pasok selama 96 jam.",
        "duration_hours": 96,
        "cascade_path"  : ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"],
        "recovery_path" : ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"],
        "start_datetime": "2026-02-15 06:00",
        "events": [
            {
                "event_id"     : "E001",
                "at_hour"      : 6,
                "timestamp"    : "2026-02-15 12:00",
                "node"         : "supplier",
                "disrupted"    : 1,
                "event_type"   : "onset",
                "pattern_after": [1, 0, 0, 0, 0],
                "rule_triggered": "R2",
                "db_changes"   : {"available_supply": 250, "lead_time": 6, "shipment_status": "delayed"},
                "description"  : "Gangguan transportasi menghambat pengiriman bahan baku. Lead time melonjak ke 6 hari. Stok Supplier tinggal 250 unit.",
            },
            {
                "event_id"     : "E002",
                "at_hour"      : 18,
                "timestamp"    : "2026-02-16 00:00",
                "node"         : "farm",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [1, 1, 0, 0, 0],
                "rule_triggered": "R3",
                "db_changes"   : {"feed_stock": 150, "production_capacity": 400, "disease_alert": 1},
                "description"  : "Kekurangan pakan akibat gangguan Supplier. Stok pakan tersisa untuk 1.8 hari. Disease alert aktif karena stress nutrisi.",
            },
            {
                "event_id"     : "E003",
                "at_hour"      : 30,
                "timestamp"    : "2026-02-16 12:00",
                "node"         : "slaughterhouse",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [1, 1, 1, 0, 0],
                "rule_triggered": "R11",
                "db_changes"   : {"processing_capacity": 180, "equipment_status": "partial", "processing_delay": 8},
                "description"  : "Pasokan ayam dari Farm turun drastis + gangguan peralatan. Kapasitas RPH turun ke 36%. Processing delay 8 jam.",
            },
            {
                "event_id"     : "E004",
                "at_hour"      : 42,
                "timestamp"    : "2026-02-17 00:00",
                "node"         : "wholesaler",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [1, 1, 1, 1, 0],
                "rule_triggered": "R16",
                "db_changes"   : {"inventory_level": 50, "pending_shipments": 90, "delivery_schedule": "delayed"},
                "description"  : "Stok Wholesaler tinggal 50 kg (17% kapasitas). Pending shipments 90 kg. Delivery schedule delayed.",
            },
            {
                "event_id"     : "E005",
                "at_hour"      : 50,
                "timestamp"    : "2026-02-17 08:00",
                "node"         : "retail",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [1, 1, 1, 1, 1],
                "rule_triggered": "R15",
                "db_changes"   : {"retail_inventory": 10, "stockout_flag": 1, "shortage_duration": 4},
                "description"  : "Stok Retail habis (10 kg, stockout_flag=1). Shortage sudah 4 jam. Full crisis mode aktif.",
            },
            {
                "event_id"     : "E006",
                "at_hour"      : 60,
                "timestamp"    : "2026-02-17 18:00",
                "node"         : "supplier",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 1, 1, 1, 1],
                "rule_triggered": "R17",
                "db_changes"   : {"available_supply": 800, "lead_time": 2, "shipment_status": "on_time"},
                "description"  : "Jalur transportasi Supplier pulih. Pengiriman bahan baku dilanjutkan. Stok Supplier 800 unit.",
            },
            {
                "event_id"     : "E007",
                "at_hour"      : 70,
                "timestamp"    : "2026-02-18 04:00",
                "node"         : "farm",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 1, 1, 1],
                "rule_triggered": "R18",
                "db_changes"   : {"feed_stock": 400, "production_capacity": 650, "disease_alert": 0},
                "description"  : "Pasokan pakan dari Supplier tiba. Production capacity Farm pulih ke 650 ekor (81%).",
            },
            {
                "event_id"     : "E008",
                "at_hour"      : 78,
                "timestamp"    : "2026-02-18 12:00",
                "node"         : "slaughterhouse",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 1, 1],
                "rule_triggered": "R9",
                "db_changes"   : {"processing_capacity": 450, "equipment_status": "operational", "processing_delay": 1},
                "description"  : "Perbaikan peralatan selesai. RPH beroperasi 90% kapasitas. Processing delay turun ke 1 jam.",
            },
            {
                "event_id"     : "E009",
                "at_hour"      : 84,
                "timestamp"    : "2026-02-18 18:00",
                "node"         : "wholesaler",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 1],
                "rule_triggered": "R14",
                "db_changes"   : {"inventory_level": 180, "pending_shipments": 5, "delivery_schedule": "normal"},
                "description"  : "Stok Wholesaler terisi kembali ke 180 kg. Pengiriman ke Retail dilanjutkan normal.",
            },
            {
                "event_id"     : "E010",
                "at_hour"      : 90,
                "timestamp"    : "2026-02-19 00:00",
                "node"         : "retail",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 0],
                "rule_triggered": "R1",
                "db_changes"   : {"retail_inventory": 80, "stockout_flag": 0, "shortage_duration": 0},
                "description"  : "Stok Retail pulih ke 80 kg. Stockout flag cleared. Sistem kembali stabil penuh.",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # SKENARIO 5 — DEMAND SURGE (Lonjakan Permintaan Retail)
    # Cascade: Retail → Wholesaler → recovery
    # Rules aktif: R14 → R9 → R8 → R1
    # ══════════════════════════════════════════════════════════════════
    {
        "scenario_id"   : 5,
        "disruption_type": "DEMAND",
        "severity"      : "medium",
        "seed_node"     : "retail",
        "description"   : "Lonjakan permintaan menjelang Hari Raya menyebabkan stok Retail habis cepat dan Wholesaler kewalahan memenuhi reorder.",
        "duration_hours": 48,
        "cascade_path"  : ["retail", "wholesaler"],
        "recovery_path" : ["wholesaler", "retail"],
        "start_datetime": "2026-03-25 06:00",
        "events": [
            {
                "event_id"     : "E001",
                "at_hour"      : 4,
                "timestamp"    : "2026-03-25 10:00",
                "node"         : "retail",
                "disrupted"    : 1,
                "event_type"   : "onset",
                "pattern_after": [0, 0, 0, 0, 1],
                "rule_triggered": "R14",
                "db_changes"   : {"sales_rate": 18, "expected_sales_rate": 10, "retail_inventory": 25, "shortage_duration": 2.5},
                "description"  : "Permintaan melonjak 180% dari normal menjelang Hari Raya. Stok Retail turun ke 25 kg dalam 4 jam.",
            },
            {
                "event_id"     : "E002",
                "at_hour"      : 10,
                "timestamp"    : "2026-03-25 16:00",
                "node"         : "wholesaler",
                "disrupted"    : 1,
                "event_type"   : "escalation",
                "pattern_after": [0, 0, 0, 1, 1],
                "rule_triggered": "R9",
                "db_changes"   : {"incoming_orders": 400, "distribution_capacity": 300, "inventory_level": 85, "pending_shipments": 55},
                "description"  : "Reorder dari Retail melonjak. Incoming orders 400 kg melebihi kapasitas 300 kg. Pending shipments 55 kg.",
            },
            {
                "event_id"     : "E003",
                "at_hour"      : 28,
                "timestamp"    : "2026-03-26 10:00",
                "node"         : "wholesaler",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 1],
                "rule_triggered": "R14",
                "db_changes"   : {"inventory_level": 150, "pending_shipments": 10, "incoming_orders": 180},
                "description"  : "Wholesaler mendapat pasokan tambahan darurat. Inventory 150 kg. Backlog terselesaikan.",
            },
            {
                "event_id"     : "E004",
                "at_hour"      : 38,
                "timestamp"    : "2026-03-26 20:00",
                "node"         : "retail",
                "disrupted"    : 0,
                "event_type"   : "recovery",
                "pattern_after": [0, 0, 0, 0, 0],
                "rule_triggered": "R1",
                "db_changes"   : {"retail_inventory": 70, "sales_rate": 12, "shortage_duration": 0},
                "description"  : "Stok Retail terisi kembali ke 70 kg. Sales rate mulai normal. Sistem stabil.",
            },
        ],
    },
]


def get_scenario(scenario_id: int) -> dict | None:
    """Ambil satu skenario berdasarkan ID."""
    for s in DISRUPTION_SCENARIOS:
        if s["scenario_id"] == scenario_id:
            return s
    return None


def get_disruption_schedule(scenario_id: int) -> list[dict]:
    """
    Konversi skenario ke format disruption_schedule
    yang siap digunakan oleh fungsi run_simulation().
    """
    scenario = get_scenario(scenario_id)
    if not scenario:
        return []
    return [
        {
            "at_hour"    : e["at_hour"],
            "node"       : e["node"],
            "disrupted"  : e["disrupted"],
            "description": e["description"],
        }
        for e in scenario["events"]
    ]


if __name__ == "__main__":
    print("=== DISRUPTION SCENARIOS ===\n")
    for s in DISRUPTION_SCENARIOS:
        print(f"  Scenario {s['scenario_id']:02d} | {s['disruption_type']:<10} | "
              f"Severity: {s['severity']:<7} | Seed: {s['seed_node']:<15} | "
              f"Duration: {s['duration_hours']}h")
        print(f"    Cascade : {' → '.join(s['cascade_path'])}")
        print(f"    Recovery: {' → '.join(s['recovery_path'])}")
        print(f"    Events  : {len(s['events'])} events")
        print()
