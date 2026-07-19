"""
Diagnostic script — cek API key, model, dan raw response dari Gemini.
Jalankan: python test_api.py
"""
import os
import sys
import json
import requests

# ── 1. Cek API key ────────────────────────────────────────────────
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
print("=" * 60)
print(f"[1] GEMINI_API_KEY di env : {'SET (' + api_key[:12] + '...)' if api_key else 'TIDAK ADA / KOSONG'}")

if not api_key:
    print("\n  ERROR: API key tidak terbaca dari environment variable.")
    print("  Pastikan Anda menjalankan ini di PowerShell yang SAMA")
    print("  di mana Anda menjalankan:")
    print('    $env:GEMINI_API_KEY="AIza..."')
    print("\n  Atau hardcode sementara di baris bawah untuk test:")
    print('    api_key = "AIza..."')
    # ── UNCOMMENT dan isi untuk test hardcode ──
    # api_key = "AIza..."
    if not api_key:
        sys.exit(1)

# ── 2. Test dengan model yang sama persis seperti di curl ─────────
models_to_test = [
    "gemini-3.1-flash-lite",   # yang berhasil di curl Anda
    "gemini-2.0-flash",      # yang dipakai program
    "gemini-1.5-flash",      # fallback
]

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
payload = {
    "contents": [{"parts": [{"text": "Reply with exactly this JSON and nothing else: {\"decision\": \"ACCEPT\", \"factor\": 1.0, \"justification\": \"test ok\"}"}]}],
    "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
}

print("\n[2] TEST TIAP MODEL:")
print("=" * 60)

for model in models_to_test:
    url = f"{BASE}/{model}:generateContent"
    try:
        resp = requests.post(
            url,
            headers={"content-type": "application/json"},
            params={"key": api_key},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = "".join(p.get("text","") for p in candidates[0]["content"]["parts"])
                usage = data.get("usageMetadata", {})
                print(f"  {model:<30} -> OK  tokens={usage.get('promptTokenCount',0)}/{usage.get('candidatesTokenCount',0)}")
                print(f"    raw response: {text[:120]!r}")
            else:
                block = data.get("promptFeedback", {}).get("blockReason", "?")
                print(f"  {model:<30} -> BLOCKED ({block})")
        elif resp.status_code == 429:
            print(f"  {model:<30} -> 429 RATE LIMIT — tunggu lalu coba lagi")
        elif resp.status_code == 404:
            print(f"  {model:<30} -> 404 MODEL NOT FOUND")
        else:
            print(f"  {model:<30} -> HTTP {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        print(f"  {model:<30} -> EXCEPTION: {e}")

# ── 3. Cek apakah env var terbaca dari subprocess (simulasi cara program jalan) ──
print("\n[3] CEK ENV VAR via subprocess:")
print("=" * 60)
import subprocess
result = subprocess.run(
    [sys.executable, "-c", "import os; k=os.environ.get('GEMINI_API_KEY',''); print('KEY_FOUND' if k else 'KEY_MISSING'); print(k[:12] if k else 'empty')"],
    capture_output=True, text=True
)
print(f"  {result.stdout.strip()}")
if result.stderr:
    print(f"  stderr: {result.stderr.strip()}")
