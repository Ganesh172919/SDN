# SELF-X System Architecture and Engineering Navigation

> **Comprehensive Architectural Specification for the Autonomous SDN Flow-Management Agent, Loss-Aware Episodic Memory, Bounded Process-Isolated Control Deadlines, and Two-Path Fluid Network Simulation**  
> *Course Project — EC466: Software Defined Networks | Team ID: SDN_07*  
> *Module Directory: `selfx/docs/` | System Scope: 86,400 Control Windows | 9 Controllers | 8 Scenarios*

---

## 📌 Architectural Scope and Execution Boundaries

SELF-X is an autonomous SDN flow management system that observes real-time network traffic, queries an episodic memory store of past state-action-outcome experiences, evaluates LLM proposals within strict wall-clock deadlines, validates candidate rules through an independent deterministic safety gate, installs simulated OpenFlow 1.3 flow/meter table interventions, and stores measured counterfactual rewards.

All production files, execution environments, test scripts, and benchmark outputs reside strictly within `selfx/`. The validated runtime on Windows utilizes a two-path finite-buffer fluid network simulation model. Real external calls to Google Gemini and OpenRouter free models supply live decision suggestions under a 3.8-second process-isolated wait budget. The local OpenFlow rule table is fully simulated with 5-second hard timeouts matching virtual observation cycles.

---

## 🎨 Colourful Architecture Mindmap

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#1E88E5', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#F3F4F6'}}}%%
flowchart TD
    classDef teleNode fill:#00897B,stroke:#004D40,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef memNode fill:#FB8C00,stroke:#E65100,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef ctrlNode fill:#1E88E5,stroke:#0D47A1,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef safeNode fill:#E53935,stroke:#B71C1C,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef switchNode fill:#8E24AA,stroke:#4A148C,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef simNode fill:#43A047,stroke:#1B5E20,stroke-width:2px,color:#ffffff;
    classDef evalNode fill:#3949AB,stroke:#1A237E,stroke-width:2px,color:#ffffff,font-weight:bold;

    ROOT["SELF-X Architectural Hierarchy"]:::ctrlNode

    ROOT --> INGESTION["1. Telemetry Ingestion Subsystem"]:::teleNode
    ROOT --> EPISODIC["2. Loss-Aware Episodic Memory Subsystem"]:::memNode
    ROOT --> REASONING["3. Hybrid Decision & Provider Subsystem"]:::ctrlNode
    ROOT --> SAFETY["4. Independent Deterministic Safety Gate"]:::safeNode
    ROOT --> SWITCHING["5. Simulated OpenFlow 1.3 Switching Engine"]:::switchNode
    ROOT --> SIMULATION["6. Finite-Buffer Fluid Network Simulation"]:::simNode
    ROOT --> REWARD["7. Counterfactual Reward & Reflection"]:::evalNode

    INGESTION --> TELE_RATES["Offered Rates: Primary (p), Alternate (a), Elephant (e)"]:::teleNode
    INGESTION --> TELE_QUEUES["Persistent Queue Occupancies: Q_primary, Q_alternate"]:::teleNode
    INGESTION --> TELE_FEATURES["8-Dimensional Normalized Feature Embedding Vector"]:::teleNode

    EPISODIC --> MEM_REGIME["Regime Partitioning: Sign of Congestion Margins"]:::memNode
    EPISODIC --> MEM_CALIPER["Caliper Filtering: Primary <= 0.12, Queues <= 0.51"]:::memNode
    EPISODIC --> MEM_KERNEL["Exponential Distance & Recency Kernel Weighting"]:::memNode
    EPISODIC --> MEM_CLUSTER["Headroom Parameter Clustering: 0.0, 0.1, 0.3 Mbps"]:::memNode
    EPISODIC --> MEM_PRUNING["Cell-Based Stratified Retention (Max 6/cell, Limit 128)"]:::memNode

    REASONING --> REASON_BYPASS["Tier 1: Healthy Bypass (Zero Queues, Fits Capacity)"]:::ctrlNode
    REASONING --> REASON_MEMORY["Tier 2: Supported Memory Policy (Support >= 3, Lower Bound > 0.005)"]:::ctrlNode
    REASONING --> REASON_CACHE["Tier 3: Exact-Context Action Cache (64 Slots, 12-Cycle TTL)"]:::ctrlNode
    REASONING --> REASON_DEADLINE["Tier 4: DeadlineProvider (Spawned Process, 3.8s Budget)"]:::ctrlNode
    REASONING --> REASON_FALLBACK["Tier 5: Deterministic Capacity-Aware Fallback Heuristic"]:::ctrlNode

    SAFETY --> SAFE_RATE["Rate Limit Rule: Flow Drop <= 20% (with +1 kbps Repair)"]:::safeNode
    SAFETY --> SAFE_ROUTE["Reroute Rule: Target Link Projected Load <= 90%"]:::safeNode
    SAFETY --> SAFE_FLOOR["Minimum Rate Limit Ceiling >= 512 kbps"]:::safeNode
    SAFETY --> SAFE_DISPATCH["Silent Fail-Closed Veto -> Default to no_op"]:::safeNode

    SWITCHING --> OF_ADD["ADD Flow-Mod (Match: in_port=1, dst=10.0.0.8, Priority=100)"]:::switchNode
    SWITCHING --> OF_METER["METER Entry (KBPS Flag, DROP Band, rate_limit_kbps)"]:::switchNode
    SWITCHING --> OF_TIMEOUT["hard_timeout = 5s (Synchronized with Control Cycle)"]:::switchNode
    SWITCHING --> OF_RESTORE["Automatic Rule Expiry & Baseline Port 2 Restoration"]:::switchNode

    SIMULATION --> FLUID_PATHS["Two Fixed-Capacity Logical Paths (C = 10 Mbps each)"]:::simNode
    SIMULATION --> FLUID_BUFFERS["Two Persistent Finite Buffers (B = 0.5 Mbit each)"]:::simNode
    SIMULATION --> FLUID_INTEGRAL["Piecewise-Linear Queue Area Integration"]:::simNode
    SIMULATION --> FLUID_CONSERVE["Conservation Law: Q_prev + Offered = Delivered + Dropped + Q_next"]:::simNode

    REWARD --> REWARD_PAIRED["Paired Same-Window Counterfactual no_op Baseline"]:::evalNode
    REWARD --> REWARD_WEIGHTS["Normalized Weights: Latency (-0.4), Tput (+0.4), Loss (-0.2)"]:::evalNode
    REWARD --> REWARD_REFLECT["Deterministic & Semantic LLM Reflection Engine"]:::evalNode
