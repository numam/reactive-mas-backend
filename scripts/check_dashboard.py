from fastapi.testclient import TestClient
from backend.main import app
import json

c = TestClient(app)
r = c.get('/dashboard/tiers')
print('status', r.status_code)
try:
    p = r.json()
except Exception as e:
    print('json error', e)
    raise
print('total_tiers=', p.get('total_tiers'))
print('tier_names=', [t['tier'] for t in p.get('tiers',[] )])
first = p.get('tiers',[])[0]
print('has meta.description=', 'description' in first.get('meta',{}))
print('has rule keys=', all(k in first.get('rule',{}) for k in ['threshold_ratio','reorder_qty_ratio','explanation']))
print(json.dumps(p, indent=2))
