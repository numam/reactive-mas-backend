import sys, os, importlib.util, traceback

sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../hitl'))

def _imp(name, base, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(base, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

HITL_DIR = os.path.abspath('../hitl')

try:
    print("Importing simulation_engine...")
    _se = _imp('simulation_engine', HITL_DIR, 'simulation_engine.py')
    print("  OK")
    print("Importing reactive_baseline...")
    _rb = _imp('reactive_baseline', HITL_DIR, 'reactive_baseline.py')
    print("  OK")
    print("Importing scenario_loader...")
    _sl = _imp('scenario_loader', HITL_DIR, 'scenario_loader.py')
    print("  OK")
    print("Importing hitl_module...")
    _hm = _imp('hitl_module', HITL_DIR, 'hitl_module.py')
    print("  OK")
    print("Importing run_simulation...")
    _rs = _imp('run_simulation', HITL_DIR, 'run_simulation.py')
    print("  OK")

    print("\nLoading scenarios...")
    _SCENARIOS_JSON = os.path.join(HITL_DIR, "scenarios_100.json")
    _sl.reset_cache()
    scenarios = _sl.load_scenarios(json_path=_SCENARIOS_JSON, fallback=True)
    print(f"  Loaded {len(scenarios)} scenarios")

    print("\nRunning scenario 1, mode=autonomous...")
    csv_ldr = _se.CSVDataLoader(data_dir=HITL_DIR)
    s = _sl.get_scenario(1, json_path=_SCENARIOS_JSON)
    if s is None:
        print("  ERROR: scenario 1 not found")
    else:
        m, sd, ed, hd = _se.run_scenario(s, mode='autonomous', csv_loader=csv_ldr, verbose=False, rng_seed=42)
        print(f"  autonomous OK: SAR={m.get('Stock Availability Rate (%)')}")

    print("\nRunning scenario 1, mode=hitl...")
    m, sd, ed, hd = _se.run_scenario(s, mode='hitl', csv_loader=csv_ldr, verbose=False, rng_seed=42)
    print(f"  hitl OK: SAR={m.get('Stock Availability Rate (%)')}")

    print("\nRunning scenario 1, mode=reactive...")
    rm, rs = _rb.run_reactive_scenario(s, csv_loader=csv_ldr, verbose=False, rng_seed=42)
    print(f"  reactive OK: SAR={rm.get('Stock Availability Rate (%)')}")

    print("\nAll OK!")

except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()
