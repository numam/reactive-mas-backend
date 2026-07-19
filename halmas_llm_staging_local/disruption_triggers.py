"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 02 — DISRUPTION TRIGGER RULES (FINAL)                         ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  Logic OR: salah satu terpenuhi → disrupted=1                       ║
║  Recovery: semua kondisi recovery terpenuhi → disrupted=0           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

DISRUPTION_TRIGGERS = {

    "supplier": {
        "logic"      : "OR",
        "description": "Supplier terganggu jika salah satu kondisi berikut terpenuhi",
        "onset": [
            {
                "condition_id": "SUP-T1",
                "variable"    : "available_supply",
                "operator"    : "<",
                "threshold"   : "capacity * 0.30",
                "event_type"  : "STOCK_SHORTAGE",
                "description" : "IF available_supply < 30% capacity → stok kritis",
            },
            {
                "condition_id": "SUP-T2",
                "variable"    : "lead_time",
                "operator"    : ">",
                "threshold"   : 4,
                "event_type"  : "DELIVERY_DELAY",
                "description" : "IF lead_time > 4 hari → pengiriman terlambat",
            },
            {
                "condition_id": "SUP-T3",
                "variable"    : "price_index",
                "operator"    : ">",
                "threshold"   : 1.50,
                "event_type"  : "PRICE_SHOCK",
                "description" : "IF price_index > 1.50 → harga naik >50% dari normal",
            },
            {
                "condition_id": "SUP-T4",
                "variable"    : "supplier_reliability",
                "operator"    : "<",
                "threshold"   : 0.60,
                "event_type"  : "RELIABILITY_DROP",
                "description" : "IF reliability < 0.60 → keandalan di bawah 60%",
            },
            {
                "condition_id": "SUP-T5",
                "variable"    : "shipment_status",
                "operator"    : "==",
                "threshold"   : "cancelled",
                "event_type"  : "SHIPMENT_CANCELLED",
                "description" : "IF shipment_status == cancelled → pengiriman dibatalkan",
            },
        ],
        "recovery": [
            {
                "condition_id": "SUP-R1",
                "variable"    : "available_supply",
                "operator"    : ">=",
                "threshold"   : "capacity * 0.50",
                "description" : "Stok kembali ≥ 50% kapasitas",
            },
            {
                "condition_id": "SUP-R2",
                "variable"    : "lead_time",
                "operator"    : "<=",
                "threshold"   : 3,
                "description" : "Lead time kembali ≤ 3 hari",
            },
            {
                "condition_id": "SUP-R3",
                "variable"    : "price_index",
                "operator"    : "<=",
                "threshold"   : 1.25,
                "description" : "Price index turun ≤ 1.25",
            },
        ],
    },

    "farm": {
        "logic"      : "OR",
        "description": "Farm terganggu jika salah satu kondisi berikut terpenuhi",
        "onset": [
            {
                "condition_id": "FAR-T1",
                "variable"    : "production_capacity",
                "operator"    : "<",
                "threshold"   : "planned_capacity * 0.60",
                "event_type"  : "PRODUCTION_DROP",
                "description" : "IF production_capacity < 60% planned → produksi turun signifikan",
            },
            {
                "condition_id": "FAR-T2",
                "variable"    : "mortality_rate",
                "operator"    : ">",
                "threshold"   : 0.08,
                "event_type"  : "DISEASE_OUTBREAK",
                "description" : "IF mortality_rate > 8% → indikasi wabah penyakit",
            },
            {
                "condition_id": "FAR-T3",
                "variable"    : "feed_stock",
                "operator"    : "<",
                "threshold"   : "expected_daily_feed * 3",
                "event_type"  : "FEED_SHORTAGE",
                "description" : "IF feed_stock < kebutuhan 3 hari → pakan kritis",
            },
            {
                "condition_id": "FAR-T4",
                "variable"    : "disease_alert",
                "operator"    : "==",
                "threshold"   : 1,
                "event_type"  : "DISEASE_ALERT",
                "description" : "IF disease_alert == 1 → alert penyakit aktif",
            },
        ],
        "recovery": [
            {
                "condition_id": "FAR-R1",
                "variable"    : "production_capacity",
                "operator"    : ">=",
                "threshold"   : "planned_capacity * 0.75",
                "description" : "Produksi kembali ≥ 75% dari rencana",
            },
            {
                "condition_id": "FAR-R2",
                "variable"    : "mortality_rate",
                "operator"    : "<=",
                "threshold"   : 0.04,
                "description" : "Mortality rate turun ≤ 4%",
            },
            {
                "condition_id": "FAR-R3",
                "variable"    : "disease_alert",
                "operator"    : "==",
                "threshold"   : 0,
                "description" : "Disease alert cleared",
            },
        ],
    },

    "slaughterhouse": {
        "logic"      : "OR",
        "description": "Slaughterhouse terganggu jika salah satu kondisi berikut terpenuhi",
        "onset": [
            {
                "condition_id": "SLH-T1",
                "variable"    : "processing_capacity",
                "operator"    : "<",
                "threshold"   : "max_capacity * 0.50",
                "event_type"  : "CAPACITY_DROP",
                "description" : "IF processing_capacity < 50% max → kapasitas turun drastis",
            },
            {
                "condition_id": "SLH-T2",
                "variable"    : "queue_length",
                "operator"    : ">",
                "threshold"   : 100,
                "event_type"  : "QUEUE_BOTTLENECK",
                "description" : "IF queue_length > 100 ekor → bottleneck operasional",
            },
            {
                "condition_id": "SLH-T3",
                "variable"    : "processing_delay",
                "operator"    : ">",
                "threshold"   : 4,
                "event_type"  : "PROCESSING_DELAY",
                "description" : "IF processing_delay > 4 jam → keterlambatan signifikan",
            },
            {
                "condition_id": "SLH-T4",
                "variable"    : "equipment_status",
                "operator"    : "==",
                "threshold"   : "down",
                "event_type"  : "EQUIPMENT_DOWN",
                "description" : "IF equipment_status == down → peralatan tidak beroperasi",
            },
            {
                "condition_id": "SLH-T5",
                "variable"    : "worker_availability",
                "operator"    : "<",
                "threshold"   : 0.60,
                "event_type"  : "WORKER_SHORTAGE",
                "description" : "IF worker_availability < 60% → tenaga kerja tidak cukup",
            },
            {
                "condition_id": "SLH-T6",
                "variable"    : "output_stock",
                "operator"    : "<",
                "threshold"   : "max_output * 0.30",
                "event_type"  : "OUTPUT_SHORTAGE",
                "description" : "IF output_stock < 30% max → stok karkas sangat rendah",
            },
        ],
        "recovery": [
            {
                "condition_id": "SLH-R1",
                "variable"    : "processing_capacity",
                "operator"    : ">=",
                "threshold"   : "max_capacity * 0.70",
                "description" : "Kapasitas kembali ≥ 70%",
            },
            {
                "condition_id": "SLH-R2",
                "variable"    : "processing_delay",
                "operator"    : "<=",
                "threshold"   : 2,
                "description" : "Delay turun ≤ 2 jam",
            },
            {
                "condition_id": "SLH-R3",
                "variable"    : "equipment_status",
                "operator"    : "!=",
                "threshold"   : "down",
                "description" : "Peralatan tidak lagi down",
            },
        ],
    },

    "wholesaler": {
        "logic"      : "OR",
        "description": "Wholesaler terganggu jika salah satu kondisi berikut terpenuhi",
        "onset": [
            {
                "condition_id": "WHO-T1",
                "variable"    : "inventory_level",
                "operator"    : "<",
                "threshold"   : "capacity * 0.30",
                "event_type"  : "LOW_INVENTORY",
                "description" : "IF inventory < 30% capacity → stok di bawah reorder point",
            },
            {
                "condition_id": "WHO-T2",
                "variable"    : "pending_shipments",
                "operator"    : ">",
                "threshold"   : 50,
                "event_type"  : "SHIPMENT_BACKLOG",
                "description" : "IF pending_shipments > 50 kg → backlog menumpuk",
            },
            {
                "condition_id": "WHO-T3",
                "variable"    : "incoming_orders",
                "operator"    : ">",
                "threshold"   : "distribution_capacity * 1.20",
                "event_type"  : "DEMAND_OVERLOAD",
                "description" : "IF incoming_orders > 120% kapasitas → overload",
            },
            {
                "condition_id": "WHO-T4",
                "variable"    : "delivery_schedule",
                "operator"    : "==",
                "threshold"   : "delayed",
                "event_type"  : "DELIVERY_DELAYED",
                "description" : "IF delivery_schedule == delayed → terlambat ke Retail",
            },
        ],
        "recovery": [
            {
                "condition_id": "WHO-R1",
                "variable"    : "inventory_level",
                "operator"    : ">=",
                "threshold"   : "capacity * 0.50",
                "description" : "Inventory kembali ≥ 50% kapasitas",
            },
            {
                "condition_id": "WHO-R2",
                "variable"    : "pending_shipments",
                "operator"    : "<=",
                "threshold"   : 20,
                "description" : "Backlog turun ≤ 20 kg",
            },
            {
                "condition_id": "WHO-R3",
                "variable"    : "delivery_schedule",
                "operator"    : "==",
                "threshold"   : "normal",
                "description" : "Delivery schedule kembali normal",
            },
        ],
    },

    "retail": {
        "logic"      : "OR",
        "description": "Retail terganggu jika salah satu kondisi berikut terpenuhi",
        "onset": [
            {
                "condition_id": "RET-T1",
                "variable"    : "retail_inventory",
                "operator"    : "<",
                "threshold"   : "safety_stock",
                "event_type"  : "BELOW_SAFETY_STOCK",
                "description" : "IF retail_inventory < safety_stock → di bawah batas aman",
            },
            {
                "condition_id": "RET-T2",
                "variable"    : "stockout_flag",
                "operator"    : "==",
                "threshold"   : 1,
                "event_type"  : "STOCKOUT",
                "description" : "IF stockout_flag == 1 → stok habis total",
            },
            {
                "condition_id": "RET-T3",
                "variable"    : "sales_rate",
                "operator"    : ">",
                "threshold"   : "expected_sales_rate * 1.50",
                "event_type"  : "DEMAND_SURGE",
                "description" : "IF sales_rate > 150% expected → lonjakan permintaan ekstrem",
            },
            {
                "condition_id": "RET-T4",
                "variable"    : "shortage_duration",
                "operator"    : ">",
                "threshold"   : 2,
                "event_type"  : "PROLONGED_SHORTAGE",
                "description" : "IF shortage_duration > 2 jam → kekurangan berkepanjangan",
            },
        ],
        "recovery": [
            {
                "condition_id": "RET-R1",
                "variable"    : "retail_inventory",
                "operator"    : ">=",
                "threshold"   : "capacity * 0.40",
                "description" : "Inventory kembali ≥ 40% kapasitas",
            },
            {
                "condition_id": "RET-R2",
                "variable"    : "stockout_flag",
                "operator"    : "==",
                "threshold"   : 0,
                "description" : "Stockout flag cleared",
            },
            {
                "condition_id": "RET-R3",
                "variable"    : "shortage_duration",
                "operator"    : "==",
                "threshold"   : 0,
                "description" : "Shortage duration = 0 (tidak ada kekurangan)",
            },
        ],
    },
}


