# Scenario Structure Documentation
## 100 Avian Influenza Disruption Scenarios — `scenario_generator.py`

---

## 1. Overview

This simulation uses **100 programmatically generated scenarios** representing Avian Influenza (AI) outbreaks in a poultry supply chain. Each scenario is a controlled combination of five parameters: **severity**, **seed node**, **cascade depth**, **duration**, and **count**. Together they produce a statistically balanced dataset for comparing the three simulation modes (Reactive, Autonomous, HITL).

The disruption type for all 100 scenarios is **AVIAN_INFLUENZA** — representing a disease outbreak that starts at one node and progressively spreads to connected downstream nodes.

---

## 2. The Five Parameters

### 2.1 Severity

How severely the disruption affects the infected node's operational variables.

| Level | Description | Key Effect on Node | Example (Farm) |
|-------|-------------|-------------------|----------------|
| `low` | Minor disruption, self-contained | Small reduction in capacity, mild alert | `mortality_rate=0.09`, `production_capacity=520` |
| `medium` | Moderate disruption, spreading risk | Significant capacity drop, stockouts possible | `mortality_rate=0.14`, `production_capacity=380` |
| `high` | Severe disruption, cascading likely | Major capacity loss, supply chain stress | `mortality_rate=0.24`, `production_capacity=220` |
| `crisis` | Catastrophic disruption, system-wide | Near-total shutdown, emergency measures required | `mortality_rate=0.38`, `production_capacity=96` |

Severity determines the `db_changes` values injected into each affected node's `db_state` at disruption onset.

---

### 2.2 Seed Node

The node where the outbreak **originates**. The infection spreads from this node downstream.

| Seed Node | Role in Supply Chain | Count in 100 Scenarios | Biological Justification |
|-----------|---------------------|------------------------|--------------------------|
| `farm` | Poultry production | 55 | AI outbreaks almost always begin on farms (live birds) |
| `supplier` | Feed & DOC supply | 20 | Contaminated feed or chick imports trigger spread |
| `slaughterhouse` | Processing | 10 | Cross-contamination from infected incoming flocks |
| `wholesaler` | Distribution | 10 | Storage or transport of infected product |
| `retail` | End consumer point | 5 | Rare — usually detected downstream last |

---

### 2.3 Cascade Depth

How many nodes the disruption **spreads to** before being contained.

| Depth | Meaning | Example Cascade Path | Triggered Rule at Peak |
|-------|---------|---------------------|------------------------|
| 1 | Disruption stays at seed node only | `[farm]` | R4 |
| 2 | Spreads to one downstream node | `[farm → slaughterhouse]` | R5 |
| 3 | Spreads to two downstream nodes | `[farm → slaughterhouse → wholesaler]` | R7 or R12 |
| 4 | Spreads to three downstream nodes | `[farm → slaughterhouse → wholesaler → retail]` | R17 |
| 5 | Spreads to entire supply chain | `[supplier → farm → slaughterhouse → wholesaler → retail]` | R15 or R16 |

**Why 1–5?** The supply chain has exactly 5 tiers. Depth 1 means the disruption is fully contained at the source; depth 5 means it has reached every single node — a full chain crisis. Values 2–4 represent the realistic intermediate stages of a spreading outbreak.

**Why does depth appear "random" across scenarios?** The generator shuffles all 100 scenario configs (`random.shuffle(plan)`) before assigning IDs. So scenario #1 may have depth=3 while scenario #2 has depth=1. The *distribution* is controlled (see Table in Section 4), but the *ordering* is randomized for statistical balance.

---

### 2.4 Duration

The total simulation time window for one scenario.

| Duration | Ticks (15 min each) | Use Case | Count in 100 Scenarios |
|----------|--------------------|---------|-----------------------|
| 48 hours | 192 ticks | Short, acute outbreak | 15 |
| 72 hours | 288 ticks | Moderate outbreak | 25 |
| 96 hours | 384 ticks | Extended outbreak | 35 |
| 120 hours | 480 ticks | Prolonged crisis | 25 |

Longer durations are assigned to more severe or deeper-cascade scenarios, reflecting the realistic recovery time needed.

---

### 2.5 Count

**Count** is the number of scenarios generated for a specific combination of `(severity, seed, depth, duration)`. It is not stored in the scenario JSON — it is a **generation parameter only**, used to reach the total of 100 scenarios.

| Example Config | Count | Why This Count |
|---------------|-------|----------------|
| `(high, farm, 3, 96)` | 10 | Most realistic scenario — farm-origin, severe, medium depth |
| `(crisis, farm, 5, 120)` | 8 | Maximum crisis — rarest but important for edge-case testing |
| `(low, farm, 1, 48)` | 5 | Baseline mild case — control group |
| `(medium, wholesaler, 2, 72)` | 3 | Downstream-origin, less common |

