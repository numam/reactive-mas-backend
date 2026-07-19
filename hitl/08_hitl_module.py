"""
╔══════════════════════════════════════════════════════════════════════╗
║  FILE 08 — HUMAN-IN-THE-LOOP MODULE (FINAL)                         ║
║  MAS Poultry Supply Chain Resilience                                 ║
║                                                                      ║
║  Advisory Mode — Probabilistic Manager Behavior:                     ║
║    Accept  : eksekusi instruksi coordinator penuh                    ║
║    Modify  : eksekusi instruksi dengan faktor konservasi (<1.0)      ║
║    Override: eksekusi instruksi dikurangi signifikan                 ║
║    Timeout : tidak merespons → auto-accept                           ║
║                                                                      ║
║  Metrik tambahan yang dihasilkan:                                    ║
║    HRT   : Human Response Time (jam)                                 ║
║    OR    : Override Rate (%)                                         ║
║    MF    : Mean Modification Factor                                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

# ════════════════════════════════════════════════════════════════════
# MANAGER PROFILE PER TIER
# ════════════════════════════════════════════════════════════════════

MANAGER_PROFILES = {
    "supplier": {
        "role"             : "Procurement Manager",
        "p_accept"         : 0.75,
        "p_modify"         : 0.18,
        "p_override"       : 0.07,
        "response_time_mu" : 2.0,    # jam
        "response_time_sd" : 0.8,
        "modify_factor_mu" : 0.90,   # nilai instruksi dikali faktor ini
        "modify_factor_sd" : 0.05,
        "override_factor"  : 0.50,   # override = 50% dari instruksi asli
        "timeout_hours"    : 3.0,    # auto-accept jika tidak merespons
        "urgency_boost"    : {"normal": 0.0, "high": 0.08, "crisis": 0.15},
    },
    "farm": {
        "role"             : "Farm Manager",
        "p_accept"         : 0.62,
        "p_modify"         : 0.28,
        "p_override"       : 0.10,
        "response_time_mu" : 1.5,
        "response_time_sd" : 0.7,
        "modify_factor_mu" : 0.85,
        "modify_factor_sd" : 0.06,
        "override_factor"  : 0.40,
        "timeout_hours"    : 2.0,
        "urgency_boost"    : {"normal": 0.0, "high": 0.10, "crisis": 0.20},
    },
    "slaughterhouse": {
        "role"             : "Operations Manager",
        "p_accept"         : 0.80,
        "p_modify"         : 0.14,
        "p_override"       : 0.06,
        "response_time_mu" : 0.5,
        "response_time_sd" : 0.2,
        "modify_factor_mu" : 0.92,
        "modify_factor_sd" : 0.04,
        "override_factor"  : 0.55,
        "timeout_hours"    : 1.0,
        "urgency_boost"    : {"normal": 0.0, "high": 0.08, "crisis": 0.12},
    },
    "wholesaler": {
        "role"             : "Distribution Manager",
        "p_accept"         : 0.68,
        "p_modify"         : 0.22,
        "p_override"       : 0.10,
        "response_time_mu" : 1.0,
        "response_time_sd" : 0.4,
        "modify_factor_mu" : 0.88,
        "modify_factor_sd" : 0.05,
        "override_factor"  : 0.45,
        "timeout_hours"    : 1.5,
        "urgency_boost"    : {"normal": 0.0, "high": 0.10, "crisis": 0.18},
    },
    "retail": {
        "role"             : "Store Manager",
        "p_accept"         : 0.58,
        "p_modify"         : 0.30,
        "p_override"       : 0.12,
        "response_time_mu" : 0.25,
        "response_time_sd" : 0.10,
        "modify_factor_mu" : 0.82,
        "modify_factor_sd" : 0.07,
        "override_factor"  : 0.40,
        "timeout_hours"    : 0.5,
        "urgency_boost"    : {"normal": 0.0, "high": 0.12, "crisis": 0.20},
    },
}


# ════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════════════════════

@dataclass
class ManagerDecision:
    tier                 : str
    decision             : str      # accept | modify | override | timeout
    response_time        : float    # jam
    original_instructions: list
    final_instructions   : list     # setelah modify/override diterapkan
    modification_factor  : float    # 1.0=accept, <1.0=modify/override
    rationale            : str


@dataclass
class HitLLogEntry:
    tick                : int
    timestamp           : str
    tier                : str
    rule_id             : str
    urgency             : str
    decision            : str
    response_time       : float
    modification_factor : float
    n_instructions      : int
    rationale           : str


# ════════════════════════════════════════════════════════════════════
# HITL ENGINE
# ════════════════════════════════════════════════════════════════════

class HitLEngine:
    """
    Probabilistic Human-in-the-Loop Advisory Mode engine.
    Setiap CoordinationSignal diproses oleh manager tier terkait.
    """

    def __init__(self, rng_seed: Optional[int] = None):
        self.rng   = np.random.default_rng(rng_seed)
        self.log   : list[HitLLogEntry] = []
        self._counts = {
            t: {"accept": 0, "modify": 0, "override": 0, "timeout": 0}
            for t in MANAGER_PROFILES
        }

    def process_signal(self, signal: dict, tick: int,
                       timestamp: str, urgency: str = "normal") -> ManagerDecision:
        """
        Proses satu CoordinationSignal melalui manager probabilistik.

        Parameters:
            signal    : {"target_type", "rule_id", "instructions", ...}
            tick      : tick simulasi saat ini
            timestamp : string timestamp
            urgency   : "normal" | "high" | "crisis"

        Return:
            ManagerDecision dengan instruksi final yang siap dieksekusi
        """
        tier         = signal.get("target_type", "")
        instructions = signal.get("instructions", [])
        rule_id      = signal.get("rule_id", "R1")

        # Jika tier tidak dikenal atau tidak ada instruksi → auto accept
        if tier not in MANAGER_PROFILES or not instructions:
            return ManagerDecision(
                tier=tier, decision="accept",
                response_time=0.0,
                original_instructions=instructions,
                final_instructions=instructions,
                modification_factor=1.0,
                rationale="No review needed",
            )

        profile = MANAGER_PROFILES[tier]
        boost   = profile["urgency_boost"].get(urgency, 0.0)

        # Hitung probabilitas dengan urgency boost
        p_a = min(0.95, profile["p_accept"]   + boost)
        p_m = profile["p_modify"]  * (1 - boost)
        p_o = max(0.01, profile["p_override"] - boost * 0.5)
        total = p_a + p_m + p_o
        p_a, p_m, p_o = p_a/total, p_m/total, p_o/total

        # Simulasi response time
        rt = max(0.05, float(self.rng.normal(
            profile["response_time_mu"], profile["response_time_sd"])))

        # Cek timeout
        if rt > profile["timeout_hours"]:
            decision = "timeout"
            final    = instructions
            factor   = 1.0
            rationale = (f"{profile['role']} tidak merespons dalam "
                         f"{profile['timeout_hours']}h → auto-accept")
        else:
            roll = float(self.rng.random())
            if roll < p_a:
                decision = "accept"
                final    = instructions
                factor   = 1.0
                rationale = (f"{profile['role']} menerima rekomendasi "
                             f"coordinator ({rule_id}, urgency={urgency})")
            elif roll < p_a + p_m:
                decision = "modify"
                factor   = max(0.50, float(self.rng.normal(
                    profile["modify_factor_mu"], profile["modify_factor_sd"])))
                final    = self._apply_factor(instructions, factor)
                rationale = (f"{profile['role']} memodifikasi instruksi "
                             f"(faktor={factor:.2f}) — pendekatan lebih konservatif")
            else:
                decision = "override"
                factor   = profile["override_factor"]
                final    = self._apply_factor(instructions, factor)
                rationale = (f"{profile['role']} mengganti instruksi "
                             f"(faktor={factor:.2f}) — kebijakan lokal diprioritaskan")

        # Catat log
        self._counts[tier][decision] += 1
        self.log.append(HitLLogEntry(
            tick=tick, timestamp=timestamp, tier=tier,
            rule_id=rule_id, urgency=urgency, decision=decision,
            response_time=round(rt, 3),
            modification_factor=round(factor, 3),
            n_instructions=len(instructions),
            rationale=rationale,
        ))

        return ManagerDecision(
            tier=tier, decision=decision,
            response_time=rt,
            original_instructions=instructions,
            final_instructions=final,
            modification_factor=factor,
            rationale=rationale,
        )

    def _apply_factor(self, instructions: list, factor: float) -> list:
        """
        Terapkan modification factor ke instruksi numerik.
        String/flag values tidak diubah.
        """
        result = []
        for inst in instructions:
            ni  = dict(inst)
            op  = inst.get("operation", "")
            val = inst.get("value")
            if op in ("multiply", "add", "subtract") and isinstance(val, (int, float)):
                if op == "multiply":
                    # Efek dikurangi: 1 + (val-1)*factor (mendekati 1 jika factor kecil)
                    ni["value"] = round(1.0 + (val - 1.0) * factor, 4)
                else:
                    ni["value"] = round(val * factor, 4)
            result.append(ni)
        return result

    # ── Metrics ──────────────────────────────────────────────────────

    def get_override_rate(self) -> dict:
        rates = {}
        for tier, counts in self._counts.items():
            total = sum(counts.values())
            rates[tier] = round(counts["override"] / total * 100, 2) if total else 0.0
        return rates

    def get_mean_hrt(self) -> dict:
        from collections import defaultdict
        times = defaultdict(list)
        for e in self.log:
            if e.decision != "timeout":
                times[e.tier].append(e.response_time)
        return {t: round(float(np.mean(v)), 3) if v else 0.0
                for t, v in times.items()}

    def get_summary(self) -> dict:
        if not self.log:
            return {}
        df   = pd.DataFrame([vars(e) for e in self.log])
        total = len(df)
        return {
            "total_decisions"        : total,
            "accept_rate_%"          : round(len(df[df.decision=="accept"]) / total * 100, 2),
            "modify_rate_%"          : round(len(df[df.decision=="modify"]) / total * 100, 2),
            "override_rate_%"        : round(len(df[df.decision=="override"]) / total * 100, 2),
            "timeout_rate_%"         : round(len(df[df.decision=="timeout"]) / total * 100, 2),
            "mean_HRT_hours"         : round(float(df.response_time.mean()), 3),
            "mean_modification_factor": round(float(df.modification_factor.mean()), 3),
            "override_rate_per_tier" : self.get_override_rate(),
            "mean_HRT_per_tier"      : self.get_mean_hrt(),
        }

    def get_log_df(self) -> pd.DataFrame:
        return pd.DataFrame([vars(e) for e in self.log])


if __name__ == "__main__":
    np.random.seed(42)
    engine = HitLEngine(rng_seed=42)
    print("=== HitL MODULE DEMO ===\n")
    test_signals = [
        {"target_type":"farm",      "rule_id":"R4",  "urgency":"normal",
         "instructions":[{"variable":"outgoing_orders","operation":"multiply","value":0.80}]},
        {"target_type":"farm",      "rule_id":"R11", "urgency":"crisis",
         "instructions":[{"variable":"outgoing_orders","operation":"multiply","value":0.50},
                          {"variable":"feed_stock","operation":"multiply","value":0.90}]},
        {"target_type":"wholesaler","rule_id":"R7",  "urgency":"high",
         "instructions":[{"variable":"delivery_schedule","operation":"flag","value":"rerouted"},
                          {"variable":"pending_shipments","operation":"multiply","value":0.60}]},
        {"target_type":"retail",    "rule_id":"R9",  "urgency":"high",
         "instructions":[{"variable":"reorder_request","operation":"multiply","value":1.20},
                          {"variable":"safety_stock","operation":"multiply","value":1.10}]},
    ]
    for sig in test_signals:
        dec = engine.process_signal(sig, tick=10, timestamp="2026-03-01 12:00",
                                    urgency=sig["urgency"])
        print(f"  [{sig['target_type'].upper()}] {sig['rule_id']} urgency={sig['urgency']}")
        print(f"  Decision: {dec.decision} | HRT={dec.response_time:.2f}h | factor={dec.modification_factor:.2f}")
        if dec.decision in ("modify","override"):
            for o, f in zip(dec.original_instructions, dec.final_instructions):
                if o.get("value") != f.get("value"):
                    print(f"    {o['variable']}: {o.get('value')} → {f.get('value')}")
        print()
    print("=== SUMMARY ===")
    for k, v in engine.get_summary().items():
        print(f"  {k:<35}: {v}")