```

---

## 🎨 Detailed ASCII Architectural Flows

### 1. Complete End-to-End Control Pipeline Flow

```
====================================================================================================
                               SELF-X COMPLETE CONTROL PIPELINE FLOW
====================================================================================================

      [Traffic Demand Trace]                 [FluidNetwork Simulator]
      - Seeded 5-second windows               - Path 1: Primary (C=10M, B=0.5M)
      - p: Primary background (Mbps)          - Path 2: Alternate (C=10M, B=0.5M)
      - a: Alternate background (Mbps)        - Persistent Queues: Q1, Q2 (Mbit)
      - e: Elephant flow burst (Mbps)                    |
                 |                                       |
                 +-------------------+-------------------+
                                     |
                                     v
                       [Step 1: State Summarizer]
                       - Embedding features: [p/C, a/C, e/C, Q1/B, Q2/B, (p+e)/C]
                       - Feasibility margins: (p+e-C), (a+e-0.9C), (p+0.8e-C)
                       - Congestion regime: (Margin_p > 0, Margin_a > 0, Margin_m > 0)
                                     |
                                     v
                       [Step 2: Episodic Retrieval]
                       - LossAwareMemory (Up to 128 preserved episodes)
                       - Caliper distance filter & exponential recency weighting
                       - Candidate headroom uncertainty: 0.0, 0.1, 0.3 Mbps
                                     |
                                     v
                       [Step 3: Decision Arbiter]
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
  [Healthy Bypass]          [Supported Memory]            [Cache Hit]
  p + e <= C & Q == 0       Support >= 3 & LCB > 0.005    Exact Context Match
  -> no_op                  -> Rebuilt Meter              -> Cached Action
        |                            |                            |
        +----------------------------+----------------------------+
                                     | (If all fast paths miss)
                                     v
                       [Step 4: Deadline Provider]
                       - Fork/Spawn isolated child worker
                       - Pacing check (>= 4.2s gap for Gemini, >= 3.1s for OpenRouter)
                       - 3.8-second strict poll deadline
                       - Reusable HTTPS session pool
                                     |
                                     +-------------------------------+
                                     |                               |
                             [Valid API Result]            [Timeout / Error]
                             Compact JSON action           Kill child process
                                     |                               |
                                     v                               v
                       [Step 5: Safety Verification]   [Deterministic Fallback]
                       - Rate drop <= 20% (+1 kbps)    Capacity-aware policy
                       - Link utilization <= 90%                     |
                       - Rate floor >= 512 kbps                      |
                                     |                               |
                                     +---------------+---------------+
                                                     |
                                                     v
                                      [Step 6: Simulated Switch]
                                      - Expire previous cycle's rule
                                      - Install ADD rule (Priority 100)
                                      - Instructions: METER + OUTPUT 2/3
                                      - Hard timeout = 5 seconds
                                                     |
                                                     v
                                      [Step 7: Fluid Integration]
                                      - Advance simulation by T = 5s
                                      - Compute delivered volume & delay
                                      - Measure buffer drops & meter drops
                                      |
                                      v
                                      [Step 8: Counterfactual Reward]
                                      - Evaluate same-window no_op baseline
                                      - r = -0.4*dL/50 + 0.4*dT/5000 - 0.2*dLoss/20
                                      - Record semantic & deterministic reflection
                                                     |
                                                     v
                                      [Step 9: Memory Update & Pruning]
                                      - Append episode tuple to memory store
                                      - Stratified cell pruning (max 6 / cell)
                                      - Persist audit to trace.jsonl