Think of count as how many "replicas" of a configuration exist in the dataset, each with slightly different `db_changes` values due to random noise (`± 8%` applied per variable).

---

## 3. Disruption Mechanism

### 3.1 What Happens at Onset

When a disruption event fires at a node:

```
inject_disruption(db_changes)
    ↓
node.db_state updated with disruption values
    ↓
check_disruption(db_state) → disrupted = 1
    ↓
NodeAgent sends DisruptionReport to CoordinatingAgent
    ↓
CoordinatingAgent updates global_pattern
    ↓
Rule matched → instructions sent to all affected tiers
```

### 3.2 db_changes Per Tier Per Severity

The exact values injected into each node's `db_state`:

#### Farm
| Variable | low | medium | high | crisis |
|----------|-----|--------|------|--------|
| `mortality_rate` | 0.09 | 0.14 | 0.24 | 0.38 |
| `production_capacity` | 520 | 380 | 220 | 96 |
| `outgoing_orders` | 350 | 240 | 120 | 50 |
| `live_inventory` | 520 | 380 | 220 | 96 |
| `feed_stock` | 470 | 420 | 380 | 320 |
| `disease_alert` | 1 | 1 | 1 | 1 |

#### Supplier
| Variable | low | medium | high | crisis |
|----------|-----|--------|------|--------|
| `available_supply` | 420 | 280 | 180 | 95 |
| `lead_time` | 4.2 | 5.5 | 7.0 | 9.5 |
| `supplier_reliability` | 0.58 | 0.45 | 0.38 | 0.22 |
| `shipment_status` | delayed | delayed | delayed | cancelled |

#### Slaughterhouse
| Variable | low | medium | high | crisis |
|----------|-----|--------|------|--------|
| `processing_capacity` | 240 | 175 | 110 | 55 |
| `processing_delay` | 4.2h | 6.0h | 8.5h | 12.0h |
| `output_stock` | 118 | 82 | 48 | 22 |
| `worker_availability` | 0.72 | 0.62 | 0.52 | 0.38 |
| `equipment_status` | partial | partial | partial | down |

#### Wholesaler
| Variable | low | medium | high | crisis |
|----------|-----|--------|------|--------|
| `inventory_level` | 88 | 58 | 32 | 14 |
| `pending_shipments` | 52 | 72 | 88 | 108 |
| `delivery_schedule` | delayed | delayed | delayed | delayed |
| `shipment_status` | delayed | delayed | cancelled | cancelled |

#### Retail
| Variable | low | medium | high | crisis |
|----------|-----|--------|------|--------|
| `retail_inventory` | 22 | 10 | 4 | 0 |
| `stockout_flag` | 0 | 1 | 1 | 1 |
| `shortage_duration` | 1.5h | 3.5h | 6.0h | 9.5h |
| `reorder_request` | 45 | 75 | 110 | 140 |

> All values include ±8% random noise per scenario for variability.

---

## 4. Scenario Distribution (All 100)

| Severity | Seed Node | Depth | Duration | Count | Scenario Type |
|----------|-----------|-------|----------|-------|---------------|
| low | farm | 1 | 48h | 5 | Mild single-node (farm) |
| low | farm | 2 | 72h | 5 | Mild two-node cascade |
| low | supplier | 1 | 48h | 3 | Mild supplier issue |
| low | slaughterhouse | 1 | 48h | 2 | Mild processing disruption |
| **low total** | | | | **15** | |
| medium | farm | 2 | 72h | 8 | Moderate farm→slaughterhouse |
| medium | farm | 3 | 96h | 7 | Moderate mid-chain spread |
| medium | supplier | 2 | 72h | 5 | Moderate upstream disruption |
| medium | slaughterhouse | 2 | 72h | 4 | Moderate processing cascade |
| medium | wholesaler | 2 | 72h | 3 | Moderate distribution disruption |
| medium | farm | 1 | 48h | 3 | Moderate single-node |
| **medium total** | | | | **30** | |
| high | farm | 3 | 96h | 10 | Severe mid-chain cascade |
| high | farm | 4 | 96h | 8 | Severe deep cascade |
| high | supplier | 3 | 96h | 6 | Severe upstream spread |
| high | slaughterhouse | 3 | 96h | 4 | Severe processing crisis |
| high | wholesaler | 3 | 96h | 4 | Severe distribution crisis |
| high | retail | 2 | 72h | 3 | Severe downstream |
| **high total** | | | | **35** | |
| crisis | farm | 5 | 120h | 8 | Full chain crisis |
| crisis | farm | 4 | 120h | 5 | Near-full chain crisis |
| crisis | supplier | 4 | 120h | 4 | Upstream-driven full crisis |
| crisis | farm | 3 | 96h | 3 | Crisis-level mid-cascade |
| **crisis total** | | | | **20** | |
| **GRAND TOTAL** | | | | **100** | |

