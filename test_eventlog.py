import urllib.request, json

data = json.dumps({"scenario_id": 3}).encode()  # skenario PRICE SHOCK
req  = urllib.request.Request(
    "http://localhost:8000/simulate/scenario",
    data=data, headers={"Content-Type": "application/json"}, method="POST"
)
r      = urllib.request.urlopen(req)
result = json.loads(r.read())

print(f"Total event_log entries: {len(result['event_log'])}\n")
print(f"{'LOG_ID':<10} {'TIMESTAMP':<18} {'CATEGORY':<18} {'NODE_ID':<15} {'RULE':<6} {'DECISION':<22} {'REPORT_TYPE':<25} {'TRIGGERED_BY':<20} {'N_ACT'}")
print("-"*160)
for e in result["event_log"]:
    print(
        f"{e.get('log_id',''):<10} "
        f"{e.get('timestamp',''):<18} "
        f"{e.get('event_category',''):<18} "
        f"{e.get('node_id',''):<15} "
        f"{e.get('matched_rule',''):<6} "
        f"{e.get('orchestrator_decision',''):<22} "
        f"{e.get('report_type',''):<25} "
        f"{str(e.get('triggered_by',[])):<20} "
        f"{e.get('n_agents_instructed',0)}"
    )

print("\n--- Sample coordination_actions dari entry pertama yang ada ---")
for e in result["event_log"]:
    if e.get("coordination_actions"):
        print(f"Log {e['log_id']} | {e['timestamp']} | {e['matched_rule']}")
        for act in e["coordination_actions"]:
            print(f"  → {act['target_node']} ({act['target_type']}): {act['n_instructions']} instruksi")
            for ins in act["instructions"]:
                print(f"     {ins['variable']} {ins['operation']} {ins['value']}: {ins['description']}")
        break