def _resolve(threshold, db_state):
    if isinstance(threshold, str) and any(c in threshold for c in ['*','+']):
        try:
            return eval(threshold, {}, db_state)
        except Exception:
            return threshold
    return threshold


def _compare(val, operator, threshold):
    try:
        if   operator == "<"  : return float(val) <  float(threshold)
        elif operator == "<=" : return float(val) <= float(threshold)
        elif operator == ">"  : return float(val) >  float(threshold)
        elif operator == ">=" : return float(val) >= float(threshold)
        elif operator == "==" :
            # Numeric equality: 0.0 == 0 must be True
            try: return float(val) == float(threshold)
            except (TypeError, ValueError): return str(val) == str(threshold)
        elif operator == "!=" :
            try: return float(val) != float(threshold)
            except (TypeError, ValueError): return str(val) != str(threshold)
    except (TypeError, ValueError):
        return str(val) == str(threshold)
    return False


def check_disruption(node_type: str, db_state: dict) -> dict:
    """
    Cek apakah node mengalami disrupsi onset.
    Dipanggil oleh agent saat interval monitoring.
    Return: {disrupted: 0/1, triggered_by: [...], event_types: [...]}
    """
    triggered = []
    for rule in DISRUPTION_TRIGGERS[node_type]["onset"]:
        val = db_state.get(rule["variable"])
        if val is None:
            continue
        thr = _resolve(rule["threshold"], db_state)
        if _compare(val, rule["operator"], thr):
            triggered.append({
                "condition_id": rule["condition_id"],
                "event_type"  : rule["event_type"],
                "variable"    : rule["variable"],
                "value"       : val,
                "threshold"   : thr,
                "description" : rule["description"],
            })
    return {
        "disrupted"   : 1 if triggered else 0,
        "triggered_by": [t["condition_id"] for t in triggered],
        "event_types" : [t["event_type"]   for t in triggered],
        "details"     : triggered,
    }