---

## 5. Event Timeline Structure

Each scenario contains a sequence of events spanning its duration:

```
0%──────────────40%────────────────50%──────────────95%──────100%
│  ONSET/ESCALATION  │    PEAK     │     RECOVERY        │
│                    │             │                     │
E001: onset          │             E004: recovery tier 1 │
E002: escalation     │             E005: recovery tier 2 │
E003: peak_escalation│             E006: recovery tier 3 │
```

| Event Type | Timing | `disrupted` | What it Does |
|------------|--------|-------------|--------------|
| `onset` | First 40% of duration | 1 | Seeds disruption at the seed node |
| `escalation` | First 40% of duration | 1 | Spreads to next tier in cascade path |
| `peak_escalation` | ~40% mark | 1 | Disruption reaches maximum spread (peak rule) |
| `recovery` | 50%–95% of duration | 0 | Tier-by-tier recovery in biologically realistic order |

---

## 6. Cascade Path Templates

The cascade path is drawn from pre-defined realistic templates per seed node:

| Seed | Depth 1 | Depth 2 | Depth 3 | Depth 4 | Depth 5 |
|------|---------|---------|---------|---------|---------|
| farm | [farm] | [farm→SH] or [farm→WH] | [farm→SH→WH] | [farm→SH→WH→Retail] | [Sup→farm→SH→WH→Retail] |
| supplier | [supplier] | [sup→farm] | [sup→farm→SH] | [sup→farm→SH→WH] | [sup→farm→SH→WH→Retail] |
| slaughterhouse | [SH] | [SH→WH] | [SH→WH→Retail] | [farm→SH→WH→Retail] | [farm→sup→SH→WH→Retail] |
| wholesaler | [WH] | [WH→Retail] | [SH→WH→Retail] | [farm→SH→WH→Retail] | [farm→sup→SH→WH→Retail] |
| retail | [Retail] | [WH→Retail] | [SH→WH→Retail] | [farm→SH→WH→Retail] | [sup→farm→SH→WH→Retail] |

> SH = Slaughterhouse, WH = Wholesaler, Sup = Supplier

---

## 7. Subtype Labels

Scenario subtype labels encode the biological context:

| Seed | Severity | Subtype Label | Biological Meaning |
|------|----------|--------------|-------------------|
| farm | low | `H9N2_LPAI` | Low Pathogenicity AI — minor impact |
| farm | medium | `H5N1_LOCAL` | Highly Pathogenic AI — localized |
| farm | high | `H5N1_SPREADING` | HPAI spreading across farms |
| farm | crisis | `H5N1_REGIONAL_CRISIS` | HPAI regional emergency |
| supplier | low | `EMBARGO_MILD` | Minor import/feed restrictions |
| supplier | medium | `EMBARGO_MODERATE` | Significant trade restriction |
| supplier | high | `EMBARGO_SEVERE` | Major export ban applied |
| supplier | crisis | `EMBARGO_CRITICAL` | Full trade embargo |
| other seeds | any | `AI_{SEVERITY}_{SEED}` | Generic AI disruption label |

---

## 8. How to Use the Scenarios

### Run a single scenario via API
```
POST /hitl/simulate/scenario
{ "scenario_id": 1, "mode": "hitl", "rng_seed": 42 }
```

### Filter scenarios by type before running
```
GET /hitl/scenarios?severity=crisis&page=1&page_size=20
GET /hitl/scenarios?disruption_type=AVIAN_INFLUENZA
```

### Regenerate `scenarios_100.json`
```bash
cd hitl/
python scenario_generator.py
# → writes scenarios_100.json
```

### Read a specific scenario's events
```
GET /hitl/scenarios/1
GET /hitl/scenarios/1/events
```

### Understand what rule fires at peak
Check `peak_rule` in the scenario JSON — it directly maps to the `ORCHESTRATOR_RULES` entry that will be active when the cascade reaches maximum spread.

---

## 9. Recovery Order

Recovery follows a biologically realistic sequence — the node that was most recently disrupted recovers first:

| Seed Node | Recovery Order |
|-----------|---------------|
| farm | farm → slaughterhouse → wholesaler → retail |
| supplier | supplier → farm → slaughterhouse → wholesaler → retail |
| slaughterhouse | slaughterhouse → wholesaler → retail → farm |
| wholesaler | wholesaler → retail |
| retail | retail only |

Recovery `db_changes` restore variables to above-threshold values (with ±5–8% noise) so `check_recovery()` returns `True` and the agent's `disrupted` flag resets to 0.
