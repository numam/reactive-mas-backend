"""
Quick sanity check: test OllamaProvider dengan prompt TOT
untuk memastikan koneksi aktif dan parse berhasil.
"""
from provider_ollama import OllamaProvider

provider = OllamaProvider()

# Prompt mirip struktur ToT
prompt = """=== BLOCK 1: PERSONA ===
You are a farm manager with 10 years of experience.

=== BLOCK 2: OPERATIONAL STATE ===
CURRENT FARM STATUS:
  - production_capacity : 80 ekor  (threshold: < 60% planned)
  - mortality_rate      : 0.05

=== BLOCK 3: COORDINATOR INSTRUCTION ===
INSTRUCTION FROM COORDINATING AGENT:
  Rule triggered : R4  (Potential Disruption)
  Urgency level  : normal
  Instruction    : Reduce production capacity by 20%

=== BLOCK 4: DECISION HISTORY ===
(No prior decisions in this session.)

=== BLOCK 5b (ToT mode) ===
Consider three possible responses to the coordinator's instruction:

OPTION A - ACCEPT (factor=1.00):
  Execute the instruction fully as specified by the coordinator.

OPTION B - MODIFY (factor=0.50-0.90):
  Execute the instruction at reduced intensity.

OPTION C - OVERRIDE (factor=0.20-0.50):
  Apply your own local policy instead of the coordinator's instruction.

Evaluate all three options, then select the best one.

Then output ONLY valid JSON in this exact format:
{
  "decision": "ACCEPT" | "MODIFY" | "OVERRIDE",
  "factor": <number between 0.0 and 1.0>,
  "justification": "<2-3 sentences explaining your reasoning>"
}
"""

print("Testing TOT call via OllamaProvider.call_and_parse() ...")
import time
t0 = time.time()
call_result, parsed = provider.call_and_parse(prompt)
elapsed = time.time() - t0

print(f"\n--- call_result ---")
print(f"  success    : {call_result.success}")
print(f"  latency    : {elapsed:.1f}s")
print(f"  error      : {call_result.error}")
print(f"\n--- parsed ---")
print(f"  parse_ok   : {parsed.parse_ok}")
print(f"  decision   : {parsed.decision}")
print(f"  factor     : {parsed.factor}")
print(f"  justif.    : {parsed.justification[:200]}")

if parsed.parse_ok and parsed.decision in ("ACCEPT","MODIFY","OVERRIDE"):
    print("\n✅ TOT OK — LLM terhubung dan parse berhasil")
else:
    print("\n❌ FAIL")
    print("raw:", repr(call_result.raw_text[:400]))
