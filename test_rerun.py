import urllib.request, json, os, pandas as pd

BASE = "http://localhost:8000"

def post(path, body):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(f"{BASE}{path}", data=data,
           headers={"Content-Type": "application/json"}, method="POST")
    r = urllib.request.urlopen(req, timeout=60)
    return json.loads(r.read())

output_dir = r"D:\PAPER\Multi Agent (NUS)\supply-chain\code\hitl\output_3mode\scenario_001"

# Test hanya mode reactive (cepat)
print("--- Run 1: scenario 1, mode=reactive ---")
r = post("/hitl/simulate/scenario", {"scenario_id": 1, "mode": "reactive"})
files1 = sorted(os.listdir(output_dir))
print(f"  SAR: {r['results'][0]['metrics'].get('Stock Availability Rate (%)')}%")
print(f"  Files: {files1}")

print("\n--- Run 2 (re-run): scenario 1, mode=reactive ---")
r2 = post("/hitl/simulate/scenario", {"scenario_id": 1, "mode": "reactive"})
files2 = sorted(os.listdir(output_dir))
print(f"  SAR: {r2['results'][0]['metrics'].get('Stock Availability Rate (%)')}%")
print(f"  Files: {files2}")
print(f"  Same files? {files1 == files2}")

# Cek scenario_metrics_3mode.csv — S1 harusnya hanya 1 baris reactive (tidak duplikat)
p = r"D:\PAPER\Multi Agent (NUS)\supply-chain\code\hitl\output_3mode\scenario_metrics_3mode.csv"
if os.path.exists(p):
    dm = pd.read_csv(p)
    s1 = dm[dm["scenario_id"]==1]
    print(f"\nscenario_metrics_3mode S1: {len(s1)} rows, modes={s1['mode'].tolist()}")
    if len(s1) == s1['mode'].nunique():
        print("  OK - tidak ada duplikat mode")
    else:
        print("  WARNING - ada duplikat mode!")
        print(s1[['scenario_id','mode','Stock Availability Rate (%)']].to_string())