====================================================================================================
```

### 2. Parent Controller & Subprocess Reusable Worker IPC Architecture

```
+==================================================================================================+
|                                    INTER-PROCESS COMMUNICATION (IPC)                             |
|                                                                                                  |
|   PARENT CONTROLLER PROCESS (Main Control Loop)             CHILD WORKER SUBPROCESS (Spawned)    |
|   ---------------------------------------------             ---------------------------------    |
|                                                                                                  |
|   +-------------------------------------------+                                                  |
|   | 1. BoundedController.decide()             |                                                  |
|   |    - Evaluates fast-path heuristics       |                                                  |
|   |    - If miss, initiates LLM request       |                                                  |
|   +-------------------------------------------+                                                  |
|                         |                                                                        |
|   +-------------------------------------------+                                                  |
|   | 2. Pacing Admission Check                 |                                                  |
|   |    - Enforces gap: monotonic() - last >= 4.2s                                                |
|   |    - If gap > budget - 1.25s -> DEFER     |                                                  |
|   +-------------------------------------------+                                                  |
|                         |                                                                        |
|   +-------------------------------------------+                                                  |
|   | 3. Pipe Connection Dispatch               |                                                  |
|   |    - connection.send(messages)            |============ multiprocessing.Pipe() =============>|
|   +-------------------------------------------+                        |                         |
|                         |                                              v                         |
|   +-------------------------------------------+             +----------------------------------+ |
|   | 4. Monitor Loop with Strict Deadline      |             | 5. Process Request               | |
|   |    - deadline = started + 3.8 seconds     |             |    - Set Gap = 0                 | |
|   |    - poll(0.05s slice)                    |             |    - Send: 'request_started'     | |
|   +-------------------------------------------+             |    - Post HTTPS Request          | |
|                         |                                   |    - Parse ActionChoice JSON     | |
|                         |<========== 'request_started' =====+----------------------------------+ |
|                         |                                              |                         |
|       +-----------------+-----------------+                            |                         |
|       | (Case A: Result Within 3.8s)      | (Case B: Timeout)          |                         |
|       v                                   v                            v                         |
|   +-----------------------+           +-----------------------+     +--------------------------+ |
|   | 6a. Receive 'result'  |           | 6b. Timeout Exceeded  |     | 7. Return Result Payload | |
|   |     Extract decision  |           |     Terminate Child   |     |    Send: 'result'        | |
|   |     Keep worker idle  |           |     Process.kill()    |====>|    Choice & Audit Logs   | |
|   |     Preserve session  |           |     Join & Clean Up   |     +--------------------------+ |
|   +-----------------------+           |     Raise Exception   |                                  |
|                                       +-----------------------+                                  |
+==================================================================================================+
```

### 3. Finite-Buffer Fluid Simulation Queue Integral & Saturation Dynamics

```
Queue Level
  ^
