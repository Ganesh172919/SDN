# SELF-X Self-Improving Agent: Master ASCII Operational Flows

> **Exhaustive Sequence Diagrams, Pipeline Topologies, State Transitions, and Mathematical Flows in Pure ASCII**  
> *Course Project — EC466: Software Defined Networks | Team ID: SDN_07*

---

## 📌 Document Overview

This document provides the definitive, comprehensive collection of **ASCII Flows** for the **SELF-X Autonomous SDN Flow-Management Agent**. It renders complex temporal, mathematical, structural, and network processes in clean, universal ASCII formatting for immediate inspection across all terminal environments and documentation renderers.

---

## 🎨 Master ASCII Flow 1: Complete 7-Phase Control Loop Pipeline Sequence

```
Time (t)      Traffic & Network          Autonomous Cognitive Agent       OpenFlow 1.3 Switch
----------------------------------------------------------------------------------------------------
t = 0.0s      [Ingress Traffic Arrives]
              - p: Primary background
              - a: Alternate background
              - e: Elephant flow burst
                    |
                    v
t = 0.05s     [Phase 1: OBSERVE]
              - Query cumulative counters via ryu_client.get_state()
              - Ingest persistent queues: [Q1, Q2]
              - Assemble normalized 8-dim context vector:
                v = [p/C, a/C, e/C, Margin_P, Margin_A, Margin_M, Q1/B, Q2/B]
                    |
                    v
t = 0.10s     [Phase 2: RETRIEVE]
              - LossAwareMemory queries past completed episodes
              - Caliper filter: max(|Delta[:6]|) <= 0.12, max(|Delta[6:]|) <= 0.51
              - Cluster candidates by headroom h in {0.0, 0.1, 0.3} Mbps
              - Compute Lower Confidence Bound (LCB) for supported candidates
                    |
                    v
t = 0.15s     [Phase 3: DECIDE / PROPOSE]
              - Check Fast Tier 1: Healthy load bypass (p + e <= C & Q == 0 -> no_op)
              - Check Fast Tier 2: Supported memory action (support >= 3 & LCB > 0.005)
              - Check Fast Tier 3: Validated context cache (64-entry LRU, TTL <= 12)
              - If miss -> Dispatch Slow Tier 4: DeadlineProvider (3.8s subprocess)
              - If timeout/error -> Dispatch Fallback Tier 5: Local capacity policy
                    |
                    v
t = 0.20s     [Phase 4: VALIDATE]
              - Independent Deterministic Safety Gate:
                * Check 1: Flow drop <= 20.0% (with +1 kbps float repair)
                * Check 2: Target link projected utilization <= 90.0%
                * Check 3: Minimum rate limit floor >= 512 kbps
              - If unsafe -> VETO action -> Fallback to safe local rule
                    |
                    v
t = 0.25s     [Phase 5: ACT & INSTALL]
              - Expire previous 5-second rule at boundary ----> [Expire Old Flow-Mod]
              - Transmit OpenFlow 1.3 OFPFC_ADD command ------> [Install New Flow-Mod]
                * Priority: 100, hard_timeout: 5s               * Port 2 or Port 3
                * Instructions: METER + APPLY_ACTIONS           * Meter DROP Band
                    |                                                    |
                    |====================== 5-SECOND DATA PLANE WINDOW ==|
                    |                                                    |
t = 5.00s     [Phase 6: MEASURE & REFLECT]
              - Advance fluid simulation by T = 5.0s
              - Measure delivered goodput, average queue delay, and total loss
              - Evaluate same-window counterfactual no_op baseline
              - Compute normalized reward:
                r = -0.4 * (dL/50) + 0.4 * (dT/5000) - 0.2 * (dLoss/20)
              - Record deterministic & semantic LLM reflection
                    |
                    v
t = 5.05s     [Phase 7: MEMORIZE]
              - Store tuple: (cycle, state, action, params, reward, reflection)
              - Apply stratified cell pruning: retain top-6 per cell (max 128)
              - Commit record to trace.jsonl and memory store
                    |
                    v
t = 5.10s     [Advance to Next 5-Second Control Window]
```

---

## 🎨 Master ASCII Flow 2: Subprocess Isolation & Worker Pooling IPC Flow

