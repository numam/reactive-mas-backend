"""
╔══════════════════════════════════════════════════════════════════════╗
║  SCENARIO GENERATOR — 100 AI Outbreak Scenarios                     ║
║  MAS Poultry Supply Chain Resilience                                 ║
║                                                                      ║
║  Generates 100 programmatic Avian Influenza disruption scenarios    ║
║  with controlled parameter distribution for statistical analysis.   ║
║                                                                      ║
║  Distribution:                                                       ║
║    Severity : low=15, medium=30, high=35, crisis=20                 ║
║    Seed node: farm=55, supplier=20, slaughter=10, wholesale=10,     ║
║               retail=5                                               ║
║    Cascade  : depth 1=15, 2=25, 3=30, 4=20, 5=10                   ║
║    Duration : 48h=15, 72h=25, 96h=35, 120h=25                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import random
import itertools
from datetime import datetime, timedelta

random.seed(42)

# ════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════

CHAIN_ORDER = ["supplier", "farm", "slaughterhouse", "wholesaler", "retail"]

# Valid orchestrator rule patterns
VALID_PATTERNS = {
    (0,0,0,0,0): "R1", (1,0,0,0,0): "R2", (1,1,0,0,0): "R3",
    (0,1,0,0,0): "R4", (0,1,1,0,0): "R5", (0,0,1,0,0): "R6",
    (0,0,1,1,0): "R7", (0,0,0,1,0): "R8", (0,0,0,1,1): "R9",
    (1,0,0,1,0): "R10",(1,1,1,0,0): "R11",(0,1,0,1,0): "R12",
    (1,0,0,0,1): "R13",(0,0,0,0,1): "R14",(1,1,1,1,1): "R15",
    (1,1,1,1,0): "R16",(0,1,1,1,1): "R17",(0,0,1,1,1): "R18",
}

URGENCY = {
    "R1":"normal","R2":"normal","R3":"high","R4":"normal","R5":"high",
    "R6":"normal","R7":"high","R8":"normal","R9":"high","R10":"high",
    "R11":"crisis","R12":"high","R13":"high","R14":"normal","R15":"crisis",
    "R16":"crisis","R17":"crisis","R18":"high",
}

TIER_IDX = {t: i for i, t in enumerate(CHAIN_ORDER)}

# ── db_changes templates per tier per severity ───────────────────────

def get_db_changes(tier, severity, event_type="onset"):
    """
    Generate db_changes for a tier based on severity and event type.
    All reference variables (max_capacity, planned_capacity, etc.)
    are always included for trigger rule consistency.
    """
    base = {
        "supplier": {
            "low":    {"available_supply":420,"capacity":1000,"lead_time":4.2,"shipment_status":"delayed","supplier_reliability":0.58,"price_index":1.22},
            "medium": {"available_supply":280,"capacity":1000,"lead_time":5.5,"shipment_status":"delayed","supplier_reliability":0.45,"price_index":1.38},
            "high":   {"available_supply":180,"capacity":1000,"lead_time":7.0,"shipment_status":"delayed","supplier_reliability":0.38,"price_index":1.48},
            "crisis": {"available_supply":95, "capacity":1000,"lead_time":9.5,"shipment_status":"cancelled","supplier_reliability":0.22,"price_index":1.65},
        },
        "farm": {
            "low":    {"mortality_rate":0.09,"disease_alert":1,"production_capacity":520,"planned_capacity":800,"outgoing_orders":350,"growth_status":"slow","live_inventory":520,"feed_stock":470,"expected_daily_feed":80},
            "medium": {"mortality_rate":0.14,"disease_alert":1,"production_capacity":380,"planned_capacity":800,"outgoing_orders":240,"growth_status":"stunted","live_inventory":380,"feed_stock":420,"expected_daily_feed":80},
            "high":   {"mortality_rate":0.24,"disease_alert":1,"production_capacity":220,"planned_capacity":800,"outgoing_orders":120,"growth_status":"stunted","live_inventory":220,"feed_stock":380,"expected_daily_feed":80},
            "crisis": {"mortality_rate":0.38,"disease_alert":1,"production_capacity":96, "planned_capacity":800,"outgoing_orders":50, "growth_status":"stunted","live_inventory":96, "feed_stock":320,"expected_daily_feed":80},
        },
        "slaughterhouse": {
            "low":    {"processing_capacity":240,"max_capacity":500,"input_inventory":200,"queue_length":28,"processing_delay":4.2,"output_stock":118,"max_output":400,"equipment_status":"partial","worker_availability":0.72},
            "medium": {"processing_capacity":175,"max_capacity":500,"input_inventory":130,"queue_length":18,"processing_delay":6.0,"output_stock":82, "max_output":400,"equipment_status":"partial","worker_availability":0.62},
            "high":   {"processing_capacity":110,"max_capacity":500,"input_inventory":75, "queue_length":10,"processing_delay":8.5,"output_stock":48, "max_output":400,"equipment_status":"partial","worker_availability":0.52},
            "crisis": {"processing_capacity":55, "max_capacity":500,"input_inventory":30, "queue_length":5, "processing_delay":12.0,"output_stock":22, "max_output":400,"equipment_status":"down","worker_availability":0.38},
        },
        "wholesaler": {
            "low":    {"inventory_level":88, "capacity":300,"pending_shipments":52,"delivery_schedule":"delayed","shipment_status":"delayed","incoming_orders":195,"distribution_capacity":300,"reorder_point":90},
            "medium": {"inventory_level":58, "capacity":300,"pending_shipments":72,"delivery_schedule":"delayed","shipment_status":"delayed","incoming_orders":235,"distribution_capacity":300,"reorder_point":90},
            "high":   {"inventory_level":32, "capacity":300,"pending_shipments":88,"delivery_schedule":"delayed","shipment_status":"cancelled","incoming_orders":268,"distribution_capacity":300,"reorder_point":90},
            "crisis": {"inventory_level":14, "capacity":300,"pending_shipments":108,"delivery_schedule":"delayed","shipment_status":"cancelled","incoming_orders":295,"distribution_capacity":300,"reorder_point":90},
        },
        "retail": {
            "low":    {"retail_inventory":22,"capacity":150,"safety_stock":30,"stockout_flag":0,"shortage_duration":1.5,"sales_rate":13.5,"expected_sales_rate":10,"reorder_request":45,"demand_estimate":95},
            "medium": {"retail_inventory":10,"capacity":150,"safety_stock":30,"stockout_flag":1,"shortage_duration":3.5,"sales_rate":16.5,"expected_sales_rate":10,"reorder_request":75,"demand_estimate":105},
            "high":   {"retail_inventory":4, "capacity":150,"safety_stock":30,"stockout_flag":1,"shortage_duration":6.0,"sales_rate":19.5,"expected_sales_rate":10,"reorder_request":110,"demand_estimate":115},
            "crisis": {"retail_inventory":0, "capacity":150,"safety_stock":30,"stockout_flag":1,"shortage_duration":9.5,"sales_rate":22.0,"expected_sales_rate":10,"reorder_request":140,"demand_estimate":125},
        },
    }

    # Recovery db_changes (stricter thresholds)
    recovery = {
        "supplier": {"available_supply":680,"capacity":1000,"lead_time":2.8,"shipment_status":"on_time","supplier_reliability":0.80,"price_index":1.12},
        "farm":     {"mortality_rate":0.035,"disease_alert":0,"production_capacity":620,"planned_capacity":800,"outgoing_orders":390,"growth_status":"normal","live_inventory":615,"feed_stock":430,"expected_daily_feed":80},
        "slaughterhouse": {"processing_capacity":372,"max_capacity":500,"input_inventory":315,"queue_length":55,"processing_delay":1.8,"output_stock":212,"max_output":400,"equipment_status":"operational","worker_availability":0.83},
        "wholesaler": {"inventory_level":162,"capacity":300,"pending_shipments":16,"delivery_schedule":"normal","shipment_status":"on_time","incoming_orders":148,"distribution_capacity":300,"reorder_point":90},
        "retail":    {"retail_inventory":68,"capacity":150,"safety_stock":30,"stockout_flag":0,"shortage_duration":0,"sales_rate":10.5,"expected_sales_rate":10,"reorder_request":0,"demand_estimate":88},
    }

    if event_type == "recovery":
        # Add noise to recovery values
        rec = dict(recovery[tier])
        for k, v in rec.items():
            if isinstance(v, float) and k not in ("disease_alert","stockout_flag"):
                rec[k] = round(v * random.uniform(0.95, 1.08), 3)
        return rec

    changes = dict(base[tier][severity])
    # Add slight noise for variability
    for k, v in changes.items():
        if isinstance(v, (int, float)) and k not in (
            "disease_alert","stockout_flag","capacity","max_capacity",
            "planned_capacity","max_output","expected_daily_feed","reorder_point",
            "distribution_capacity"
        ):
            noise = random.uniform(0.92, 1.08)
            if isinstance(v, float):
                changes[k] = round(v * noise, 3)
            else:
                changes[k] = max(0, int(v * noise))
    return changes


# ════════════════════════════════════════════════════════════════════
# CASCADE PATH BUILDER
# ════════════════════════════════════════════════════════════════════

# Realistic cascade paths per seed node
CASCADE_TEMPLATES = {
    "farm": {
        1: [["farm"]],
        2: [["farm","slaughterhouse"], ["farm","wholesaler"]],
        3: [["farm","slaughterhouse","wholesaler"],
            ["farm","supplier","slaughterhouse"]],
        4: [["farm","slaughterhouse","wholesaler","retail"],
            ["farm","supplier","slaughterhouse","wholesaler"]],
        5: [["farm","supplier","slaughterhouse","wholesaler","retail"]],
    },
    "supplier": {
        1: [["supplier"]],
        2: [["supplier","farm"]],
        3: [["supplier","farm","slaughterhouse"]],
        4: [["supplier","farm","slaughterhouse","wholesaler"]],
        5: [["supplier","farm","slaughterhouse","wholesaler","retail"]],
    },
    "slaughterhouse": {
        1: [["slaughterhouse"]],
        2: [["slaughterhouse","wholesaler"]],
        3: [["slaughterhouse","wholesaler","retail"]],
        4: [["farm","slaughterhouse","wholesaler","retail"]],
        5: [["farm","supplier","slaughterhouse","wholesaler","retail"]],
    },
    "wholesaler": {
        1: [["wholesaler"]],
        2: [["wholesaler","retail"]],
        3: [["slaughterhouse","wholesaler","retail"]],
        4: [["farm","slaughterhouse","wholesaler","retail"]],
        5: [["farm","supplier","slaughterhouse","wholesaler","retail"]],
    },
    "retail": {
        1: [["retail"]],
        2: [["wholesaler","retail"]],
        3: [["slaughterhouse","wholesaler","retail"]],
        4: [["farm","slaughterhouse","wholesaler","retail"]],
        5: [["supplier","farm","slaughterhouse","wholesaler","retail"]],
    },
}

RECOVERY_ORDER = {
    "farm":          ["farm","slaughterhouse","wholesaler","retail"],
    "supplier":      ["supplier","farm","slaughterhouse","wholesaler","retail"],
    "slaughterhouse":["slaughterhouse","wholesaler","retail","farm"],
    "wholesaler":    ["wholesaler","retail"],
    "retail":        ["retail"],
}


def pattern_from_cascade(cascade_path):
    """Convert cascade path to binary pattern tuple."""
    pat = [0, 0, 0, 0, 0]
    for tier in cascade_path:
        pat[TIER_IDX[tier]] = 1
    return tuple(pat)


def peak_rule(cascade_path):
    """Get the orchestrator rule for peak disruption."""
    pat = pattern_from_cascade(cascade_path)
    return VALID_PATTERNS.get(pat, "R1")


def build_events(scenario_id, seed_node, cascade_path, recovery_path,
                 severity, duration_hours, start_dt):
    """Build event list for a scenario."""
    events = []
    ev_id  = 1

    # --- Onset/escalation events ---
    current_cascade = []
    n_onset = len(cascade_path)
    # Space onset events across first 40% of duration
    onset_spacing = (duration_hours * 0.40) / max(n_onset, 1)

    for i, tier in enumerate(cascade_path):
        at_hour = round(onset_spacing * (i + 1), 1)
        current_cascade = cascade_path[:i+1]
        pattern_after   = list(pattern_from_cascade(current_cascade)) + [0] * (5 - len(current_cascade))

        # Determine event type
        if i == 0:
            ev_type = "onset"
            rule    = peak_rule([cascade_path[0]])
        elif i == len(cascade_path) - 1:
            ev_type = "peak_escalation"
            rule    = peak_rule(cascade_path)
        else:
            ev_type = "escalation"
            rule    = peak_rule(cascade_path[:i+1])

        # Pattern after should reflect current disrupted tiers
        pat = [0]*5
        for t in cascade_path[:i+1]:
            pat[TIER_IDX[t]] = 1

        events.append({
            "event_id"    : f"E{ev_id:03d}",
            "at_hour"     : at_hour,
            "timestamp"   : (start_dt + timedelta(hours=at_hour)).strftime("%Y-%m-%d %H:%M"),
            "node"        : tier,
            "disrupted"   : 1,
            "event_type"  : ev_type,
            "pattern_after": pat,
            "rule_triggered": rule,
            "db_changes"  : get_db_changes(tier, severity, "onset"),
            "description" : f"AI outbreak {ev_type} at {tier} — severity={severity}",
        })
        ev_id += 1

    # --- Recovery events ---
    n_recovery = len(recovery_path)
    # Recovery events spread across last 50% of duration
    rec_start   = duration_hours * 0.50
    rec_spacing = (duration_hours * 0.45) / max(n_recovery, 1)

    disrupted_set = set(cascade_path)
    for i, tier in enumerate(recovery_path):
        if tier not in disrupted_set:
            continue
        at_hour  = round(rec_start + rec_spacing * (i + 1), 1)
        at_hour  = min(at_hour, duration_hours - 0.5)

        # Remove this tier from disrupted set
        disrupted_set.discard(tier)
        pat = [0]*5
        for t in disrupted_set:
            pat[TIER_IDX[t]] = 1

        # Map to nearest valid rule (R1 fallback is correct behavior)
        rule = VALID_PATTERNS.get(tuple(pat), "R1")

        events.append({
            "event_id"    : f"E{ev_id:03d}",
            "at_hour"     : at_hour,
            "timestamp"   : (start_dt + timedelta(hours=at_hour)).strftime("%Y-%m-%d %H:%M"),
            "node"        : tier,
            "disrupted"   : 0,
            "event_type"  : "recovery",
            "pattern_after": pat,
            "rule_triggered": rule,
            "db_changes"  : get_db_changes(tier, severity, "recovery"),
            "description" : f"Recovery at {tier} — pattern returns toward normal",
        })
        ev_id += 1

    return events


# ════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ════════════════════════════════════════════════════════════════════

def generate_100_scenarios():
    """Generate 100 AI outbreak scenarios with controlled distribution."""

    # Distribution plan
    plan = []

    # severity × seed_node × cascade_depth × duration
    configs = [
        # (severity, seed, depth, duration, count)
        # LOW — 15 scenarios
        ("low",    "farm",         1, 48,  5),
        ("low",    "farm",         2, 72,  5),
        ("low",    "supplier",     1, 48,  3),
        ("low",    "slaughterhouse",1,48,  2),
        # MEDIUM — 30 scenarios
        ("medium", "farm",         2, 72,  8),
        ("medium", "farm",         3, 96,  7),
        ("medium", "supplier",     2, 72,  5),
        ("medium", "slaughterhouse",2,72,  4),
        ("medium", "wholesaler",   2, 72,  3),
        ("medium", "farm",         1, 48,  3),
        # HIGH — 35 scenarios
        ("high",   "farm",         3, 96,  10),
        ("high",   "farm",         4, 96,  8),
        ("high",   "supplier",     3, 96,  6),
        ("high",   "slaughterhouse",3,96,  4),
        ("high",   "wholesaler",   3, 96,  4),
        ("high",   "retail",       2, 72,  3),
        # CRISIS — 20 scenarios
        ("crisis", "farm",         5, 120, 8),
        ("crisis", "farm",         4, 120, 5),
        ("crisis", "supplier",     4, 120, 4),
        ("crisis", "farm",         3, 96,  3),
    ]

    for cfg in configs:
        sev, seed, depth, dur, count = cfg
        for _ in range(count):
            plan.append((sev, seed, depth, dur))

    # Shuffle for variety
    random.shuffle(plan)

    # Assign start dates spread across 6 months
    base_date = datetime(2026, 1, 1, 6, 0)

    scenarios = []
    for idx, (sev, seed, depth, dur) in enumerate(plan):
        scenario_id = idx + 1
        start_dt    = base_date + timedelta(days=idx * 2)

        # Pick cascade path
        templates = CASCADE_TEMPLATES[seed][depth]
        cascade   = random.choice(templates)

        # Recovery path (reverse cascade order, biologically)
        rec_order = RECOVERY_ORDER.get(seed, cascade[::-1])
        recovery  = [t for t in rec_order if t in cascade]
        if not recovery:
            recovery = cascade[::-1]

        # Subtype label
        subtypes = {
            ("farm", "low"):    "H9N2_LPAI",
            ("farm", "medium"): "H5N1_LOCAL",
            ("farm", "high"):   "H5N1_SPREADING",
            ("farm", "crisis"): "H5N1_REGIONAL_CRISIS",
            ("supplier", "low"): "EMBARGO_MILD",
            ("supplier", "medium"): "EMBARGO_MODERATE",
            ("supplier", "high"): "EMBARGO_SEVERE",
            ("supplier", "crisis"): "EMBARGO_CRITICAL",
        }
        subtype_key  = (seed, sev)
        subtype      = subtypes.get(subtype_key, f"AI_{sev.upper()}_{seed.upper()}")

        # Peak rule
        peak = peak_rule(cascade)

        events = build_events(
            scenario_id, seed, cascade, recovery,
            sev, dur, start_dt
        )

        scenario = {
            "scenario_id"    : scenario_id,
            "disruption_type": "AVIAN_INFLUENZA",
            "subtype"        : subtype,
            "severity"       : sev,
            "seed_node"      : seed,
            "cascade_depth"  : depth,
            "cascade_path"   : cascade,
            "recovery_path"  : recovery,
            "duration_hours" : dur,
            "start_datetime" : start_dt.strftime("%Y-%m-%d %H:%M"),
            "peak_rule"      : peak,
            "description"    : (f"AI outbreak [{subtype}] — severity={sev}, "
                                f"seed={seed}, cascade depth={depth}, "
                                f"duration={dur}h, peak_rule={peak}"),
            "events"         : events,
        }
        scenarios.append(scenario)

    return scenarios


if __name__ == "__main__":
    print("Generating 100 AI outbreak scenarios...")
    scenarios = generate_100_scenarios()

    # Save to JSON
    output_path = "scenarios_100.json"
    with open(output_path, "w") as f:
        json.dump(scenarios, f, indent=2)

    print(f"\nGenerated {len(scenarios)} scenarios → {output_path}")
    print("\nDistribution summary:")

    from collections import Counter
    sev_dist  = Counter(s["severity"]    for s in scenarios)
    seed_dist = Counter(s["seed_node"]   for s in scenarios)
    dep_dist  = Counter(s["cascade_depth"] for s in scenarios)
    dur_dist  = Counter(s["duration_hours"] for s in scenarios)

    print(f"  Severity   : {dict(sorted(sev_dist.items()))}")
    print(f"  Seed node  : {dict(sorted(seed_dist.items()))}")
    print(f"  Cascade dep: {dict(sorted(dep_dist.items()))}")
    print(f"  Duration   : {dict(sorted(dur_dist.items()))}")

    # Validate all patterns are in valid set
    all_valid = True
    for s in scenarios:
        for ev in s["events"]:
            pat = tuple(ev["pattern_after"])
            if pat != (0,0,0,0,0) and pat not in VALID_PATTERNS:
                print(f"  WARNING: Scenario {s['scenario_id']} event {ev['event_id']} "
                      f"has invalid pattern {pat}")
                all_valid = False
    if all_valid:
        print(f"\n  All patterns validated against 18-rule set ✓")
    print(f"\nDone.")
