"""
╔══════════════════════════════════════════════════════════════════════╗
║  SIMULATION ENGINE v3 — Fixed Supply Flow & Proper HitL Effect      ║
║                                                                      ║
║  Root cause fixes:                                                   ║
║  [F1] Initial state taken from CSV row with adequate inventory       ║
║  [F2] Supply flow mechanism: upstream restocks downstream each N h  ║
║  [F3] HitL delay: instructions delayed by HRT before execution      ║
║  [F4] Disruption reduces supply flow (not just DB variables)        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from agent_database      import AGENT_DATABASE, init_node_state, get_monitoring_interval
from disruption_triggers import check_disruption, check_recovery
from orchestrator_rules  import ORCHESTRATOR_RULES, PATTERN_TO_RULE, apply_instructions
from scenario_loader     import get_disruption_schedule
from hitl_module         import HitLEngine

CHAIN_ORDER  = ["supplier","farm","slaughterhouse","wholesaler","retail"]
TICK_MINUTES = 15
TICK_HOURS   = TICK_MINUTES / 60

# ── Supply flow parameters ────────────────────────────────────────────
# How much stock flows from upstream to downstream per hour (normal)
SUPPLY_FLOW_RATE = {
    "supplier"       : 0,      # no upstream
    "farm"           : 0,      # receives from supplier (DOC/feed, not stock flow)
    "slaughterhouse" : 0,      # processes farm output
    "wholesaler"     : 12.0,   # kg/hour from slaughterhouse
    "retail"         : 8.0,    # kg/hour from wholesaler
}

# Restock interval (ticks) per tier
RESTOCK_INTERVAL = {
    "wholesaler": 8,   # every 2 hours
    "retail"    : 4,   # every 1 hour
}

# How disruption reduces supply flow (multiplier)
DISRUPTION_SUPPLY_FACTOR = {
    "low"   : 0.65,
    "medium": 0.40,
    "high"  : 0.18,
    "crisis": 0.05,
}


# ════════════════════════════════════════════════════════════════════
# CSV LOADER — Fixed initial state selection
# ════════════════════════════════════════════════════════════════════

class CSVDataLoader:
    def __init__(self, data_dir="."):
        self._cache    = {}
        self._baselines= {}
        self._data_dir = data_dir
        import os
        for tier in CHAIN_ORDER:
            path = os.path.join(data_dir, f"data_normal_{tier}.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                self._cache[tier] = df
                num = df.select_dtypes(include="number").columns
                num = [c for c in num if c not in
                       ("disrupted","disease_alert","stockout_flag","above_safety_stock")]
                self._baselines[tier] = df[num].mean().to_dict()

    def get_initial_state(self, tier: str,
                          rng: Optional[np.random.Generator] = None) -> dict:
        """[F1] Pick row with adequate inventory levels."""
        if tier not in self._cache:
            return init_node_state(tier)

        df  = self._cache[tier]
        schema = AGENT_DATABASE[tier]["variables"]

        # Filter for rows with adequate inventory
        if tier == "retail":
            # Start with inventory >= 60% capacity (well-stocked)
            ok = df[df["stock_ratio"] >= 0.55] if "stock_ratio" in df.columns else df
        elif tier == "wholesaler":
            ok = df[df["stock_ratio"] >= 0.55] if "stock_ratio" in df.columns else df
        elif tier == "farm":
            ok = df[df["production_ratio"] >= 0.85] if "production_ratio" in df.columns else df
        else:
            ok = df

        if len(ok) == 0:
            ok = df

        idx = int(rng.integers(0, len(ok))) if rng else 0
        row = ok.iloc[idx]

        state = init_node_state(tier)
        for col in schema:
            if col in row.index:
                val = row[col]
                if isinstance(val, float) and np.isnan(val):
                    continue
                state[col] = val
        state.pop("disrupted", None)
        return state

    def get_sar_threshold(self, tier="retail") -> float:
        """[M3] SAR threshold = 75% of historical mean."""
        if tier in self._baselines:
            key = "retail_inventory" if tier == "retail" else "inventory_level"
            mean = self._baselines[tier].get(key, 90)
            return round(mean * 0.75, 2)
        return 30.0

    def get_baselines(self, tier):
        return self._baselines.get(tier, {})


# ════════════════════════════════════════════════════════════════════
# NODE AGENT
# ════════════════════════════════════════════════════════════════════

class NodeAgent:
    def __init__(self, node_type, node_id, db_state):
        self.node_type  = node_type
        self.node_id    = node_id
        self.db_state   = dict(db_state)
        self.disrupted  = 0
        self._disruption_severity = None  # track current severity

    @property
    def interval_ticks(self):
        return max(1, int(get_monitoring_interval(self.node_type) / TICK_HOURS))

    def should_scan(self, tick):
        return tick % self.interval_ticks == 0

    def scan(self, tick, current_time, verbose=False):
        if not self.should_scan(tick):
            return None

        if self.disrupted == 0:
            result = check_disruption(self.node_type, self.db_state)
            if result["disrupted"] == 1:
                self.disrupted = 1
                if verbose:
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"⚠  {self.node_id} DISRUPTED — {result['event_types']}")
                return {
                    "type"        : "DisruptionReport",
                    "node_id"     : self.node_id,
                    "node_type"   : self.node_type,
                    "timestamp"   : current_time,
                    "disrupted"   : 1,
                    "triggered_by": result["triggered_by"],
                    "event_types" : result["event_types"],
                    "db_snapshot" : dict(self.db_state),
                }
        elif self.disrupted == 1:
            if check_recovery(self.node_type, self.db_state):
                self.disrupted = 0
                self._disruption_severity = None
                if verbose:
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"✓  {self.node_id} RECOVERED")
                return {
                    "type"       : "RecoveryReport",
                    "node_id"    : self.node_id,
                    "node_type"  : self.node_type,
                    "timestamp"  : current_time,
                    "disrupted"  : 0,
                    "db_snapshot": dict(self.db_state),
                }
        return None

    def apply_instruction(self, instructions):
        updated, _ = apply_instructions(self.node_type, self.db_state, instructions)
        self.db_state = updated

    def consume_demand(self):
        """Update DB: consumption per tick."""
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

    def receive_restock(self, amount: float):
        """[F2] Receive physical stock from upstream."""
        nt = self.node_type
        if nt == "retail":
            cap = self.db_state.get("capacity", 150)
            inv = self.db_state.get("retail_inventory", 0)
            self.db_state["retail_inventory"] = round(min(cap, inv + amount), 2)
        elif nt == "wholesaler":
            cap = self.db_state.get("capacity", 300)
            inv = self.db_state.get("inventory_level", 0)
            self.db_state["inventory_level"] = round(min(cap, inv + amount), 2)

    def inject_disruption(self, db_changes):
        self.db_state.update(db_changes)
        # Detect severity from db_changes
        if "mortality_rate" in db_changes:
            mr = db_changes["mortality_rate"]
            if   mr >= 0.30: self._disruption_severity = "crisis"
            elif mr >= 0.18: self._disruption_severity = "high"
            elif mr >= 0.10: self._disruption_severity = "medium"
            else:            self._disruption_severity = "low"
        result = check_disruption(self.node_type, self.db_state)
        if result["disrupted"] == 1:
            self.disrupted = 1
        if check_recovery(self.node_type, self.db_state):
            self.disrupted = 0


# ════════════════════════════════════════════════════════════════════
# COORDINATING AGENT
# ════════════════════════════════════════════════════════════════════

class CoordinatingAgent:
    def __init__(self):
        self.agent_status     = {t: 0 for t in CHAIN_ORDER}
        self.event_log        = []
        self.action_log       = []
        self.disruption_start = None
        self.recovery_time    = None
        self._log_id          = 1

    @property
    def global_pattern(self):
        return tuple(self.agent_status[t] for t in CHAIN_ORDER)

    def _match_rule(self):
        rule_id = PATTERN_TO_RULE.get(self.global_pattern, "R1")
        return rule_id, ORCHESTRATOR_RULES[rule_id]

    def receive_report(self, report, agents, verbose=False):
        node_type = report["node_type"]
        ts        = report["timestamp"]
        self.agent_status[node_type] = report["disrupted"]

        if report["disrupted"] == 1 and self.disruption_start is None:
            self.disruption_start = ts

        rule_id, rule = self._match_rule()
        if rule_id == "R1" and self.disruption_start and not self.recovery_time:
            self.recovery_time = ts

        self.event_log.append({
            "log_id"               : f"L{self._log_id:03d}",
            "timestamp"            : ts.strftime("%Y-%m-%d %H:%M"),
            "supplier"             : self.agent_status["supplier"],
            "farm"                 : self.agent_status["farm"],
            "slaughterhouse"       : self.agent_status["slaughterhouse"],
            "wholesaler"           : self.agent_status["wholesaler"],
            "retail"               : self.agent_status["retail"],
            "matched_rule"         : rule_id,
            "orchestrator_decision": rule["decision"],
            "urgency_level"        : rule["urgency"],
            "justification"        : rule["justification"],
            "report_type"          : report["type"],
        })
        self._log_id += 1

        if verbose:
            print(f"    [{ts.strftime('%H:%M')}] 🧠 {rule_id} | "
                  f"{rule['decision']} | {rule['urgency']}")

        signals = []
        for tier, instructions in rule["instructions"].items():
            if instructions and tier in agents:
                signals.append({
                    "target_node" : agents[tier].node_id,
                    "target_type" : tier,
                    "rule_id"     : rule_id,
                    "urgency"     : rule["urgency"],
                    "instructions": instructions,
                    "timestamp"   : ts,
                })
        return signals


# ════════════════════════════════════════════════════════════════════
# SUPPLY FLOW ENGINE — [F2] Physical stock movement between tiers
# ════════════════════════════════════════════════════════════════════

class SupplyFlowEngine:
    """
    Models physical stock flow from upstream to downstream tiers.
    Flow rate is reduced when upstream tiers are disrupted.
    This creates meaningful difference between Autonomous and HitL:
    - Autonomous: coordinator instructions improve flow immediately
    - HitL: instructions are delayed by HRT → slower recovery
    """

    def __init__(self):
        # Pending restocks: {tick_to_deliver: [(tier, amount)]}
        self._pending = defaultdict(list)

    def schedule_restock(self, tick: int, tier: str, amount: float,
                          delay_ticks: int = 0):
        """Schedule a restock delivery at tick + delay."""
        deliver_at = tick + max(0, delay_ticks)
        self._pending[deliver_at].append((tier, amount))

    def deliver(self, tick: int, agents: dict) -> dict:
        """Deliver all pending restocks for this tick."""
        delivered = {}
        if tick in self._pending:
            for tier, amount in self._pending[tick]:
                if tier in agents and amount > 0:
                    agents[tier].receive_restock(amount)
                    delivered[tier] = delivered.get(tier, 0) + amount
            del self._pending[tick]
        return delivered

    def compute_flow(self, tick: int, agents: dict,
                     mode: str = "autonomous",
                     pending_signals: dict = None) -> None:
        """
        Compute and schedule supply flows for this tick.
        KEY DIFFERENCE vs Reactive:
        - MAS Autonomous: reorder_request raised by coordinator → amplifies flow
        - MAS HitL: same but with HRT delay
        - Reactive: no reorder_request signal → base flow only
        pending_signals: {tier: delay_ticks} from HitL decisions
        """
        if pending_signals is None:
            pending_signals = {}

        # Wholesaler → Retail flow
        if tick % RESTOCK_INTERVAL["retail"] == 0:
            ws_agent = agents.get("wholesaler")
            rt_agent = agents.get("retail")
            if ws_agent and rt_agent:
                ws_inv = ws_agent.db_state.get("inventory_level", 200)
                rt_inv = rt_agent.db_state.get("retail_inventory", 90)
                rt_cap = rt_agent.db_state.get("capacity", 150)
                rt_ss  = rt_agent.db_state.get("safety_stock", 30)

                # Only restock if retail needs it and wholesaler has stock
                restock_needed = max(0, rt_cap * 0.70 - rt_inv)
                if restock_needed > 0 and ws_inv > rt_ss:
                    # Base flow rate
                    base_flow = SUPPLY_FLOW_RATE["retail"] * TICK_HOURS * RESTOCK_INTERVAL["retail"]

                    # ── MAS vs Reactive key difference ──────────────────────
                    # MAS: coordinator raises reorder_request → emergency supply override
                    # Reactive: no signal → supply capped by disruption factor
                    reorder_req = rt_agent.db_state.get("reorder_request", 0)

                    if reorder_req > 0:
                        # MAS AUTONOMOUS/HitL PATH:
                        # Coordinator raised reorder_request → amplify AND bypass disruption caps
                        amplify    = min(2.5, 1.0 + reorder_req / rt_cap)
                        flow_final = base_flow * amplify
                        # Farm/slaughter disruption still reduces but less severely
                        if agents.get("farm") and agents["farm"].disrupted == 1:
                            flow_final *= 0.80
                        if agents.get("slaughterhouse") and agents["slaughterhouse"].disrupted == 1:
                            flow_final *= 0.70
                        amount = round(min(ws_inv * 0.55, restock_needed, flow_final), 2)
                    else:
                        # REACTIVE PATH:
                        # No coordination signal → apply all disruption caps normally
                        if ws_agent.disrupted == 1:
                            sev = ws_agent._disruption_severity or "high"
                            factor = DISRUPTION_SUPPLY_FACTOR.get(sev, 0.18)
                            base_flow *= factor
                        if agents.get("farm") and agents["farm"].disrupted == 1:
                            base_flow *= 0.60
                        if agents.get("slaughterhouse") and agents["slaughterhouse"].disrupted == 1:
                            base_flow *= 0.50
                        amount = round(min(ws_inv * 0.40, restock_needed, base_flow), 2)

                    if amount > 0:
                        # HitL delay: add HRT delay to delivery
                        delay = 0
                        if mode == "hitl":
                            hrt_hours = pending_signals.get("wholesaler_to_retail_hrt", 0)
                            delay = int(hrt_hours / TICK_HOURS)
                        self.schedule_restock(tick, "retail", amount, max(1, delay))
                        # Deduct from wholesaler
                        ws_agent.db_state["inventory_level"] = round(
                            max(0, ws_inv - amount), 2)

        # Slaughterhouse → Wholesaler flow
        if tick % RESTOCK_INTERVAL["wholesaler"] == 0:
            sh_agent = agents.get("slaughterhouse")
            ws_agent = agents.get("wholesaler")
            if sh_agent and ws_agent:
                sh_out  = sh_agent.db_state.get("output_stock", 300)
                ws_inv  = ws_agent.db_state.get("inventory_level", 200)
                ws_cap  = ws_agent.db_state.get("capacity", 300)

                restock_needed = max(0, ws_cap * 0.70 - ws_inv)
                if restock_needed > 0 and sh_out > 50:
                    base_flow = SUPPLY_FLOW_RATE["wholesaler"] * TICK_HOURS * RESTOCK_INTERVAL["wholesaler"]

                    if sh_agent.disrupted == 1:
                        sev = sh_agent._disruption_severity or "high"
                        factor = DISRUPTION_SUPPLY_FACTOR.get(sev, 0.18)
                        base_flow *= factor

                    amount = round(min(sh_out * 0.40, restock_needed, base_flow), 2)
                    if amount > 0:
                        delay = 0
                        if mode == "hitl":
                            hrt_hours = pending_signals.get("slaughter_to_wholesaler_hrt", 0)
                            delay = int(hrt_hours / TICK_HOURS)
                        self.schedule_restock(tick, "wholesaler", amount, max(1, delay))
                        sh_agent.db_state["output_stock"] = round(
                            max(0, sh_out - amount), 2)


# ════════════════════════════════════════════════════════════════════
# METRICS
# ════════════════════════════════════════════════════════════════════

def calculate_metrics(stock_log, coordinator, scenario,
                      hitl_engine=None, csv_loader=None):
    df     = pd.DataFrame(stock_log)
    retail = df[df["node_type"] == "retail"].copy() if not df.empty else pd.DataFrame()

    # [M3] SAR threshold from CSV baseline
    if csv_loader:
        sar_threshold = csv_loader.get_sar_threshold("retail")
    else:
        sar_threshold = 30.0

    SAR = (retail["retail_inventory"] >= sar_threshold).mean() * 100 \
          if len(retail) else 0.0

    TTR = None
    if coordinator.disruption_start and coordinator.recovery_time:
        TTR = (coordinator.recovery_time
               - coordinator.disruption_start).total_seconds() / 3600

    flags = retail["stockout_flag"].values if "stockout_flag" in retail.columns \
            else np.zeros(len(retail))
    SOD = float(flags.sum()) * TICK_HOURS
    SOF = int(np.sum((flags[1:] == 1) & (flags[:-1] == 0)))
    min_stock = float(retail["retail_inventory"].min()) if len(retail) else 0.0
    max_ttr   = scenario.get("duration_hours", 96)
    RSI       = round(1 - TTR / max_ttr, 4) if TTR else None

    # Peak inventory during recovery (indicator of recovery quality)
    recovery_inv = float(retail[retail["disrupted"]==0]["retail_inventory"].mean()) \
                   if len(retail[retail["disrupted"]==0]) > 0 else 0.0

    metrics = {
        "scenario_id"                 : scenario["scenario_id"],
        "disruption_type"             : scenario["disruption_type"],
        "subtype"                     : scenario.get("subtype",""),
        "severity"                    : scenario["severity"],
        "seed_node"                   : scenario["seed_node"],
        "cascade_depth"               : scenario.get("cascade_depth", len(scenario.get("cascade_path",[]))),
        "SAR_threshold_used"          : round(sar_threshold, 2),
        "Stock Availability Rate (%)" : round(SAR, 3),
        "Time to Recovery (hours)"    : round(TTR, 2) if TTR else None,
        "Stockout Duration (hours)"   : round(SOD, 2),
        "Stockout Frequency"          : SOF,
        "Min Stock During Disruption" : round(min_stock, 2),
        "Recovery Speed Index"        : RSI,
        "Mean Recovery Inventory (kg)": round(recovery_inv, 2),
        "Total Coordinator Events"    : len(coordinator.event_log),
    }

    if hitl_engine:
        s = hitl_engine.get_summary()
        metrics.update({
            "HitL_Accept_Rate_%"   : s.get("accept_rate_%"),
            "HitL_Modify_Rate_%"   : s.get("modify_rate_%"),
            "HitL_Override_Rate_%" : s.get("override_rate_%"),
            "HitL_Mean_HRT_hours"  : s.get("mean_HRT_hours"),
            "HitL_Modify_Factor"   : s.get("mean_modification_factor"),
        })

    return metrics


# ════════════════════════════════════════════════════════════════════
# MAIN SIMULATION RUNNER
# ════════════════════════════════════════════════════════════════════

def run_scenario(scenario, mode="autonomous", csv_loader=None,
                 verbose=False, rng_seed=None):
    """
    Run one scenario with proper supply flow and HitL delay mechanics.
    mode: "autonomous" | "hitl"
    """
    np.random.seed(rng_seed)
    rng         = np.random.default_rng(rng_seed)
    start_dt    = datetime.strptime(scenario["start_datetime"], "%Y-%m-%d %H:%M")
    total_ticks = int(scenario["duration_hours"] / TICK_HOURS)

    if verbose:
        print(f"\n{'═'*65}")
        print(f"  S{scenario['scenario_id']:03d} | {scenario.get('subtype','')} "
              f"| {scenario['severity']} | mode={mode.upper()}")
        print(f"{'═'*65}")

    # [F1] Initialize from CSV with adequate stock levels
    agents = {}
    for tier in CHAIN_ORDER:
        if csv_loader:
            db_state = csv_loader.get_initial_state(tier, rng)
        else:
            db_state = init_node_state(tier)
        agents[tier] = NodeAgent(
            node_type=tier,
            node_id  =AGENT_DATABASE[tier]["meta"]["node_id"],
            db_state =db_state,
        )

    coordinator  = CoordinatingAgent()
    hitl         = HitLEngine(rng_seed=rng_seed) if mode == "hitl" else None
    supply_flow  = SupplyFlowEngine()

    # Build disruption schedule
    schedule    = get_disruption_schedule(scenario["scenario_id"])
    disrupt_map = {}
    for ev in schedule:
        tk = int(ev["at_hour"] / TICK_HOURS)
        disrupt_map.setdefault(tk, []).append(ev)

    stock_log = []
    # Track HRT delays for supply flow
    hrt_delays = {}

    for tick in range(total_ticks):
        current_time = start_dt + timedelta(minutes=TICK_MINUTES * tick)

        # Step 1: Inject disruptions
        if tick in disrupt_map:
            for ev in disrupt_map[tick]:
                agents[ev["node"]].inject_disruption(ev.get("db_changes", {}))
                if verbose:
                    status = "DISRUPTED" if ev["disrupted"] else "RECOVERING"
                    print(f"\n  [{current_time.strftime('%Y-%m-%d %H:%M')}] "
                          f"📌 {ev.get('event_id','')} {ev['node'].upper()} {status}")

        # Step 2: Consume demand
        for agent in agents.values():
            agent.consume_demand()

        # Step 3: Supply flow delivery (deliver pending restocks from previous computation)
        supply_flow.deliver(tick, agents)

        # Step 4: Supply flow computation (schedule new restocks for next tick delivery)
        supply_flow.compute_flow(tick, agents, mode=mode,
                                  pending_signals=hrt_delays)

        # Step 5: Scan DB local
        reports = []
        for agent in agents.values():
            r = agent.scan(tick, current_time, verbose)
            if r:
                reports.append(r)

        # Step 6: Coordinator processes reports
        signals = []
        for report in reports:
            signals.extend(coordinator.receive_report(report, agents, verbose))

        # Step 7: HitL or autonomous instruction execution
        hrt_delays = {}
        for signal in signals:
            tier         = signal["target_type"]
            instructions = signal.get("instructions", [])
            if not instructions or tier not in agents:
                continue

            if mode == "hitl" and hitl:
                dec = hitl.process_signal(
                    signal, tick=tick,
                    timestamp=current_time.strftime("%Y-%m-%d %H:%M"),
                    urgency=signal.get("urgency","normal"),
                )
                final_inst = dec.final_instructions
                # [F3] HRT delay: store for supply flow computation
                if dec.response_time > 0:
                    hrt_delays[f"{tier}_hrt"] = dec.response_time
                    # Track wholesaler-retail specific delay
                    if tier == "wholesaler":
                        hrt_delays["wholesaler_to_retail_hrt"] = dec.response_time
                    if tier == "slaughterhouse":
                        hrt_delays["slaughter_to_wholesaler_hrt"] = dec.response_time
                if verbose and dec.decision != "accept":
                    print(f"    [{current_time.strftime('%H:%M')}] "
                          f"👤 {tier}: {dec.decision.upper()} "
                          f"factor={dec.modification_factor:.2f} "
                          f"HRT={dec.response_time:.2f}h")
            else:
                final_inst = instructions

            agents[tier].apply_instruction(final_inst)

        # Step 8: Log state
        for tier, agent in agents.items():
            entry = {
                "tick"     : tick,
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M"),
                "node_id"  : agent.node_id,
                "node_type": tier,
                "disrupted": agent.disrupted,
            }
            if tier == "retail":
                entry.update({
                    "retail_inventory" : agent.db_state.get("retail_inventory"),
                    "safety_stock"     : agent.db_state.get("safety_stock"),
                    "stockout_flag"    : agent.db_state.get("stockout_flag", 0),
                    "shortage_duration": agent.db_state.get("shortage_duration", 0),
                    "sales_rate"       : agent.db_state.get("sales_rate"),
                    "reorder_request"  : agent.db_state.get("reorder_request", 0),
                })
            elif tier == "wholesaler":
                entry["inventory_level"]   = agent.db_state.get("inventory_level")
                entry["pending_shipments"] = agent.db_state.get("pending_shipments")
            elif tier == "farm":
                entry["production_capacity"] = agent.db_state.get("production_capacity")
                entry["mortality_rate"]      = agent.db_state.get("mortality_rate")
            elif tier == "slaughterhouse":
                entry["processing_capacity"] = agent.db_state.get("processing_capacity")
                entry["output_stock"]        = agent.db_state.get("output_stock")
            elif tier == "supplier":
                entry["available_supply"]    = agent.db_state.get("available_supply")
            stock_log.append(entry)

    metrics  = calculate_metrics(stock_log, coordinator, scenario, hitl, csv_loader)
    stock_df = pd.DataFrame(stock_log)
    event_df = pd.DataFrame(coordinator.event_log)
    hitl_df  = hitl.get_log_df() if hitl else pd.DataFrame()

    if verbose:
        print(f"\n  ── Metrics ({mode.upper()}) ──")
        for k, v in metrics.items():
            if k not in ("scenario_id","disruption_type","subtype","seed_node"):
                print(f"    {k:<38}: {v}")

    return metrics, stock_df, event_df, hitl_df
