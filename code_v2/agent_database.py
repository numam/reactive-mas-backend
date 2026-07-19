"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 01 — AGENT DATABASE SCHEMA (FINAL)                            ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  1 node per tier | Python | Expandable                              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

AGENT_DATABASE = {

    "supplier": {
        "meta": {
            "node_id"                  : "supplier_1",
            "description"              : "Pemasok bahan baku (DOC, pakan, obat-obatan)",
            "monitoring_interval_hours": 18,
            "change_character"         : "Lambat, strategis",
        },
        "variables": {
            "available_supply"    : {"default": 1000, "unit": "unit",    "description": "Stok bahan baku tersedia"},
            "capacity"            : {"default": 1000, "unit": "unit",    "description": "Kapasitas produksi/penyimpanan maksimum"},
            "lead_time"           : {"default": 2,    "unit": "hari",    "description": "Waktu pengiriman ke Farm"},
            "shipment_status"     : {"default": "on_time", "unit": "-",  "description": "Status pengiriman: on_time/delayed/cancelled"},
            "price_index"         : {"default": 1.0,  "unit": "ratio",   "description": "Indeks harga bahan baku (1.0=normal)"},
            "supplier_reliability": {"default": 1.0,  "unit": "ratio",   "description": "Keandalan pemasok (0.0–1.0)"},
        },
        "thresholds": {
            "disruption": {
                "available_supply_min_ratio": 0.30,
                "lead_time_max"             : 4,
                "price_index_max"           : 1.50,
                "reliability_min"           : 0.60,
            },
            "recovery": {
                "available_supply_min_ratio": 0.50,
                "lead_time_max"             : 3,
                "price_index_max"           : 1.25,
                "reliability_min"           : 0.75,
            },
        },
    },

    "farm": {
        "meta": {
            "node_id"                  : "farm_1",
            "description"              : "Peternakan ayam broiler",
            "monitoring_interval_hours": 9,
            "change_character"         : "Biologis, dinamis",
        },
        "variables": {
            "live_inventory"      : {"default": 800,      "unit": "ekor",  "description": "Jumlah ayam hidup siap panen"},
            "production_capacity" : {"default": 800,      "unit": "ekor",  "description": "Kapasitas produksi aktual"},
            "planned_capacity"    : {"default": 800,      "unit": "ekor",  "description": "Target produksi yang direncanakan"},
            "growth_status"       : {"default": "normal", "unit": "-",     "description": "Status pertumbuhan: normal/slow/stunted"},
            "mortality_rate"      : {"default": 0.02,     "unit": "ratio", "description": "Tingkat kematian per periode (normal <5%)"},
            "outgoing_orders"     : {"default": 500,      "unit": "ekor",  "description": "Order keluar ke Slaughterhouse"},
            "feed_stock"          : {"default": 500,      "unit": "kg",    "description": "Stok pakan tersedia"},
            "expected_daily_feed" : {"default": 80,       "unit": "kg",    "description": "Kebutuhan pakan harian normal"},
            "disease_alert"       : {"default": 0,        "unit": "bool",  "description": "Flag alert penyakit: 0=aman, 1=waspada"},
        },
        "thresholds": {
            "disruption": {
                "production_ratio_min" : 0.60,
                "mortality_rate_max"   : 0.08,
                "feed_stock_min_days"  : 3,
                "disease_alert_trigger": 1,
            },
            "recovery": {
                "production_ratio_min" : 0.75,
                "mortality_rate_max"   : 0.04,
                "feed_stock_min_days"  : 5,
                "disease_alert_trigger": 0,
            },
        },
    },

    "slaughterhouse": {
        "meta": {
            "node_id"                  : "slaughterhouse_1",
            "description"              : "Rumah Potong Hewan (RPH)",
            "monitoring_interval_hours": 3,
            "change_character"         : "Operasional, time-sensitive",
        },
        "variables": {
            "input_inventory"    : {"default": 400,           "unit": "ekor",  "description": "Ayam masuk dari Farm yang antri"},
            "processing_capacity": {"default": 500,           "unit": "ekor",  "description": "Kapasitas pemotongan aktual per periode"},
            "max_capacity"       : {"default": 500,           "unit": "ekor",  "description": "Kapasitas pemotongan maksimum normal"},
            "queue_length"       : {"default": 50,            "unit": "ekor",  "description": "Antrian ayam menunggu proses"},
            "processing_delay"   : {"default": 0,             "unit": "jam",   "description": "Keterlambatan proses dari jadwal normal"},
            "output_stock"       : {"default": 300,           "unit": "kg",    "description": "Stok produk jadi (karkas/potongan)"},
            "max_output"         : {"default": 400,           "unit": "kg",    "description": "Output maksimum normal per periode"},
            "equipment_status"   : {"default": "operational", "unit": "-",     "description": "Status mesin: operational/partial/down"},
            "hygiene_compliance" : {"default": 1.0,           "unit": "ratio", "description": "Tingkat kepatuhan sanitasi (0.0–1.0)"},
            "worker_availability": {"default": 1.0,           "unit": "ratio", "description": "Ketersediaan tenaga kerja relatif normal"},
        },
        "thresholds": {
            "disruption": {
                "capacity_ratio_min"    : 0.50,
                "queue_max"             : 100,
                "processing_delay_max"  : 4,
                "output_stock_min_ratio": 0.30,
                "worker_min"            : 0.60,
            },
            "recovery": {
                "capacity_ratio_min"    : 0.70,
                "queue_max"             : 70,
                "processing_delay_max"  : 2,
                "output_stock_min_ratio": 0.50,
                "worker_min"            : 0.80,
            },
        },
    },

    "wholesaler": {
        "meta": {
            "node_id"                  : "wholesaler_1",
            "description"              : "Pedagang besar / distributor utama",
            "monitoring_interval_hours": 2,
            "change_character"         : "Time-sensitive, distribusi kritis",
        },
        "variables": {
            "inventory_level"     : {"default": 200,       "unit": "kg",  "description": "Stok produk tersedia di gudang"},
            "capacity"            : {"default": 300,       "unit": "kg",  "description": "Kapasitas gudang maksimum"},
            "reorder_point"       : {"default": 90,        "unit": "kg",  "description": "Titik reorder (30% kapasitas)"},
            "shipment_status"     : {"default": "on_time", "unit": "-",   "description": "Status pengiriman: on_time/delayed/cancelled"},
            "distribution_capacity":{"default": 300,       "unit": "kg",  "description": "Kapasitas distribusi per periode"},
            "pending_shipments"   : {"default": 0,         "unit": "kg",  "description": "Volume pengiriman tertunda"},
            "delivery_schedule"   : {"default": "normal",  "unit": "-",   "description": "Jadwal pengiriman: normal/delayed/rerouted"},
            "incoming_orders"     : {"default": 150,       "unit": "kg",  "description": "Total order masuk dari Retail"},
        },
        "thresholds": {
            "disruption": {
                "inventory_min_ratio"  : 0.30,
                "pending_shipments_max": 50,
                "order_capacity_ratio" : 1.20,
            },
            "recovery": {
                "inventory_min_ratio"  : 0.50,
                "pending_shipments_max": 20,
                "order_capacity_ratio" : 1.00,
            },
        },
    },

    "retail": {
        "meta": {
            "node_id"                  : "retail_1",
            "description"              : "Pengecer (pasar tradisional, supermarket, dll)",
            "monitoring_interval_hours": 0.75,
            "change_character"         : "Sangat fluktuatif, demand-driven",
        },
        "variables": {
            "retail_inventory"   : {"default": 90,  "unit": "kg",     "description": "Stok produk di rak/display"},
            "capacity"           : {"default": 150, "unit": "kg",     "description": "Kapasitas penyimpanan maksimum"},
            "safety_stock"       : {"default": 30,  "unit": "kg",     "description": "Stok minimum aman (20% kapasitas)"},
            "sales_rate"         : {"default": 10,  "unit": "kg/jam", "description": "Laju penjualan aktual"},
            "expected_sales_rate": {"default": 10,  "unit": "kg/jam", "description": "Laju penjualan ekspektasi normal"},
            "shortage_duration"  : {"default": 0,   "unit": "jam",    "description": "Durasi kekurangan stok berlangsung"},
            "demand_estimate"    : {"default": 90,  "unit": "kg",     "description": "Estimasi kebutuhan per periode"},
            "reorder_request"    : {"default": 0,   "unit": "kg",     "description": "Volume reorder dikirim ke Wholesaler"},
            "stockout_flag"      : {"default": 0,   "unit": "bool",   "description": "Flag stok habis: 1=stockout, 0=tersedia"},
        },
        "thresholds": {
            "disruption": {
                "inventory_min_ratio"   : 0.20,
                "safety_stock_breach"   : True,
                "sales_rate_surge_ratio": 1.50,
                "shortage_duration_max" : 2,
                "stockout_trigger"      : 1,
            },
            "recovery": {
                "inventory_min_ratio"   : 0.40,
                "sales_rate_surge_ratio": 1.20,
                "shortage_duration_max" : 0,
                "stockout_trigger"      : 0,
            },
        },
    },
}


def init_node_state(node_type: str, overrides: dict = None) -> dict:
    schema = AGENT_DATABASE[node_type]["variables"]
    state  = {k: v["default"] for k, v in schema.items()}
    if overrides:
        state.update(overrides)
    return state


def get_monitoring_interval(node_type: str) -> float:
    return AGENT_DATABASE[node_type]["meta"]["monitoring_interval_hours"]


def get_node_id(node_type: str) -> str:
    return AGENT_DATABASE[node_type]["meta"]["node_id"]


if __name__ == "__main__":
    print("=== AGENT DATABASE SCHEMA (FINAL) ===\n")
    for node, schema in AGENT_DATABASE.items():
        print(f"[{node.upper()}] {schema['meta']['node_id']}")
        print(f"  Interval : {schema['meta']['monitoring_interval_hours']} jam")
        print(f"  Variables: {list(schema['variables'].keys())}")
        print(f"  Disruption thresholds: {schema['thresholds']['disruption']}")
        print(f"  Recovery thresholds  : {schema['thresholds']['recovery']}")
        print()