```
+==================================================================================================+
|                                  SUBPROCESS WORKER ISOLATION & POOLING                           |
|                                                                                                  |
|   PARENT CONTROLLER PROCESS (Main Loop)                     CHILD WORKER PROCESS (Spawned)       |
|   -------------------------------------                     ------------------------------       |
|                                                                                                  |
|   1. Pacing Admission Check:                                                                     |
|      gap = monotonic() - last_started[provider]                                                  |
|      If gap < 4.2s (Gemini) -> sleep(gap)                                                        |
|      If gap > budget - 1.25s -> DEFER (avoid queue stall)                                        |
|                     |                                                                            |
|   2. Dispatch Message:                                                                           |
|      parent_conn.send(messages) ============= Pipe =============> child_conn.recv()              |
|                     |                                                       |                    |
|   3. Set Deadline:                                               3. Set Gap = 0                  |
|      deadline = started + 3.8s                                   4. Notify: 'request_started'    |
|                     |<================= Pipe ===============================|                    |
|   4. Record Start:                                                          |                    |
|      last_started[provider] = monotonic()                        5. Call Cloud REST API:         |
|                     |                                               - Persistent HTTPS Session   |
|   5. Monitor Loop:                                                  - Gemini / OpenRouter Free   |
|      while now < deadline:                                          - Parse ActionChoice JSON    |
|          poll(slice = 0.05s)                                                |                    |
|                     |                                                       |                    |
|       +-------------+-------------+                                         |                    |
|       |                           |                                         |                    |
|   (Case A: Result in Time)   (Case B: Deadline Miss)                        |                    |
|       |                           |                                         |                    |
|   6a. parent_conn.recv()      6b. Timeout Exceeded (t > 3.8s)               |                    |
|       Receive JSON result         Kill child process:                       |                    |
|       Audit logs updated          - process.terminate()                     |                    |
|       Keep worker alive           - process.kill()                          |                    |
|       Reuse HTTPS pool            - child dies cleanly                     |                    |
|       Adopt LLM action            Fall back to local rule                   v                    |
|       Proceed to validation       Proceed to validation          7. Return Payload via Pipe:     |
|                     |                           |                   parent_conn.send(result)     |
|                     v                           v                   Worker waits for next cycle  |
|          [Safety Guard Check]        [Safety Guard Check]                                        |
+==================================================================================================+
```

---

## 🎨 Master ASCII Flow 3: Fluid Network Queue Saturation & Area Calculus

```
Queue Level Q(t)
  ^
B |-----------------------------------------------------+  <- Buffer Limit (0.5 Mbit)
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
0 +-------------------+---------------------------------+--> Time t (seconds)
  0                   t_sat                             T (5.0s)

Detailed Integral Formulations:
----------------------------------------------------------------------------------------------------
1. Net Offered Traffic Rate:    Net = Admitted_Rate - Capacity_C
2. Buffer Saturation Time:      t_sat = (Buffer_B - Initial_Q0) / Net  (for Net > 0)
3. Ending Buffer Level:         Q_next = min(B, max(0.0, Q0 + Net * T))
4. Buffer Overflow Drops:       Overflow = max(0.0, Q0 + Net * T - B)
5. Delivered Volume:            Delivered = Q0 + Admitted_Rate * T - Q_next - Overflow
6. Piecewise Queue Area:        If saturated (t_sat < T):
                                  Area = 0.5 * (Q0 + B) * t_sat + B * (T - t_sat)
                                If draining to zero (t_drain < T):
                                  Area = 0.5 * Q0 * t_drain
                                If unsaturated:
                                  Area = 0.5 * (Q0 + Q_next) * T
7. Exact Average Queue Depth:   Q_avg = Area / T
8. Modeled Path Delay:          Delay_i = 8.0 ms + (1000.0 * Q_avg / C) ms
```

---

## 🎨 Master ASCII Flow 4: Core Bottleneck Mininet Topology & Traffic Multipath

