"""
╔══════════════════════════════════════════════════════════════════════╗
║  REACTIVE BASELINE — No MAS Coordination                            ║
║  Each tier reacts independently with fixed reorder policy           ║
║  No coordinator, no cross-tier communication                        ║
║                                                                      ║
║  Mechanism:                                                          ║
║  - Each tier has a fixed reorder_point threshold                    ║
║  - When inventory < reorder_point → trigger fixed restock order     ║
║  - No disruption report sent to any coordinator                     ║
║  - No CoordinationSignal received from any coordinator              ║
║  - Supply flow continues but at REDUCED rate during disruption      ║
║    (no adaptive adjustment — fixed schedule only)                   ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

import os
import json

from agent_database      import AGENT_DATABASE, init_node_state, get_monitoring_interval
from disruption_triggers import check_disruption
from scenario_loader     import get_disruption_schedule

CHAIN_ORDER  = ["supplier","farm","slaughterhouse","wholesaler","retail"]
TICK_MINUTES = 15
TICK_HOURS   = TICK_MINUTES / 60

# ════════════════════════════════════════════════════════════════════
# RULES LOADER
# ════════════════════════════════════════════════════════════════════

_RULES_DIR         = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_RULES_PATH = os.path.join(_RULES_DIR, "default_rules.json")
_CUSTOM_RULES_PATH  = os.path.join(_RULES_DIR, "custom_rules.json")


def _load_rules_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rules(use_custom: bool = False) -> dict:
    """
    Load reactive rules from JSON.

    - use_custom=False  → always returns default_rules.json (the fixed baseline)
    - use_custom=True   → merges custom_rules.json on top of defaults so any
                          key not overridden still falls back to the default value.

    Returns a dict with keys:
        reorder_policy           : dict[tier] → {threshold_ratio, reorder_qty_ratio}
        restock_interval         : dict  → {wholesaler, retail}
        fixed_disruption_factor  : float
    """
    defaults = _load_rules_file(_DEFAULT_RULES_PATH)

    if not use_custom:
        return _extract_rules(defaults)

    # Merge custom on top of defaults
    if not os.path.exists(_CUSTOM_RULES_PATH):
        return _extract_rules(defaults)

    custom = _load_rules_file(_CUSTOM_RULES_PATH)
    merged = json.loads(json.dumps(defaults))          # deep copy

    # reorder_policy — per-tier merge
    for tier in CHAIN_ORDER:
        if "reorder_policy" in custom and tier in custom["reorder_policy"]:
            merged["reorder_policy"].setdefault(tier, {})
            merged["reorder_policy"][tier].update(custom["reorder_policy"][tier])

    # restock_interval — per-key merge
    if "restock_interval" in custom:
        for k, v in custom["restock_interval"].items():
            if k.startswith("_"):
                continue
            merged["restock_interval"][k] = v

    # fixed_disruption_factor — scalar override
    if "fixed_disruption_factor" in custom:
        merged["fixed_disruption_factor"] = custom["fixed_disruption_factor"]

    return _extract_rules(merged)


def _extract_rules(raw: dict) -> dict:
    """Strip comment keys and return only the numeric rule values."""
    reorder = {}
    for tier in CHAIN_ORDER:
        entry = raw.get("reorder_policy", {}).get(tier, {})
        reorder[tier] = {
            "threshold_ratio"  : float(entry.get("threshold_ratio",   0.40)),
            "reorder_qty_ratio": float(entry.get("reorder_qty_ratio", 0.30)),
        }

    interval_raw = raw.get("restock_interval", {})
    interval = {
        "wholesaler": int(interval_raw.get("wholesaler", 8)),
        "retail"    : int(interval_raw.get("retail",     4)),
    }

    factor = float(raw.get("fixed_disruption_factor", 0.35))

    return {
        "reorder_policy"          : reorder,
        "restock_interval"        : interval,
        "fixed_disruption_factor" : factor,
    }


# ════════════════════════════════════════════════════════════════════
# CSV DATA LOADER
# ════════════════════════════════════════════════════════════════════

class CSVDataLoader:
    """Load normal-operations baseline data from CSV files per tier."""

    def __init__(self, data_dir="."):
        self._cache     = {}
        self._baselines = {}
        self._data_dir  = data_dir
        for tier in CHAIN_ORDER:
            path = os.path.join(data_dir, f"data_normal_{tier}.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                self._cache[tier] = df
                num = df.select_dtypes(include="number").columns
                num = [c for c in num if c not in
                       ("disrupted", "disease_alert", "stockout_flag", "above_safety_stock")]
                self._baselines[tier] = df[num].mean().to_dict()

    def get_initial_state(self, tier: str,
                          rng: Optional[np.random.Generator] = None) -> dict:
        """Pick a row with adequate inventory levels as initial state."""
        if tier not in self._cache:
            return init_node_state(tier)
        df  = self._cache[tier]
        inv_col = {
            "supplier"      : "available_supply",
            "farm"          : "feed_stock",
            "slaughterhouse": "output_stock",
            "wholesaler"    : "inventory_level",
            "retail"        : "retail_inventory",
        }.get(tier)
        if inv_col and inv_col in df.columns:
            threshold = df[inv_col].quantile(0.40)
            good_rows = df[df[inv_col] >= threshold]
            if len(good_rows) == 0:
                good_rows = df
        else:
            good_rows = df
        idx = rng.integers(0, len(good_rows)) if rng else np.random.randint(0, len(good_rows))
        row = good_rows.iloc[int(idx)].to_dict()
        # Add any missing keys from AGENT_DATABASE defaults
        base = init_node_state(tier)
        for k, v in base.items():
            if k not in row:
                row[k] = v
        return row

    def get_sar_threshold(self, tier: str) -> float:
        """Return safety stock threshold for SAR calculation."""
        if tier in self._baselines and "safety_stock" in self._baselines[tier]:
            return float(self._baselines[tier]["safety_stock"])
        if tier == "retail":
            return 30.0
        return 0.0

    def get_baseline(self, tier: str) -> dict:
        return self._baselines.get(tier, {})


# ── Reorder policy per tier ──────────────────────────────────────────
# Loaded from default_rules.json (fixed baseline) or custom_rules.json
# (user-defined override). Pass use_custom=True to run_reactive_scenario
# to activate custom rules; default is always the fixed baseline.
#
# Module-level defaults are kept for backward-compat imports:
_DEFAULT_RULES       = load_rules(use_custom=False)
REORDER_POLICY       = _DEFAULT_RULES["reorder_policy"]
RESTOCK_INTERVAL     = _DEFAULT_RULES["restock_interval"]
FIXED_DISRUPTION_FACTOR = _DEFAULT_RULES["fixed_disruption_factor"]


class ReactiveNodeAgent:
    """
    Tier agent in reactive (no-MAS) mode.
    Acts only on local information, no external coordination.
    """
    def __init__(self, node_type, node_id, db_state):
        self.node_type = node_type
        self.node_id   = node_id
        self.db_state  = dict(db_state)
        self.disrupted = 0
        self._disruption_severity = None

    def consume_demand(self):
        nt = self.node_type
        if nt == "retail":
            sr   = self.db_state.get("sales_rate", 10)
            sold = sr * TICK_HOURS * np.random.uniform(0.88, 1.12)
            inv  = max(0.0, self.db_state.get("retail_inventory", 90) - sold)
            ss   = self.db_state.get("safety_stock", 30)
            self.db_state["retail_inventory"] = round(inv, 2)
            self.db_state["stockout_flag"]    = 1 if inv <= 0 else 0
            if inv < ss:
                self.db_state["shortage_duration"] = round(
                    self.db_state.get("shortage_duration", 0) + TICK_HOURS, 2)
            else:
                self.db_state["shortage_duration"] = 0.0
        elif nt == "wholesaler":
            demand = np.random.uniform(6, 12) * TICK_HOURS
            self.db_state["inventory_level"] = round(
                max(0.0, self.db_state.get("inventory_level", 200) - demand), 2)
        elif nt == "slaughterhouse":
            proc = self.db_state.get("processing_capacity", 500)
            add  = proc * TICK_HOURS * 0.12 * np.random.uniform(0.85, 1.0)
            self.db_state["output_stock"] = round(
                min(self.db_state.get("max_output", 400),
                    self.db_state.get("output_stock", 300) + add), 2)
        elif nt == "farm":
            daily = self.db_state.get("expected_daily_feed", 80)
            self.db_state["feed_stock"] = round(
                max(0.0, self.db_state.get("feed_stock", 500)
                    - daily * TICK_HOURS * np.random.uniform(0.95, 1.05)), 2)
        elif nt == "supplier":
            self.db_state["available_supply"] = round(
                max(0.0, self.db_state.get("available_supply", 1000)
                    - np.random.uniform(2, 6) * TICK_HOURS), 2)

    def check_local_disruption(self):
        """Check disruption status locally — no reporting to coordinator."""
        result = check_disruption(self.node_type, self.db_state)
        self.disrupted = result["disrupted"]
        if self.disrupted == 1:
            # Detect severity from mortality_rate if available
            mr = self.db_state.get("mortality_rate", 0)
            if   mr >= 0.30: self._disruption_severity = "crisis"
            elif mr >= 0.18: self._disruption_severity = "high"
            elif mr >= 0.10: self._disruption_severity = "medium"
            else:            self._disruption_severity = "low"

    def receive_restock(self, amount: float):
        nt = self.node_type
        if nt == "retail":
            cap = self.db_state.get("capacity", 150)
            inv = self.db_state.get("retail_inventory", 0)
            self.db_state["retail_inventory"] = round(min(cap, inv + amount), 2)
        elif nt == "wholesaler":
            cap = self.db_state.get("capacity", 300)
            inv = self.db_state.get("inventory_level", 0)
            self.db_state["inventory_level"] = round(min(cap, inv + amount), 2)

    def inject_disruption(self, db_changes: dict):
        self.db_state.update(db_changes)
        self.check_local_disruption()


class ReactiveSupplyFlowEngine:
    """
    Supply flow for reactive baseline.
    Uses FIXED schedule — no adaptive adjustment based on signals.
    Disruption reduces flow by a fixed factor regardless of severity.
    """
    def __init__(self, rules: dict = None):
        self._pending = defaultdict(list)
        r = rules or load_rules(use_custom=False)
        self._restock_interval        = r["restock_interval"]
        self._fixed_disruption_factor = r["fixed_disruption_factor"]
        self._reorder_policy          = r["reorder_policy"]

    def schedule_restock(self, tick, tier, amount, delay=0):
        self._pending[tick + delay].append((tier, amount))

    def deliver(self, tick, agents):
        if tick in self._pending:
            for tier, amount in self._pending[tick]:
                if tier in agents and amount > 0:
                    agents[tier].receive_restock(amount)
            del self._pending[tick]

    def compute_flow(self, tick, agents):
        """
        Fixed supply flow — no MAS coordination.
        Tier only knows its own inventory, not upstream status.

        reorder_qty_ratio  : porsi stok upstream yang dikirim per event restock.
        threshold_ratio    : batas inventory downstream yang memicu restock.
        restock_interval   : seberapa sering restock dicek (tick).
                             Interval lebih pendek = restock lebih sering,
                             setiap pengiriman tetap sama jumlahnya → total lebih banyak.
        fixed_disruption_factor : pengali saat upstream disrupted (0–1).
        """
        # ── Wholesaler → Retail ───────────────────────────────────────────
        if tick % self._restock_interval["retail"] == 0:
            ws = agents.get("wholesaler")
            rt = agents.get("retail")
            if ws and rt:
                ws_inv = ws.db_state.get("inventory_level", 200)
                rt_inv = rt.db_state.get("retail_inventory", 90)
                rt_cap = rt.db_state.get("capacity", 150)
                rt_ss  = rt.db_state.get("safety_stock", 30)

                # Restock jika retail di bawah threshold
                rt_threshold = rt_cap * self._reorder_policy["retail"]["threshold_ratio"]
                if rt_inv < rt_threshold and ws_inv > rt_ss:
                    # base_flow: kapasitas retail × reorder_qty_ratio per event
                    # Tidak dikalikan interval — interval lebih pendek = lebih sering kirim
                    # dengan jumlah yang sama per event (bukan dikecilkan)
                    base_flow = rt_cap * self._reorder_policy["retail"]["reorder_qty_ratio"]
                    if ws.disrupted == 1:
                        base_flow *= self._fixed_disruption_factor
                    amount = round(min(
                        ws_inv * self._reorder_policy["retail"]["reorder_qty_ratio"],
                        rt_cap - rt_inv,
                        base_flow
                    ), 2)
                    if amount > 0:
                        self.schedule_restock(tick, "retail", amount, delay=0)
                        ws.db_state["inventory_level"] = round(
                            max(0, ws_inv - amount), 2)

        # ── Slaughterhouse → Wholesaler ───────────────────────────────────
        if tick % self._restock_interval["wholesaler"] == 0:
            sh = agents.get("slaughterhouse")
            ws = agents.get("wholesaler")
            if sh and ws:
                sh_out = sh.db_state.get("output_stock", 300)
                ws_inv = ws.db_state.get("inventory_level", 200)
                ws_cap = ws.db_state.get("capacity", 300)

                ws_threshold = ws_cap * self._reorder_policy["wholesaler"]["threshold_ratio"]
                if ws_inv < ws_threshold and sh_out > 50:
                    base_flow = ws_cap * self._reorder_policy["wholesaler"]["reorder_qty_ratio"]
                    if sh.disrupted == 1:
                        base_flow *= self._fixed_disruption_factor
                    amount = round(min(
                        sh_out * self._reorder_policy["slaughterhouse"]["reorder_qty_ratio"],
                        ws_cap - ws_inv,
                        base_flow
                    ), 2)
                    if amount > 0:
                        self.schedule_restock(tick, "wholesaler", amount, delay=0)
                        sh.db_state["output_stock"] = round(
                            max(0, sh_out - amount), 2)


def run_reactive_scenario(scenario, csv_loader=None,
                          verbose=False, rng_seed=None,
                          use_custom_rules=False):
    """
    Run one scenario in Reactive Baseline mode.
    No coordinator, no HitL — each tier acts on fixed local policy only.

    Parameters
    ----------
    use_custom_rules : bool
        False (default) → use default_rules.json (fixed baseline).
        True            → merge custom_rules.json over the defaults.
    """
    np.random.seed(rng_seed)
    rng         = np.random.default_rng(rng_seed)
    start_dt    = datetime.strptime(scenario["start_datetime"], "%Y-%m-%d %H:%M")
    total_ticks = int(scenario["duration_hours"] / TICK_HOURS)

    # Load rules once for the whole run
    rules = load_rules(use_custom=use_custom_rules)
    reorder_policy = rules["reorder_policy"]

    if verbose:
        src = "custom" if use_custom_rules else "default"
        print(f"\n  [REACTIVE] S{scenario['scenario_id']:03d} | "
              f"{scenario.get('subtype','')} | {scenario['severity']} | rules={src}")

    # Initialize agents from CSV
    agents = {}
    for tier in CHAIN_ORDER:
        db_state = csv_loader.get_initial_state(tier, rng) \
                   if csv_loader else init_node_state(tier)
        agents[tier] = ReactiveNodeAgent(
            node_type=tier,
            node_id  =AGENT_DATABASE[tier]["meta"]["node_id"],
            db_state =db_state,
        )

    supply_flow = ReactiveSupplyFlowEngine(rules=rules)

    # Disruption schedule
    schedule    = get_disruption_schedule(scenario["scenario_id"])
    disrupt_map = {}
    for ev in schedule:
        tk = int(ev["at_hour"] / TICK_HOURS)
        disrupt_map.setdefault(tk, []).append(ev)

    stock_log          = []
    disruption_start   = None
    recovery_time      = None
    all_recovered_tick = None

    for tick in range(total_ticks):
        current_time = start_dt + timedelta(minutes=TICK_MINUTES * tick)

        # Inject disruptions
        if tick in disrupt_map:
            for ev in disrupt_map[tick]:
                agents[ev["node"]].inject_disruption(ev.get("db_changes", {}))

        # Deliver pending restocks
        supply_flow.deliver(tick, agents)

        # Consume demand
        for agent in agents.values():
            agent.consume_demand()

        # Supply flow — fixed, no coordination
        supply_flow.compute_flow(tick, agents)

        # Each tier checks locally — no reporting
        for agent in agents.values():
            agent.check_local_disruption()

        # Track disruption start and recovery
        any_disrupted = any(a.disrupted == 1 for a in agents.values())
        if any_disrupted and disruption_start is None:
            disruption_start = current_time
        if not any_disrupted and disruption_start and not recovery_time:
            recovery_time = current_time

        # Log retail state
        for tier, agent in agents.items():
            entry = {
                "tick"     : tick,
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M"),
                "node_id"  : agent.node_id,
                "node_type": tier,
                "disrupted": agent.disrupted,
                "mode"     : "reactive",
            }
            if tier == "retail":
                entry.update({
                    "retail_inventory" : agent.db_state.get("retail_inventory"),
                    "safety_stock"     : agent.db_state.get("safety_stock"),
                    "stockout_flag"    : agent.db_state.get("stockout_flag", 0),
                    "shortage_duration": agent.db_state.get("shortage_duration", 0),
                    "sales_rate"       : agent.db_state.get("sales_rate"),
                    "reorder_request"  : 0,
                })
            elif tier == "wholesaler":
                entry["inventory_level"]   = agent.db_state.get("inventory_level")
                entry["pending_shipments"] = agent.db_state.get("pending_shipments", 0)
            elif tier == "farm":
                entry["production_capacity"] = agent.db_state.get("production_capacity")
                entry["mortality_rate"]      = agent.db_state.get("mortality_rate")
            elif tier == "slaughterhouse":
                entry["processing_capacity"] = agent.db_state.get("processing_capacity")
                entry["output_stock"]        = agent.db_state.get("output_stock")
            elif tier == "supplier":
                entry["available_supply"]    = agent.db_state.get("available_supply")
            stock_log.append(entry)

    # Calculate metrics
    df     = pd.DataFrame(stock_log)
    retail = df[df["node_type"] == "retail"].copy()

    sar_threshold = csv_loader.get_sar_threshold("retail") if csv_loader else 30.0
    SAR = (retail["retail_inventory"] >= sar_threshold).mean() * 100 \
          if len(retail) else 0.0

    TTR = None
    if disruption_start and recovery_time:
        TTR = (recovery_time - disruption_start).total_seconds() / 3600

    flags = retail["stockout_flag"].values if "stockout_flag" in retail.columns \
            else np.zeros(len(retail))
    SOD = float(flags.sum()) * TICK_HOURS
    SOF = int(np.sum((flags[1:] == 1) & (flags[:-1] == 0)))
    min_stock = float(retail["retail_inventory"].min()) if len(retail) else 0.0
    max_ttr   = scenario.get("duration_hours", 96)
    RSI       = round(1 - TTR / max_ttr, 4) if TTR else None

    recovery_inv = float(
        retail[retail["disrupted"]==0]["retail_inventory"].mean()
    ) if len(retail[retail["disrupted"]==0]) > 0 else 0.0

    metrics = {
        "scenario_id"                 : scenario["scenario_id"],
        "disruption_type"             : scenario["disruption_type"],
        "subtype"                     : scenario.get("subtype",""),
        "severity"                    : scenario["severity"],
        "seed_node"                   : scenario["seed_node"],
        "cascade_depth"               : scenario.get("cascade_depth", 1),
        "SAR_threshold_used"          : round(sar_threshold, 2),
        "Stock Availability Rate (%)" : round(SAR, 3),
        "Time to Recovery (hours)"    : round(TTR, 2) if TTR else None,
        "Stockout Duration (hours)"   : round(SOD, 2),
        "Stockout Frequency"          : SOF,
        "Min Stock During Disruption" : round(min_stock, 2),
        "Recovery Speed Index"        : RSI,
        "Mean Recovery Inventory (kg)": round(recovery_inv, 2),
        "mode"                        : "reactive",
        "rules_source"                : "custom" if use_custom_rules else "default",
        "rules_used"                  : {
            "reorder_policy"         : {
                tier: {
                    "threshold_ratio"  : round(rules["reorder_policy"][tier]["threshold_ratio"], 4),
                    "reorder_qty_ratio": round(rules["reorder_policy"][tier]["reorder_qty_ratio"], 4),
                }
                for tier in CHAIN_ORDER
            },
            "restock_interval"       : rules["restock_interval"],
            "fixed_disruption_factor": rules["fixed_disruption_factor"],
        },
    }

    if verbose:
        print(f"    SAR={SAR:.1f}% | TTR={TTR}h | SOD={SOD:.1f}h")

    return metrics, df
