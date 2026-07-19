import sys
sys.path.insert(0, '.')
try:
    import backend.main
    print("OK - import berhasil")
    routes = [r.path for r in backend.main.app.routes if hasattr(r, 'path')]
    print(f"Total routes: {len(routes)}")
except Exception as e:
    import traceback
    print("ERROR:", e)
    traceback.print_exc()