B |-----------------------------------------------------+  <- Buffer Ceiling (0.5 Mbit)
  |                                 /==================/|
  |                                /  Overflow Drop    /|  <- Dropped Volume = Net * (T - t_sat)
  |                               /====================/|
  |                              /                      |
  |                             /                       |
  |                            /                        |
  |                           /                         |
  |                          /                          |  <- Piecewise Linear Growth:
  |                         /                           |     dQ/dt = Net = (Admitted - C)
  |                        /                            |
Q0|                       /                             |  <- Initial Queue from Previous Window
  |                      /                              |
  |                     /                               |
  |                    /                                |
0 +-------------------+---------------------------------+--> Time (s)
  0                   t_sat                             T (5.0s)

Mathematical Formulations:
1. Saturation Time:       t_sat = (B - Q0) / (Admitted - C)
2. Final Queue:           Q_next = min(B, max(0.0, Q0 + Net * T))
3. Buffer Overflow:       Overflow = max(0.0, Q0 + Net * T - B)
4. Delivered Volume:      Delivered = Q0 + Admitted * T - Q_next - Overflow
5. Piecewise Queue Area:  Area = Integral[0 to T] Q(t) dt
                          = 0.5 * (Q0 + B) * t_sat + B * (T - t_sat)
6. Average Queue Depth:   Q_avg = Area / T
7. Modeled Path Delay:    Delay_i = 8.0 ms + (1000.0 * Q_avg / C) ms
```

---

## 💻 Subsystem Interface & Contract Specifications

### 1. LangGraph State Machine Schema (`selfx/agent/graph.py`)

```python
class GraphState(TypedDict, total=False):
    cycle: int
    raw_state_prev: Optional[dict]     # Carried in from previous cycle
    raw_state_before: dict            # State snapshot at start of cycle
    state_summary: dict               # Computed rates, queue depths, hot flows
    latency_before_ms: float          # Ping RTT probe before actuation
    decision: dict                    # Proposed action vector
    decision_attempts: int            # Retries performed
    safety_result: dict               # Allowed status, reason, safe_action
    installed_action: str             # Actually installed OpenFlow action
    raw_state_after: dict             # Telemetry snapshot after 5s window
    latency_after_ms: float           # Ping RTT probe after window
    metrics_before: dict              # Normalized metrics before
    metrics_after: dict               # Normalized metrics after
    reward: float                     # Normalized composite reward
    reward_breakdown: dict            # Latency, throughput, loss components
    reflection: str                   # Semantic reflection string
```

### 2. Safety Gate Contracts (`selfx/safety.py`)

```python
@dataclass
class SafetyContext:
    action: str                                     # "reroute" | "rate_limit" | "no_op"
    target_flow_rate_kbps: float = 0.0              # Current throughput of target flow
    proposed_rate_limit_kbps: float | None = None   # Proposed meter cap (rate_limit)
    target_link_capacity_kbps: float | None = None  # Candidate link capacity (reroute)
    target_link_current_kbps: float = 0.0           # Candidate link current load (reroute)

@dataclass
class SafetyResult:
    allowed: bool                                   # True if invariants are satisfied
    reason: str                                     # Explanation string (or veto justification)
    safe_action: str                                # Action to install: context.action or "no_op"