def check_recovery(node_type: str, db_state: dict) -> bool:
    """
    Cek apakah node sudah memenuhi kondisi recovery.
    Return True jika SEMUA recovery conditions terpenuhi (AND logic).
    """
    recovery_rules = DISRUPTION_TRIGGERS[node_type]["recovery"]
    return all(
        _compare(db_state.get(r["variable"]), r["operator"],
                 _resolve(r["threshold"], db_state))
        for r in recovery_rules
        if db_state.get(r["variable"]) is not None
    )


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from agent_database import init_node_state

    print("=== DISRUPTION TRIGGER EVALUATION (FINAL) ===\n")
    cases = [
        ("supplier",      "Normal",   {}),
        ("supplier",      "Disrupted",{"lead_time": 6, "price_index": 1.8, "available_supply": 250}),
        ("farm",          "Normal",   {}),
        ("farm",          "Disrupted",{"mortality_rate": 0.12, "disease_alert": 1, "production_capacity": 320, "planned_capacity": 800}),
        ("slaughterhouse","Normal",   {}),
        ("slaughterhouse","Disrupted",{"equipment_status": "down", "queue_length": 130, "processing_capacity": 200, "max_capacity": 500}),
        ("wholesaler",    "Normal",   {}),
        ("wholesaler",    "Disrupted",{"inventory_level": 60, "capacity": 300, "delivery_schedule": "delayed"}),
        ("retail",        "Normal",   {}),
        ("retail",        "Disrupted",{"retail_inventory": 15, "safety_stock": 30, "stockout_flag": 1}),
    ]
    for node, label, overrides in cases:
        state  = init_node_state(node, overrides)
        result = check_disruption(node, state)
        recovered = check_recovery(node, state)
        status = "DISRUPTED ⚠" if result["disrupted"] else "Normal ✓"
        print(f"  [{node.upper()}] {label} → {status} | Recovery: {recovered}")
        for d in result["details"]:
            print(f"    {d['condition_id']}: {d['variable']}={d['value']} (threshold={d['threshold']})")
        print()
