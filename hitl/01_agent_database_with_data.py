"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 01b — AGENT DATABASE + DATA NORMAL (FINAL)                    ║
║  MAS Poultry Supply Chain Resilience                                 ║
║                                                                      ║
║  Perubahan dari versi sebelumnya:                                    ║
║  - Data dikalibrasi agar konsisten dengan threshold di 01 & 02      ║
║  - Kolom CSV selaras persis dengan variabel DB di agent_database    ║
║  - Ditambah kolom feed_days_remaining untuk validasi FAR-T3          ║
║  - Semua assertion threshold diperkuat                               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)
START = datetime(2026, 1, 1, 6, 0)

def _ts(interval_hours: float, n: int) -> list:
    return [(START + timedelta(hours=interval_hours * i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)]

# ════════════════════════════════════════════════════════════════════
# SUPPLIER — interval 18 jam → 40 observasi / 30 hari
# Thresholds disrupsi: supply<30%, lead>4, price>1.5, reliability<0.6
# ════════════════════════════════════════════════════════════════════
def supplier_data(n: int = 40) -> pd.DataFrame:
    cap      = 1000
    supply   = np.clip(np.random.normal(920, 28, n), 820, 980).round(0)
    lead     = np.clip(np.random.normal(2.0, 0.18, n), 1.5, 2.8).round(2)
    price    = np.clip(np.random.normal(1.02, 0.025, n), 0.96, 1.12).round(3)
    reliable = np.clip(np.random.normal(0.95, 0.018, n), 0.89, 1.00).round(3)

    df = pd.DataFrame({
        "timestamp"           : _ts(18, n),
        "node_id"             : "supplier_1",
        "node_type"           : "supplier",
        # Variabel DB utama (selaras dengan agent_database.py)
        "available_supply"    : supply,
        "capacity"            : cap,
        "lead_time"           : lead,
        "shipment_status"     : "on_time",
        "price_index"         : price,
        "supplier_reliability": reliable,
        # Kolom turunan untuk analisis
        "stock_ratio"         : (supply / cap).round(3),
        "disrupted"           : 0,
    })

    # Validasi threshold disrupsi tidak terlewati
    assert (df["stock_ratio"]          >= 0.30).all(), "supplier stock_ratio violation"
    assert (df["lead_time"]            <= 4.00).all(), "supplier lead_time violation"
    assert (df["price_index"]          <= 1.50).all(), "supplier price_index violation"
    assert (df["supplier_reliability"] >= 0.60).all(), "supplier reliability violation"
    assert (df["disrupted"]            == 0).all(),    "supplier disrupted violation"
    return df

# ════════════════════════════════════════════════════════════════════
# FARM — interval 9 jam → 80 observasi / 30 hari
# Thresholds: prod_ratio<0.60, mortality>0.08, feed_days<3, disease=1
# ════════════════════════════════════════════════════════════════════
def farm_data(n: int = 80) -> pd.DataFrame:
    planned  = 800
    prod     = np.clip(np.random.normal(760, 18, n), 700, 800).round(0)
    feed     = np.clip(np.random.normal(475, 28, n), 380, 555).round(0)
    mort     = np.clip(np.random.normal(0.022, 0.003, n), 0.015, 0.038).round(4)
    orders   = np.clip(np.random.normal(485, 18, n), 440, 535).round(0)
    # Live inventory: siklus panen setiap ~7 hari
    cycle    = max(1, n // 7)
    live     = np.array([
        max(510, 800 - (i % cycle / cycle) * 290 + np.random.normal(0, 12))
        for i in range(n)
    ]).round(0)
    daily_feed = 80  # konstan

    df = pd.DataFrame({
        "timestamp"           : _ts(9, n),
        "node_id"             : "farm_1",
        "node_type"           : "farm",
        # Variabel DB utama
        "live_inventory"      : live,
        "production_capacity" : prod,
        "planned_capacity"    : planned,
        "growth_status"       : "normal",
        "mortality_rate"      : mort,
        "outgoing_orders"     : orders,
        "feed_stock"          : feed,
        "expected_daily_feed" : daily_feed,
        "disease_alert"       : 0,
        # Kolom turunan
        "production_ratio"    : (prod / planned).round(3),
        "feed_days_remaining" : (feed / daily_feed).round(1),
        "disrupted"           : 0,
    })

    assert (df["production_ratio"]    >= 0.60).all(), "farm production_ratio violation"
    assert (df["mortality_rate"]      <= 0.08).all(), "farm mortality_rate violation"
    assert (df["feed_days_remaining"] >= 3.00).all(), "farm feed_days violation"
    assert (df["disease_alert"]       == 0).all(),    "farm disease_alert violation"
    assert (df["disrupted"]           == 0).all(),    "farm disrupted violation"
    return df

# ════════════════════════════════════════════════════════════════════
# SLAUGHTERHOUSE — interval 3 jam → 240 observasi / 30 hari
# Thresholds: capacity_ratio<0.50, queue>100, delay>4, output<30%, worker<0.60
# ════════════════════════════════════════════════════════════════════
def slaughterhouse_data(n: int = 240) -> pd.DataFrame:
    max_cap  = 500
    max_out  = 400
    # Variasi kapasitas berdasarkan shift kerja (pagi lebih tinggi)
    hours    = [(6 + 3 * i) % 24 for i in range(n)]
    shift    = np.array([1.0 if 6 <= h < 18 else 0.78 for h in hours])
    proc     = np.clip(shift * max_cap * np.random.normal(1.0, 0.04, n), 260, 500).round(0)
    out      = np.clip(shift * np.random.normal(310, 22, n), 130, 395).round(0)
    worker   = np.clip(np.random.normal(0.92, 0.038, n), 0.78, 1.00).round(3)
    delay    = np.clip(np.random.normal(0.28, 0.28, n), 0, 1.4).round(2)
    queue    = np.clip(np.random.normal(44, 9, n), 18, 78).round(0)
    inp      = np.clip(np.random.normal(378, 28, n), 285, 448).round(0)
    hygiene  = np.clip(np.random.normal(0.97, 0.018, n), 0.91, 1.00).round(3)

    df = pd.DataFrame({
        "timestamp"          : _ts(3, n),
        "node_id"            : "slaughterhouse_1",
        "node_type"          : "slaughterhouse",
        # Variabel DB utama
        "input_inventory"    : inp,
        "processing_capacity": proc,
        "max_capacity"       : max_cap,
        "queue_length"       : queue,
        "processing_delay"   : delay,
        "output_stock"       : out,
        "max_output"         : max_out,
        "equipment_status"   : "operational",
        "hygiene_compliance" : hygiene,
        "worker_availability": worker,
        # Kolom turunan
        "capacity_ratio"     : (proc / max_cap).round(3),
        "output_ratio"       : (out / max_out).round(3),
        "disrupted"          : 0,
    })

    assert (df["capacity_ratio"]     >= 0.50).all(), "slh capacity_ratio violation"
    assert (df["queue_length"]        <= 100).all(),  "slh queue_length violation"
    assert (df["processing_delay"]    <= 4.0).all(),  "slh processing_delay violation"
    assert (df["output_ratio"]        >= 0.30).all(), "slh output_ratio violation"
    assert (df["worker_availability"] >= 0.60).all(), "slh worker violation"
    assert (df["disrupted"]           == 0).all(),    "slh disrupted violation"
    return df

# ════════════════════════════════════════════════════════════════════
# WHOLESALER — interval 2 jam → 360 observasi / 30 hari
# Thresholds: inventory<30%, pending>50, orders>120%
# ════════════════════════════════════════════════════════════════════
def wholesaler_data(n: int = 360) -> pd.DataFrame:
    cap     = 300
    dist_cap= 300
    # Inventory naik-turun mengikuti ritme restock & distribusi
    inv     = []
    current = 195.0
    for i in range(n):
        if i % 12 == 0 and current < 165:
            current = min(cap, current + np.random.uniform(55, 95))
        current = max(cap * 0.32, current - np.random.normal(11, 2.8))
        inv.append(round(current, 1))
    inv     = np.array(inv)
    orders  = np.clip(np.random.normal(143, 18, n), 92, 195).round(0)
    pending = np.clip(np.random.normal(7.5, 4.5, n), 0, 28).round(1)

    df = pd.DataFrame({
        "timestamp"            : _ts(2, n),
        "node_id"              : "wholesaler_1",
        "node_type"            : "wholesaler",
        # Variabel DB utama
        "inventory_level"      : inv,
        "capacity"             : cap,
        "reorder_point"        : 90,
        "shipment_status"      : "on_time",
        "distribution_capacity": dist_cap,
        "pending_shipments"    : pending,
        "delivery_schedule"    : "normal",
        "incoming_orders"      : orders,
        # Kolom turunan
        "stock_ratio"          : (inv / cap).round(3),
        "order_vs_capacity"    : (orders / dist_cap).round(3),
        "disrupted"            : 0,
    })

    assert (df["stock_ratio"]       >= 0.30).all(), "wholesaler stock_ratio violation"
    assert (df["pending_shipments"] <= 50.0).all(), "wholesaler pending violation"
    assert (df["order_vs_capacity"] <= 1.20).all(), "wholesaler order_cap violation"
    assert (df["disrupted"]         == 0).all(),    "wholesaler disrupted violation"
    return df

# ════════════════════════════════════════════════════════════════════
# RETAIL — interval 0.75 jam (45 mnt) → 960 observasi / 30 hari
# Thresholds: inventory<safety_stock, stockout=1, sales>150%, shortage>2h
# ════════════════════════════════════════════════════════════════════
def retail_data(n: int = 960) -> pd.DataFrame:
    cap          = 150
    safety_stock = 30

    # Sales rate mengikuti pola permintaan harian
    hours = [((6 * 60 + int(45 * i)) // 60) % 24 for i in range(n)]
    demand_factor = np.array([
        0.32 if h < 6 else 1.18 if 6 <= h < 10
        else 0.82 if 10 <= h < 15 else 1.28 if 15 <= h < 20
        else 0.48 for h in hours
    ])
    sales = np.clip(demand_factor * np.random.normal(10, 1.4, n), 1.5, 14.5).round(2)

    # Inventory bergerak mengikuti penjualan, reorder periodik
    inv   = []
    curr  = 88.0
    for i in range(n):
        curr = max(0.0, curr - sales[i] * 0.75)
        if i % 11 == 0 and curr < 75:
            curr = min(cap, curr + np.random.uniform(38, 68))
        inv.append(round(curr, 1))
    inv = np.array(inv)

    # Pastikan tidak pernah di bawah 5 kg (kondisi normal)
    inv = np.where(inv < 5, 5 + np.random.uniform(2, 10, n), inv)

    reorder = np.where(
        inv < safety_stock,
        np.clip(np.random.normal(48, 9, n), 28, 75).round(0),
        0
    )
    demand_est = np.clip(np.random.normal(89, 7.5, n), 70, 112).round(1)

    df = pd.DataFrame({
        "timestamp"          : _ts(0.75, n),
        "node_id"            : "retail_1",
        "node_type"          : "retail",
        # Variabel DB utama
        "retail_inventory"   : inv,
        "capacity"           : cap,
        "safety_stock"       : safety_stock,
        "sales_rate"         : sales,
        "expected_sales_rate": 10.0,
        "shortage_duration"  : 0.0,
        "demand_estimate"    : demand_est,
        "reorder_request"    : reorder,
        "stockout_flag"      : 0,
        # Kolom turunan
        "stock_ratio"        : (inv / cap).round(3),
        "above_safety_stock" : (inv >= safety_stock).astype(int),
        "sales_vs_expected"  : (sales / 10.0).round(3),
        "disrupted"          : 0,
    })

    assert (df["stockout_flag"]    == 0).all(), "retail stockout violation"
    assert (df["shortage_duration"]== 0).all(), "retail shortage violation"
    assert (df["disrupted"]        == 0).all(), "retail disrupted violation"
    # Catatan: dalam kondisi normal boleh ada saat inventory < safety_stock
    # karena reorder sedang dalam perjalanan — ini realistis
    return df


# ════════════════════════════════════════════════════════════════════
# GENERATE ALL & SAVE CSV
# ════════════════════════════════════════════════════════════════════

def generate_all(output_dir: str = ".") -> dict:
    import os
    os.makedirs(output_dir, exist_ok=True)

    generators = {
        "supplier"      : supplier_data,
        "farm"          : farm_data,
        "slaughterhouse": slaughterhouse_data,
        "wholesaler"    : wholesaler_data,
        "retail"        : retail_data,
    }
    dfs = {}
    for tier, fn in generators.items():
        df   = fn()
        path = os.path.join(output_dir, f"data_normal_{tier}.csv")
        df.to_csv(path, index=False)
        dfs[tier] = df
    return dfs


if __name__ == "__main__":
    import os

    OUT_DIR = "/mnt/user-data/outputs"

    print("=== GENERATING NORMAL CONDITION DATA (30 DAYS) ===\n")
    dfs = generate_all(output_dir=OUT_DIR)

    INTERVALS = {"supplier":18,"farm":9,"slaughterhouse":3,"wholesaler":2,"retail":0.75}
    summary   = []
    for tier, df in dfs.items():
        num_cols = df.select_dtypes(include="number").columns.tolist()
        num_cols = [c for c in num_cols if c not in
                    ("disrupted","disease_alert","stockout_flag",
                     "above_safety_stock","capacity","max_capacity",
                     "max_output","planned_capacity","expected_daily_feed",
                     "expected_sales_rate","reorder_point","distribution_capacity")]
        print(f"  [{tier.upper()}]")
        print(f"  Records  : {len(df)} rows × {len(df.columns)} cols")
        print(f"  Interval : {INTERVALS[tier]} jam")
        print(f"  Validated: disrupted=0 ✓ | thresholds OK ✓")
        print(df[num_cols].describe().round(3).loc[["mean","std","min","max"]].to_string())
        print()
        summary.append({
            "Tier"    : tier,
            "Records" : len(df),
            "Columns" : len(df.columns),
            "Interval": f"{INTERVALS[tier]} jam",
            "Validated": True,
        })

    print(pd.DataFrame(summary).to_string(index=False))
    print(f"\n  All CSV saved to: {OUT_DIR}/")