```

---

## 🏛️ Comprehensive Subsystem Specifications

### 1. Telemetry & Ingestion Subsystem (`selfx/agent/metrics.py`, `selfx/eval/simulator.py`)
- **Cumulative Counter Ingestion**: Interacts with OpenFlow counters via `get_state()`. Computes interval deltas divided by window length ($T = 5.0\text{ s}$).
- **Flow Key Indexing**: Uniquely indexes flows by `(dpid, match_items, priority, table_id)`. Detects resets and flow reinstalls.
- **Port Utilization Engine**: Computes normalized transmit byte rates against configured link capacity ($C = 10\text{ Mbps}$).
- **State Vector Embedding (`selfx/agent/embedding.py`)**: Transforms raw state into an 8-dimensional normalized unit vector:
  $$\vec{v} = \left[ \frac{p}{C},\, \frac{a}{C},\, \frac{e}{C},\, \frac{p+e-C}{C},\, \frac{a+e-0.9C}{C},\, \frac{p+0.8e-C}{C},\, \frac{Q_1}{B},\, \frac{Q_2}{B} \right]$$
  Vectors are normalized by Euclidean magnitude: $\hat{v} = \frac{\vec{v}}{\|\vec{v}\|_2}$.

### 2. Loss-Aware Episodic Memory Subsystem (`selfx/agent/loss_aware_memory.py`)
- **Storage Boundary**: Maximum capacity of 128 completed episodes. Retains parameter-conditioned records with actual headroom selection ($h \in \{0.0, 0.1, 0.3\}\text{ Mbps}$).
- **Stratified Pruning**: Buckets records into cells defined by:
  $$\text{Cell Key} = \left( \text{action},\, \text{headroom},\, \text{regime},\, \text{round}\left(\frac{\vec{v}_{[:3]}}{0.12}\right) \right)$$
  Retains the most recent 6 episodes per cell, discarding oldest entries to preserve behavioral and operational diversity.
- **Caliper Neighborhood & Kernel Distance**:
  $$\text{dist}^2 = \sum_{i=1}^6 (\Delta v_i)^2 + 0.08 \sum_{j=7}^8 (\Delta v_j)^2$$
  $$w = \exp\left(-\frac{\text{dist}^2}{0.02}\right) \times \exp\left(-\frac{\text{cycle} - \text{cycle}_{\text{ep}}}{120}\right)$$
- **Uncertainty Margin & Selection**:
  $$\text{LCB}(h) = \hat{\mu}_h - 1.96 \sqrt{\frac{\hat{\sigma}_h^2}{N_h}} - 0.002$$
  Requires $N_h \ge 3$ neighboring episodes for supported candidate selection.

### 3. Hybrid Control & Deadline Subsystem (`selfx/agent/bounded_control.py`, `selfx/agent/deadline_provider.py`)
- **Process Isolation**: Spawns isolated worker processes via Python `multiprocessing.get_context('spawn')` to decouple LLM network socket timeouts from the SDN controller loop.
- **Budget Allocation**: Total parent wait budget of 3.8 seconds. Allocates $\ge 1.0\text{ s}$ for network transport and $0.25\text{ s}$ for IPC termination/joining.
- **Pacing Engine**: Enforces strict inter-request pacing ($4.2\text{ s}$ for Gemini, $3.1\text{ s}$ for OpenRouter) to prevent cloud provider rate-limit throttling (HTTP 429).
- **Exact-Context Action Cache**: 64-entry LRU cache with a 12-window TTL. Validates signatures across offered rates, buffers, ports, and queue depths.

### 4. Independent Deterministic Safety Gate (`selfx/safety.py`)
- **Rate-Limit Guard**: Rejects any proposal where:
  $$\text{Drop \%} = 100 \times \frac{e - \text{rate\_limit\_kbps}}{e} > 20.0\% \quad \text{or} \quad \text{rate\_limit\_kbps} < 512\text{ kbps}$$
- **Reroute Guard**: Rejects any proposal where:
  $$\text{Projected Utilization} = 100 \times \frac{a + e}{C_{\text{alt}}} > 90.0\%$$
- **Fail-Closed Semantics**: If any check fails, the proposal is vetoed and converted to `no_op` for the cycle.

### 5. Switching & Rule Lifecycle Engine (`selfx/agent/rule_demo.py`)
- **Rule Construction**: Generates OpenFlow 1.3 `OFPFC_ADD` messages with priority 100 and `hard_timeout = 5`.
- **Instruction Sets**:
  - `reroute`: `APPLY_ACTIONS` $\to$ `OUTPUT: port 3`
  - `rate_limit`: `METER: meter_id` $\to$ `APPLY_ACTIONS` $\to$ `OUTPUT: port 2`
  - `no_op`: Default forwarding on primary `OUTPUT: port 2` (no rule installed)
- **Automatic Teardown**: Rules expire deterministically after 5 virtual seconds, returning the switch to default behavior.

---

## 🛠️ Step-by-Step Developer Guide: Extending the Architecture

### Adding a New State Embedding Dimension
1. Open [`selfx/agent/embedding.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/embedding.py).
2. Append the normalized feature (e.g., flow rate entropy $H_{\text{flow}} \in [0, 1]$):
   ```python
   def context(summary):
       # Existing 8 features
       features = [...]
       # Add 9th feature: normalized flow entropy
       features.append(summary.get('flow_entropy', 0.5))
       return features
   ```
3. Update `LossAwareMemory.meter_estimates` in [`selfx/agent/loss_aware_memory.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/loss_aware_memory.py) to include the new dimension in the Euclidean distance weighting array.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks*
