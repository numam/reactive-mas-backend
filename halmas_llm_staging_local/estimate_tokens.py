"""Estimasi total token dan biaya untuk 100 skenario berdasarkan log nyata."""
import pandas as pd

df = pd.read_csv('outputs/llm_decision_log_cot.csv', sep=';')

print(f"Total decisions logged  : {len(df)}")
print(f"Scenarios covered       : {df['scenario_id'].nunique()} (IDs: {sorted(df['scenario_id'].unique())})")

ok   = df[df['tokens_in'] > 0]
fail = df[df['tokens_in'] == 0]
print(f"\nSuccessful API calls : {len(ok)} ({len(ok)/len(df)*100:.1f}%)")
print(f"Failed / rate-limited: {len(fail)} ({len(fail)/len(df)*100:.1f}%)")

print(f"\n--- Token stats dari successful calls ---")
print(f"tokens_in  mean : {ok['tokens_in'].mean():.0f}")
print(f"tokens_out mean : {ok['tokens_out'].mean():.0f}")

per_scenario = df.groupby('scenario_id').size()
print(f"\n--- Decisions per scenario ---")
print(f"Min : {per_scenario.min()}")
print(f"Max : {per_scenario.max()}")
print(f"Mean: {per_scenario.mean():.1f}")

# Proyeksi ke 100 skenario
avg_decisions_per_scenario = per_scenario.mean()
proj_decisions = avg_decisions_per_scenario * 100

avg_in  = ok['tokens_in'].mean()
avg_out = ok['tokens_out'].mean()

proj_in_M  = (avg_in  * proj_decisions) / 1_000_000
proj_out_M = (avg_out * proj_decisions) / 1_000_000

print(f"\n{'='*50}")
print(f"ESTIMASI UNTUK 100 SKENARIO (CoT saja)")
print(f"{'='*50}")
print(f"Projected decisions : {proj_decisions:.0f}")
print(f"Tokens input        : {proj_in_M:.2f}M")
print(f"Tokens output       : {proj_out_M:.2f}M")
print(f"Total tokens        : {proj_in_M + proj_out_M:.2f}M")

# Harga per model (Google AI pricing, Juni 2025)
# gemini-2.5-flash: $0.15/1M input, $0.60/1M output (non-thinking mode)
# gemini-3.5-flash (=2.0-flash): $0.075/1M input, $0.30/1M output
models = {
    "gemini-3.5-flash (2.0)": (0.075, 0.30),
    "gemini-2.5-flash          ": (0.15,  0.60),
    "gemini-1.5-pro            ": (1.25,  5.00),
}

print(f"\n--- Estimasi Biaya ---")
print(f"{'Model':<30} {'Input':>8} {'Output':>8} {'Total':>8}  x2 (CoT+ToT)")
print("-" * 70)
for model, (p_in, p_out) in models.items():
    cost_in  = proj_in_M  * p_in
    cost_out = proj_out_M * p_out
    total    = cost_in + cost_out
    print(f"{model:<30} ${cost_in:>6.3f}  ${cost_out:>6.3f}  ${total:>6.3f}   ${total*2:.3f}")

print(f"\nCatatan: x2 karena perlu jalankan CoT (C2) DAN ToT (C3)")
print(f"         C1 (probabilistic) tidak pakai LLM, gratis.")
