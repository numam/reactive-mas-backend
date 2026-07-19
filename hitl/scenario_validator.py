"""
╔══════════════════════════════════════════════════════════════════════╗
║  SCENARIO VALIDATOR                                                  ║
║  Validates scenarios_100.json before running simulation             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import sys

CHAIN_ORDER = ["supplier","farm","slaughterhouse","wholesaler","retail"]
TIER_IDX    = {t:i for i,t in enumerate(CHAIN_ORDER)}

VALID_PATTERNS = {
    (0,0,0,0,0),(1,0,0,0,0),(1,1,0,0,0),(0,1,0,0,0),(0,1,1,0,0),
    (0,0,1,0,0),(0,0,1,1,0),(0,0,0,1,0),(0,0,0,1,1),(1,0,0,1,0),
    (1,1,1,0,0),(0,1,0,1,0),(1,0,0,0,1),(0,0,0,0,1),(1,1,1,1,1),
    (1,1,1,1,0),(0,1,1,1,1),(0,0,1,1,1),
}

REQUIRED_DB_KEYS = {
    "supplier"      : {"available_supply","capacity","lead_time"},
    "farm"          : {"production_capacity","planned_capacity","mortality_rate"},
    "slaughterhouse": {"processing_capacity","max_capacity","output_stock","max_output"},
    "wholesaler"    : {"inventory_level","capacity","pending_shipments"},
    "retail"        : {"retail_inventory","safety_stock"},
}

def validate(path="scenarios_100.json"):
    with open(path) as f:
        scenarios = json.load(f)

    errors   = []
    warnings = []

    ids_seen = set()
    for s in scenarios:
        sid = s["scenario_id"]

        # Duplicate IDs
        if sid in ids_seen:
            errors.append(f"S{sid}: Duplicate scenario_id")
        ids_seen.add(sid)

        # Required fields
        for field in ["severity","seed_node","cascade_path","recovery_path",
                      "duration_hours","start_datetime","events"]:
            if field not in s:
                errors.append(f"S{sid}: Missing field '{field}'")

        # Severity valid
        if s.get("severity") not in ("low","medium","high","crisis"):
            errors.append(f"S{sid}: Invalid severity '{s.get('severity')}'")

        # Seed node valid
        if s.get("seed_node") not in CHAIN_ORDER:
            errors.append(f"S{sid}: Invalid seed_node '{s.get('seed_node')}'")

        # At least 1 onset + 1 recovery event
        onset_count    = sum(1 for e in s.get("events",[]) if e.get("disrupted")==1)
        recovery_count = sum(1 for e in s.get("events",[]) if e.get("disrupted")==0)
        if onset_count < 1:
            errors.append(f"S{sid}: No onset events")
        if recovery_count < 1:
            errors.append(f"S{sid}: No recovery events")

        # Event validations
        at_hours = []
        for ev in s.get("events",[]):
            eid = ev.get("event_id","?")

            # Pattern valid — onset must be valid, recovery transitions can use R1 fallback
            pat = tuple(ev.get("pattern_after",[]))
            ev_type = ev.get("event_type","")
            if pat not in VALID_PATTERNS and pat != (0,0,0,0,0):
                if ev_type == "recovery":
                    warnings.append(f"S{sid} {eid}: Recovery transition pattern {pat} uses R1 fallback (expected)")
                else:
                    errors.append(f"S{sid} {eid}: Onset pattern {pat} not in 18-rule set")

            # db_changes has required keys
            tier    = ev.get("node","")
            changes = ev.get("db_changes",{})
            if tier in REQUIRED_DB_KEYS:
                missing = REQUIRED_DB_KEYS[tier] - set(changes.keys())
                if missing:
                    warnings.append(f"S{sid} {eid}: Missing db_changes keys: {missing}")

            # at_hour within duration
            at = ev.get("at_hour",0)
            dur = s.get("duration_hours",96)
            if at > dur:
                errors.append(f"S{sid} {eid}: at_hour={at} > duration={dur}")
            at_hours.append(at)

        # Events ordered by time
        if at_hours != sorted(at_hours):
            warnings.append(f"S{sid}: Events not ordered by at_hour")

    # Summary
    n = len(scenarios)
    print(f"Validated {n} scenarios")
    print(f"  Errors   : {len(errors)}")
    print(f"  Warnings : {len(warnings)}")
    if errors:
        print("\nERRORS:")
        for e in errors[:20]:
            print(f"  {e}")
    if warnings:
        print("\nWARNINGS (first 10):")
        for w in warnings[:10]:
            print(f"  {w}")
    if not errors:
        print("\n  All scenarios VALID ✓")
    return len(errors) == 0

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "scenarios_100.json"
    ok   = validate(path)
    sys.exit(0 if ok else 1)
