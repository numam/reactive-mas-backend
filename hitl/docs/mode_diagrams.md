# Mode Diagrams — Reactive / Autonomous / HITL

Berisi diagram Mermaid yang menggambarkan alur aturan utama tiap mode.

## Reactive

```mermaid
flowchart LR
  Start([Start])
  Start --> ScanLocal[Local scan: check_disruption & inventory]
  ScanLocal --> LowInv{Inventory < reorder_point?}
  LowInv -- yes --> LocalReorder[Schedule local restock]
  LowInv -- no --> NoAction[No coordination action]
  LocalReorder --> SupplyFlowFixed[SupplyFlowEngine (fixed schedule)]
  SupplyFlowFixed --> DisruptionCap{Upstream disrupted?}
  DisruptionCap -- yes --> ApplyFixed[Apply FIXED_DISRUPTION_FACTOR]
  DisruptionCap -- no --> NormalFlow[Normal fixed flow]
  ApplyFixed --> End([End])
  NormalFlow --> End
  NoAction --> End
```

## Autonomous (MAS, immediate execution)

```mermaid
flowchart LR
  Start([Start])
  Start --> Scan[Node scan → DisruptionReport? (`NodeAgent.scan`)]
  Scan --> ReportYes{Disrupted?}
  ReportYes -- yes --> Coordinator[`CoordinatingAgent.receive_report`]
  Coordinator --> MatchRule[`match_rule` → ORCHESTRATOR_RULES]
  MatchRule --> Signals[Emit signals (instructions)]
  Signals --> ApplyInst[`apply_instructions()` applied immediately]
  ApplyInst --> UpdateDB[DB updated (may set `reorder_request`)]
  UpdateDB --> ReorderCheck{`reorder_request` > 0?}
  ReorderCheck -- yes --> Amplify[Amplify flow (bypass caps)]
  ReorderCheck -- no --> Caps[Apply disruption caps to flow]
  Amplify --> SupplyFlow[SupplyFlowEngine schedules restock (no HRT)]
  Caps --> SupplyFlow
  SupplyFlow --> End([End])
```

## HITL (MAS + Human‑in‑the‑Loop)

```mermaid
flowchart LR
  Start([Start])
  Start --> Scan[Node scan → DisruptionReport?]
  Scan --> Coordinator[`CoordinatingAgent.receive_report`]
  Coordinator --> MatchRule[`match_rule` → ORCHESTRATOR_RULES]
  MatchRule --> Signals[Emit signals (instructions)]
  Signals --> HitL[`HitLEngine.process_signal`]
  HitL --> Decision{Decision: accept / modify / override / timeout}
  Decision -- accept --> FinalA[Final instructions = original]
  Decision -- modify --> FinalM[Apply `modification_factor` via `_apply_factor`]
  Decision -- override --> FinalO[Apply `override_factor`]
  Decision -- timeout --> FinalT[Auto-accept (timeout)]
  FinalA --> RecordHRT[Record `response_time` (HRT)]
  FinalM --> RecordHRT
  FinalO --> RecordHRT
  FinalT --> RecordHRT
  RecordHRT --> HRTDelay{HRT > 0?}
  HRTDelay -- yes --> StoreDelay[Store in `pending_signals` (hrt_delays)]
  HRTDelay -- no --> ImmediateExec[Execute instructions immediately]
  StoreDelay --> DelayedExec[SupplyFlowEngine uses `pending_signals` → schedule restock with delay]
  ImmediateExec --> DelayedExec
  DelayedExec --> End([End])
```

---

File dibuat otomatis oleh assistant; kalau mau, saya bisa juga menaruh diagram gabungan atau menambahkan keterangan tiap node/operation.