```
+====================================================================================================+
|                                    MININET EMULATION TESTBED                                       |
|                                                                                                    |
|    [h1: 10.0.0.1]---\ (100M, 1ms)                                     /---[h7: 10.0.0.7]           |
|                      +---[s1: dpid 0x1]                            [s4: dpid 0x4]---+              |
|    [h2: 10.0.0.2]---/        |                                           |        \---[h8: 10.0.0.8]           |
|                              |                                           |                         |
|                       Trunk: 20 Mbps                              Trunk: 20 Mbps                   |
|                        Delay: 2ms                                  Delay: 2ms                      |
|                              |                                           |                         |
|    [h3: 10.0.0.3]---\        v                                           v        /---[h5: 10.0.0.5]           |
|                      +---[s2: dpid 0x2]                            [s3: dpid 0x3]---+              |
|    [h4: 10.0.0.4]---/      /          \                            /         \    \---[h6: 10.0.0.6]           |
|                           /            \                          /           \                    |
|                          /              \                        /             \                   |
|       +-----------------+                +----------------------+               +-------------+    |
|       |                                                                                       |    |
|       |   [PRIMARY LINK A] (Core Bottleneck):                                                 |    |
|       |   - Bandwidth: 10 Mbps, Propagation Delay: 5 ms                                       |    |
|       |   - Buffer Queue Size: 40 packets (0.5 Mbit)                                          |    |
|       |   - Default Route for steady background + elephant flows                              |    |
|       |                                                                                       |    |
|       |   [ALTERNATE LINK B] (Secondary / Reroute Path):                                      |    |
|       |   - Bandwidth: 10 Mbps, Propagation Delay: 12 ms                                      |    |
|       |   - Buffer Queue Size: 40 packets (0.5 Mbit)                                          |    |
|       |   - Alternate path activated dynamically when Primary Link is congested               |    |
|       +---------------------------------------------------------------------------------------+    |
|                                                                                                    |
|                                 OpenFlow 1.3 Control Channel                                       |
|                         +------------------------------------------+                               |
|                         |    RemoteController (c0: 127.0.0.1:6653) |                               |
|                         +------------------------------------------+                               |
+====================================================================================================+
```

---

## 🎨 Master ASCII Flow 5: Parameter Headroom Exploration & Uncertainty LCB Flow

```
Query Context: [ p/C, a/C, e/C, Margins, Queues ]
                      |
                      v
       +------------------------------+
       | Query LossAwareMemory Store  |
       | Filter by Congestion Regime  |
       +------------------------------+
                      |
                      v
       +------------------------------+
       | Caliper Neighborhood Filter  |
       | max(|Delta_v[:6]|) <= 0.12   |
       | max(|Delta_v[6:]|) <= 0.51   |
       +------------------------------+
                      |
                      v
       +------------------------------------------------------------+
       | Dual-Kernel Distance Weighting:                            |
       | dist^2 = sum(Delta[:6]^2) + 0.08 * sum(Delta[6:]^2)        |
       | w = exp(-dist^2 / 0.02) * exp(-(cycle - cycle_ep) / 120)   |
       +------------------------------------------------------------+
                      |
                      v
       +------------------------------------------------------------+
       | Cluster Neighbors by Headroom Candidate:                   |
       | h = 0.0 Mbps,  h = 0.1 Mbps,  h = 0.3 Mbps                 |
       | Select nearest 6 observations per candidate                |
       +------------------------------------------------------------+
                      |
                      v
       +------------------------------------------------------------+
       | Compute Support & Lower Confidence Bound (LCB):            |
       | mu = sum(w * reward) / sum(w)                              |
       | var = sum(w * (reward - mu)^2) / sum(w)                    |
       | LCB(h) = mu - 1.96 * sqrt(var / N) - 0.002                 |
       +------------------------------------------------------------+
                      |
            +---------+---------+
            |                   |
     (Any Support < 3)    (All Support >= 3)
            |                   |
            v                   v
     [EXPLORATION PHASE]   [EXPLOITATION PHASE]
     Select unsupported    Select candidate with
     headroom candidate    maximum LCB:
     to gather evidence    max(LCB(h))
```

---

## 🎨 Master ASCII Flow 6: Binary Floating-Point Rounding Repair Arithmetic Flow

```
====================================================================================================
                        20% FLOW-DROP GUARD BOUNDARY & REPAIR
====================================================================================================

Problem Context:
- Elephant flow rate e = 8.06 Mbps (8060 kbps).
- The maximum permissible throttling is exactly 20.0%:
    Allowed Cap = 0.80 * 8060 kbps = 6448.0 kbps.
- In binary floating-point arithmetic (IEEE 754 double precision):
    e * 1000 = 8060.0
    cap = 0.80 * 8.06 = 6.448
    ceil(cap * 1000) = 6448 kbps
- Guard dropped percentage calculation:
    dropped_pct = 100.0 * (8060.0 - 6448) / 8060.0
                = 100.0 * 1612.0 / 8060.0
                = 20.000000000000004%  (Binary subtraction precision artifact!)
- Guard Condition:
    if dropped_pct > 20.0:  --> Evaluates to TRUE! (Vetoed incorrectly as unsafe!)

Engineered Solution in `loss_aware_memory.py`:
```python
# Check if binary rounding caused dropped percentage to exceed 20%
if 100.0 * (e * 1000 - d.rate_limit_kbps) / (e * 1000) > 20.0:
    d.rate_limit_kbps += 1  # Admit exactly 1 extra kbps: 6449 kbps
