"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 01b — AGENT DATABASE + CONTOH DATA NORMAL (FINAL)             ║
║  MAS Poultry Supply Chain Resilience                                 ║
║  Kondisi: Normal (disrupted=0, semua threshold tidak terlewati)      ║
║  Periode : 30 hari | Format: Pandas DataFrame per tier              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)
START = datetime(2026, 1, 1, 6, 0)

def _ts(interval_hours, n):
    return [(START + timedelta(hours=interval_hours * i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)]

# ── SUPPLIER — 18 jam → 40 obs ──────────────────────────────────────
def supplier_data(n=40):
    cap = 1000
    supply = np.clip(np.random.normal(920, 28, n), 810, 980).round(0)
    df = pd.DataFrame({
        "timestamp"           : _ts(18, n),
        "node_id"             : "supplier_1",
        "node_type"           : "supplier",
        "available_supply"    : supply,
        "capacity"            : cap,
        "stock_ratio"         : (supply / cap).round(3),
        "lead_time"           : np.clip(np.random.normal(2.0, 0.18, n), 1.5, 2.8).round(2),
        "shipment_status"     : "on_time",
        "price_index"         : np.clip(np.random.normal(1.02, 0.025, n), 0.96, 1.12).round(3),
        "supplier_reliability": np.clip(np.random.normal(0.95, 0.018, n), 0.89, 1.00).round(3),
        "disrupted"           : 0,
    })
    # Validasi: pastikan semua di atas threshold disrupsi
    assert (df.stock_ratio >= 0.30).all(),   "stock_ratio violation"
    assert (df.lead_time   <= 4.0).all(),    "lead_time violation"
    assert (df.price_index <= 1.50).all(),   "price_index violation"
    assert (df.supplier_reliability >= 0.60).all(), "reliability violation"
    return df

# ── FARM — 9 jam → 80 obs ───────────────────────────────────────────
def farm_data(n=80):
    planned = 800
    prod    = np.clip(np.random.normal(760, 18, n), 700, 800).round(0)
    feed    = np.clip(np.random.normal(475, 28, n), 380, 555).round(0)
    mort    = np.clip(np.random.normal(0.022, 0.003, n), 0.015, 0.038).round(4)
    # Live inventory: siklus panen setiap ~7 hari
    cycle = max(1, n // 7)
    live  = np.array([max(510, 800 - (i % cycle / cycle) * 290
                          + np.random.normal(0, 12)) for i in range(n)]).round(0)
    df = pd.DataFrame({
        "timestamp"           : _ts(9, n),
        "node_id"             : "farm_1",
        "node_type"           : "farm",
        "live_inventory"      : live,
        "production_capacity" : prod,
        "planned_capacity"    : planned,
        "production_ratio"    : (prod / planned).round(3),
        "growth_status"       : "normal",
        "mortality_rate"      : mort,
        "outgoing_orders"     : np.clip(np.random.normal(485, 18, n), 440, 535).round(0),
        "feed_stock"          : feed,
        "expected_daily_feed" : 80,
        "feed_days_remaining" : (feed / 80).round(1),
        "disease_alert"       : 0,
        "disrupted"           : 0,
    })
    assert (df.production_ratio >= 0.60).all(), "production_ratio violation"
    assert (df.mortality_rate   <= 0.08).all(), "mortality_rate violation"
    assert (df.feed_days_remaining >= 3).all(), "feed_days violation"
    return df

# ── SLAUGHTERHOUSE — 3 jam → 240 obs ────────────────────────────────
def slaughterhouse_data(n=240):
    max_cap = 500
    max_out = 400
    hours   = [(6 + 3*i) % 24 for i in range(n)]
    shift   = np.array([1.0 if 6 <= h < 18 else 0.78 for h in hours])
    proc    = np.clip(shift * max_cap * np.random.normal(1.0, 0.04, n), 260, 500).round(0)
    out     = np.clip(shift * np.random.normal(310, 22, n), 130, 395).round(0)
    df = pd.DataFrame({
        "timestamp"          : _ts(3, n),
        "node_id"            : "slaughterhouse_1",
        "node_type"          : "slaughterhouse",
        "input_inventory"    : np.clip(np.random.normal(378, 28, n), 285, 448).round(0),
        "processing_capacity": proc,
        "max_capacity"       : max_cap,
        "capacity_ratio"     : (proc / max_cap).round(3),
        "queue_length"       : np.clip(np.random.normal(44, 9, n), 18, 78).round(0),
        "processing_delay"   : np.clip(np.random.normal(0.28, 0.28, n), 0, 1.4).round(2),
        "output_stock"       : out,
        "max_output"         : max_out,
        "output_ratio"       : (out / max_out).round(3),
        "equipment_status"   : "operational",
        "hygiene_compliance" : np.clip(np.random.normal(0.97, 0.018, n), 0.91, 1.00).round(3),
        "worker_availability": np.clip(np.random.normal(0.92, 0.038, n), 0.78, 1.00).round(3),
        "disrupted"          : 0,
    })
    assert (df.capacity_ratio     >= 0.50).all(), "capacity_ratio violation"
    assert (df.queue_length        <= 100).all(),  "queue_length violation"
    assert (df.processing_delay    <= 4.0).all(),  "processing_delay violation"
    assert (df.worker_availability >= 0.60).all(), "worker violation"
    return df

# ── WHOLESALER — 2 jam → 360 obs ────────────────────────────────────
def wholesaler_data(n=360):
    cap     = 300
    inv     = []
    current = 195.0
    for i in range(n):
        if i % 12 == 0 and current < 165:           # restock tiap ~24 jam
            current = min(cap, current + np.random.uniform(55, 95))
        current = max(cap * 0.32, current - np.random.normal(11, 2.8))
        inv.append(round(current, 1))
    inv = np.array(inv)
    orders = np.clip(np.random.normal(143, 18, n), 92, 195).round(0)
    df = pd.DataFrame({
        "timestamp"            : _ts(2, n),
        "node_id"              : "wholesaler_1",
        "node_type"            : "wholesaler",
        "inventory_level"      : inv,
        "capacity"             : cap,
        "stock_ratio"          : (inv / cap).round(3),
        "reorder_point"        : 90,
        "shipment_status"      : "on_time",
        "distribution_capacity": cap,
        "pending_shipments"    : np.clip(np.random.normal(7.5, 4.5, n), 0, 28).round(1),
        "delivery_schedule"    : "normal",
        "incoming_orders"      : orders,
        "order_vs_capacity"    : (orders / cap).round(3),
        "disrupted"            : 0,
    })
    assert (df.stock_ratio        >= 0.30).all(), "inventory violation"
    assert (df.pending_shipments   <= 50).all(),  "pending violation"
    assert (df.order_vs_capacity   <= 1.20).all(),"order_capacity violation"
    return df

# ── RETAIL — 0.75 jam (45 mnt) → 960 obs ───────────────────────────
def retail_data(n=960):
    cap          = 150
    safety_stock = 30
    hours = [((6*60 + int(45*i))//60) % 24 for i in range(n)]
    demand_factor = np.array([
        0.32 if h < 6 else 1.18 if 6 <= h < 10
        else 0.82 if 10 <= h < 15 else 1.28 if 15 <= h < 20
        else 0.48 for h in hours
    ])
    sales = np.clip(demand_factor * np.random.normal(10, 1.4, n), 1.5, 19.5).round(2)
    inv   = []
    curr  = 88.0
    for i in range(n):
        curr = max(0, curr - sales[i] * 0.75)
        if i % 11 == 0 and curr < 75:              # reorder tiap ~8 jam
            curr = min(cap, curr + np.random.uniform(38, 68))
        inv.append(round(curr, 1))
    inv = np.array(inv)
    # Pastikan tidak pernah stockout dalam kondisi normal
    inv = np.where(inv < 5, 5 + np.random.uniform(2, 10, n), inv)
    reorder = np.where(inv < safety_stock,
                       np.clip(np.random.normal(48, 9, n), 28, 75).round(0), 0)
    df = pd.DataFrame({
        "timestamp"          : _ts(0.75, n),
        "node_id"            : "retail_1",
        "node_type"          : "retail",
        "retail_inventory"   : inv,
        "capacity"           : cap,
        "stock_ratio"        : (inv / cap).round(3),
        "safety_stock"       : safety_stock,
        "above_safety_stock" : (inv >= safety_stock).astype(int),
        "sales_rate"         : sales,
        "expected_sales_rate": 10.0,
        "sales_vs_expected"  : (sales / 10.0).round(3),
        "shortage_duration"  : 0.0,
        "demand_estimate"    : np.clip(np.random.normal(89, 7.5, n), 70, 112).round(1),
        "reorder_request"    : reorder,
        "stockout_flag"      : 0,
        "disrupted"          : 0,
    })
    assert (df.stockout_flag    == 0).all(),    "stockout violation"
    assert (df.shortage_duration== 0).all(),    "shortage violation"
    return df


def generate_all():
    return {
        "supplier"      : supplier_data(),
        "farm"          : farm_data(),
        "slaughterhouse": slaughterhouse_data(),
        "wholesaler"    : wholesaler_data(),
        "retail"        : retail_data(),
    }


if __name__ == "__main__":
    dfs = generate_all()
    print("=== NORMAL CONDITION DATA (30 DAYS) — VALIDATED ===\n")
    summary = []
    for tier, df in dfs.items():
        num_cols = df.select_dtypes(include='number').columns
        num_cols = [c for c in num_cols if c not in
                    ['disrupted','disease_alert','stockout_flag','above_safety_stock']]
        summary.append({
            "Tier"    : tier,
            "Records" : len(df),
            "Columns" : len(df.columns),
            "Interval": str({'supplier':18,'farm':9,'slaughterhouse':3,'wholesaler':2,'retail':0.75}[tier]) + " jam",
            "disrupted=0": (df.disrupted == 0).all(),
        })
        path = f"/mnt/user-data/outputs/data_normal_{tier}.csv"
        df.to_csv(path, index=False)
        print(f"  [{tier.upper()}] {len(df)} records × {len(df.columns)} cols → saved")
        print(f"  {df[num_cols].describe().round(3).loc[['mean','std','min','max']].to_string()}\n")

    print(pd.DataFrame(summary).to_string(index=False))
