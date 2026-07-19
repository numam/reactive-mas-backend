"""
╔══════════════════════════════════════════════════════════════════════╗
║  SCENARIO LOADER                                                     ║
║  Loads scenarios from scenarios_100.json (or fallback to            ║
║  hardcoded 5 scenarios from disruption_scenarios_ai.py)             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import os
from typing import Optional

_CACHE: Optional[list] = None

def load_scenarios(json_path: str = "scenarios_100.json",
                   fallback: bool = True) -> list:
    """
    Load scenarios from JSON file.
    Falls back to hardcoded 5 scenarios if JSON not found and fallback=True.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    # Try loading from JSON
    if os.path.exists(json_path):
        with open(json_path) as f:
            scenarios = json.load(f)
        print(f"  Loaded {len(scenarios)} scenarios from {json_path}")
        _CACHE = scenarios
        return scenarios

    # Fallback to hardcoded 5 scenarios
    if fallback:
        print(f"  WARNING: {json_path} not found — using 5 hardcoded scenarios")
        from disruption_scenarios_ai import AI_OUTBREAK_SCENARIOS
        _CACHE = AI_OUTBREAK_SCENARIOS
        return _CACHE

    raise FileNotFoundError(f"Scenario file not found: {json_path}")


def get_scenario(scenario_id: int,
                 json_path: str = "scenarios_100.json") -> Optional[dict]:
    """Get a single scenario by ID."""
    scenarios = load_scenarios(json_path)
    for s in scenarios:
        if s["scenario_id"] == scenario_id:
            return s
    return None


def get_disruption_schedule(scenario_id: int,
                             json_path: str = "scenarios_100.json") -> list:
    """
    Convert scenario events to disruption_schedule format
    compatible with run_scenario().
    """
    scenario = get_scenario(scenario_id, json_path)
    if not scenario:
        # Try hardcoded fallback
        from disruption_scenarios_ai import get_disruption_schedule as _fallback
        return _fallback(scenario_id)

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


def reset_cache():
    """Clear the scenario cache (useful for testing)."""
    global _CACHE
    _CACHE = None


if __name__ == "__main__":
    scenarios = load_scenarios()
    print(f"\nScenario IDs available: {[s['scenario_id'] for s in scenarios[:10]]}...")
    s = get_scenario(1)
    if s:
        print(f"\nScenario 1: {s['subtype']} | {s['severity']} | {s['duration_hours']}h")
        print(f"  cascade: {s['cascade_path']}")
        print(f"  events : {len(s['events'])}")