```
Outcome:
- With rate_limit_kbps = 6449:
    dropped_pct = 100.0 * (8060 - 6449) / 8060 = 19.98759% <= 20.0%
- Result: Perfectly satisfies the strict, independent, unmodified safety guard!
====================================================================================================
```

---

## 🎨 Master ASCII Flow 7: OpenFlow 1.3 Flow Modification & Rule Expiry State Machine

```
Virtual Cycle 0 (0s - 5s)               Virtual Cycle 1 (5s - 10s)              Virtual Cycle 2 (10s - 15s)
[Healthy Load: p+e <= 10M]              [Primary Burst: p+e > 10M]              [Both Busy: Alternate Saturated]
----------------------------------------------------------------------------------------------------------------
Installed Rule: (None)                  Installed Rule: REROUTE                 Installed Rule: RATE_LIMIT
Port Forwarding: Port 2 (Default)       Port Forwarding: Port 3 (Alternate)     Port Forwarding: Port 2 + METER
hard_timeout: -                         hard_timeout: 5 seconds                 hard_timeout: 5 seconds
----------------------------------------------------------------------------------------------------------------
      |                                       |                                       |
      | 1. Observe healthy load               | 1. Detect bottleneck congestion       | 1. Alternate link busy (a > 7M)
      | 2. Bypass fast path                   | 2. Alternate link has headroom        | 2. Reroute would cause overload
      | 3. Default forwarding                 | 3. Propose 'reroute'                  | 3. Propose 'rate_limit' (4900k)
      |                                       | 4. Safety Guard: ALLOWED              | 4. Safety Guard: ALLOWED
      |                                       | 5. Install OFPFC_ADD:                 | 5. Expire Cycle 1 rule at 10.0s
      |                                       |    Cookie: 2, Priority: 100           | 6. Install OFPFC_ADD:
      |                                       |    Match: in_port=1, dst=10.0.0.8     |    Cookie: 3, Priority: 100
      |                                       |    Instructions: OUTPUT: port 3       |    Instructions: METER 4900
      |                                       |                                       |    OUTPUT: port 2
      v                                       v                                       v
[Default Port 2 Active]                 [Port 3 Flow-Mod Active]                [Meter Flow-Mod Active]
(t = 0.0s to 5.0s)                      (t = 5.0s to 10.0s)                     (t = 10.0s to 15.0s)
                                              |                                       |
                                              v                                       v
                                        [EXPIRES at t = 10.0s]                  [EXPIRES at t = 15.0s]
                                        Clean boundary teardown                 Clean boundary teardown
```

---

## 🎨 Master ASCII Flow 8: 86,400-Window Matrix & Bootstrap Resampling Pipeline

```
====================================================================================================
                        86,400-WINDOW MATRIX & BOOTSTRAP PIPELINE
====================================================================================================

 Raw Execution Grid:
 -------------------
   8 Scenarios:  [mixed, flash, alternate, shift, overload, light, recurring, volatile]
   10 Seeds:     [1900, 1901, 1902, 1903, 1904, 1905, 1906, 1907, 1908, 1909]
   9 Controllers:[A0, B1, A2, H1, A3, V3, H2, A4, O2]
   120 Windows:  5.0 seconds each (600 simulated seconds per condition)
   Total Windows: 8 * 10 * 9 * 120 = 86,400 simulation windows

 Raw Data Logging:
 -----------------
   Row Tuple: (scenario, condition, seed, cycle, latency_ms, goodput_kbps, loss_pct, reward, ...)
   Stored at: output/benchmarks/v4/metrics.csv (86,400 CSV lines)

 Statistical Aggregation Pipeline:
 ---------------------------------
   Step 1: Compute Seed Means
           For each (scenario, controller, seed):
               Metric_Mean = (1/120) * sum(Window_Metrics)

   Step 2: Paired Seed Differences
           For each seed s:
               Delta[s] = Mean_A4[s] - Mean_Baseline[s]

   Step 3: 4,000-Draw Percentile Bootstrap Resampling (RNG Seed 4099)
           For draw = 1 to 4000:
               Resample 10 seed deltas WITH REPLACEMENT
               Calculate bootstrap mean difference: Delta_draw

   Step 4: Non-Parametric 95% Confidence Interval Derivation
           Sort 4,000 sample means: Delta_(1) <= ... <= Delta_(4000)
           Lower 95% CI: 2.5th percentile  = Delta_(100)
           Upper 95% CI: 97.5th percentile = Delta_(3900)

   Output: output/benchmarks/v4/summary.json (Locked statistical metadata and digests)
====================================================================================================
```
