# SELF-X Audited Algorithm Comparison: Full Mathematical & Empirical Specification

> **Formal Specification of the 14-Controller Audited CPU Comparison Suite**
> *Module: `selfx/eval/run_audited_comparison.py` | Data Source: `paper/comparison/runs.json` & `effects.json`*
> *Component Guide — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*

---

## 📌 Table of Contents
1. [Executive Summary & Benchmarking Philosophy](#executive-summary--benchmarking-philosophy)
2. [Fluid Datapath Mathematical Formulation](#fluid-datapath-mathematical-formulation)
   - [Topology & Link Capacities](#topology--link-capacities)
   - [Queue Dynamics & Conservation Laws](#queue-dynamics--conservation-laws)
   - [Delay & Loss Decomposition](#delay--loss-decomposition)
3. [The 14 Evaluated Control Architectures](#the-14-evaluated-control-architectures)
   - [The Primary Agentic Progression (S0 through S5)](#the-primary-agentic-progression-s0-through-s5)
   - [Traditional & Reinforcement Learning Baselines](#traditional--reinforcement-learning-baselines)
   - [Ablation Arms (Decoupling Components)](#ablation-arms-decoupling-components)
4. [Control Cadences & Simulated Execution Latency](#control-cadences--simulated-execution-latency)
5. [Deterministic Safety Guard & Action Clamping](#deterministic-safety-guard--action-clamping)
6. [Workload Profiles & Seed Assignments](#workload-profiles--seed-assignments)
7. [Statistical Analysis & Multiple Testing Correction](#statistical-analysis--multiple-testing-correction)
   - [Profile-Stratified Mean Paired Difference](#profile-stratified-mean-paired-difference)
   - [Welch-Satterthwaite Paired Student's t-Test](#welch-satterthwaite-paired-students-t-test)
   - [Holm-Bonferroni Step-Down Correction](#holm-bonferroni-step-down-correction)
   - [20,000-Draw Stratified Bootstrap Resampling](#20000-draw-stratified-bootstrap-resampling)
8. [Scientific Attribution & Key Empirical Findings](#scientific-attribution--key-empirical-findings)

---

## 🏛️ Executive Summary & Benchmarking Philosophy

In modern software-defined networking research, claiming superiority for LLM-driven or multi-agent controllers often suffers from reproducibility gaps, unverified baseline implementations, or hidden simulation shortcuts.

The **SELF-X Audited Comparison Suite** (`selfx/eval/run_audited_comparison.py`) addresses this by enforcing **100% auditable CPU execution**:
1. **Real Inference**: Runs local CPU inference using Hugging Face `SmolLM2-135M-Instruct` and the trained LoRA adapter checkpoint without mocks or random number generators.
2. **Real Deep Learning Baselines**: Fully trains deep neural architectures (DQN and Two-Agent Independent Q-Learning) with PyTorch experience replay and target networks.
3. **Cryptographic Trace Auditing**: Every offered traffic burst, model weight matrix, and effective per-slot forwarding decision is hashed via SHA-256 (`effective_actions_sha256`), so the verifier can compare those artifacts across reruns.
4. **Shared Fluid Datapath**: All 14 configurations are evaluated against identical bit-for-bit synthetic traffic schedules on the same underlying physical equations.

---

## 🌊 Fluid Datapath Mathematical Formulation

The datapath model simulates a software-defined network with dual forwarding paths connecting ingress and egress switches:

```
                  +----------------------------------------------+
                  |  Primary Path: C1 = 10 Mbps, d1 = 2 ms, B1   |
           +----->|  (Bottleneck: Hosts h1->h7 + h2->h8 Surge)   |-----+
           |      +----------------------------------------------+     |
           |                                                           v
[ Ingress s1 ]                                                   [ Egress s4 ]
           |      +----------------------------------------------+     ^
           +----->|  Secondary Path: C2 = 10 Mbps, d2 = 12 ms, B2 |-----+
                  |  (Alternate Path: Higher Propagation Delay)  |
                  +----------------------------------------------+
```

### Topology & Link Capacities
- **Primary Path ($P_1$)**: High-speed, low-propagation link.
  - Bandwidth Capacity: $C_1 = 10.0\,\text{Mbps} = 1.0\,\text{Mbit/slot}$ (for $\Delta t = 100\,\text{ms}$).
  - Propagation Delay: $d_1 = 2.0\,\text{ms}$.
  - Buffer Depth: $B_1 = 2.0\,\text{Mbit}$ ($250\,\text{KB}$).
- **Secondary Path ($P_2$)**: Alternate reroute path.
  - Bandwidth Capacity: $C_2 = 10.0\,\text{Mbps} = 1.0\,\text{Mbit/slot}$.
  - Propagation Delay: $d_2 = 12.0\,\text{ms}$ (10 ms latency penalty).
  - Buffer Depth: $B_2 = 2.0\,\text{Mbit}$.

### Queue Dynamics & Conservation Laws
Time is discretized into control slots of length $\tau = 100\,\text{ms}$. For each path $k \in \{1, 2\}$, let:
- $A_k(t)$: Ingress traffic offered to path $k$ during slot $t$ (Mbit).
- $Q_k(t)$: Fluid queue backlog at the start of slot $t$ (Mbit).
- $S_k(t)$: Service rate during slot $t$, bounded by capacity: $S_k(t) = \min(Q_k(t) + A_k(t), C_k \cdot \tau)$.

The queue evolves according to Lindley's recurrence relation:
$$Q_k(t+1) = \min\Big( B_k, \, \max\big(0, \, Q_k(t) + A_k(t) - C_k \cdot \tau \big) \Big)$$

If the offered traffic plus existing queue exceeds buffer capacity $B_k$, packet drop occurs:
$$L_k(t) = \max\Big(0, \, Q_k(t) + A_k(t) - C_k \cdot \tau - B_k \Big)$$

### Delay & Loss Decomposition
For packets successfully delivered across path $k$ during slot $t$:
1. **Queuing Delay**: $D_{\text{queue}, k}(t) = \frac{Q_k(t) + \frac{1}{2} A_k(t)}{C_k}$
2. **Total End-to-End Delay**: $D_k(t) = d_k + D_{\text{queue}, k}(t)$
3. **Aggregate Mean Delay**: Weighted across transmitted bits on both paths:
   $$\bar{D}(t) = \frac{S_1(t) D_1(t) + S_2(t) D_2(t)}{S_1(t) + S_2(t)}$$

---

## 🤖 The 14 Evaluated Control Architectures

The benchmark evaluates 14 distinct controllers spanning baseline, heuristic, learned, and agentic paradigms:

| Config ID | Controller Name | Paradigm | Control Cadence | Description |
| :---: | :--- | :--- | :---: | :--- |
| **S0** | Static Default | Baseline | None | All traffic routed across primary path; zero dynamic control. |
| **S1** | Base LM | LLM | 5 s | Raw `SmolLM2-135M` greedy token generation predicting action token. |
| **S2** | Base LM + Critique | LLM Reflexion | 5 s | S1 plus a verbal critique pass over proposal and 3 prior window outcomes. |
| **S3** | LoRA Policy | LLM Parametric | 5 s | Same prompt as S1 but using the fine-tuned LoRA adapter ($r=8, \alpha=16$). |
| **S4** | Agentic at 5 s | Decoupled Agentic | 5 s | Full DPP + LoRA + Governor stack, but throttled to 5 s decision intervals. |
| **S5** | **SELF-X (Complete)** | **Two-Timescale** | **100 ms** | **Fast 100 ms DPP + 5 s LoRA preference prior + 30 s multi-agent governor.** |
| **threshold** | Capacity Threshold | Heuristic | 5 s | Reroutes elephant flow when primary link utilization exceeds 70%. |
| **least_loaded**| Least Loaded | Heuristic | 5 s | Directs incoming bursts to whichever path has smaller queue depth. |
| **tabular_q** | Tabular Q-Learning | Classic RL | 5 s | Discretized state table updating online via $\epsilon$-greedy Q-learning. |
| **dqn** | Deep Q-Network | Deep RL | 100 ms | 2-layer MLP (64 units), experience replay (20k), target network updates. |
| **marl** | Two-Agent IQL | Multi-Agent RL | 100 ms | Independent Q-learning: Agent 1 (routing) + Agent 2 (metering). |
| **dpp** | DPP Only | Control Theory | 100 ms | Pure quadratic Lyapunov drift-plus-penalty queue minimization. |
| **no_lora** | Agentic w/o LoRA | Ablation | 100 ms | Complete SELF-X stack with LoRA action prior disabled. |
| **no_governor** | Agentic w/o Governor| Ablation | 100 ms | Complete SELF-X stack with slow-loop multi-agent governor disabled. |

---

## ⏱️ Control Cadences & Simulated Execution Latency

A core contribution of the audited benchmark is modeling **computational inference latency**:
- **Fast Datapath Slot ($\tau = 100\,\text{ms}$)**: Lyapunov DPP and greedy neural inference operate at wire rate (<1 ms).
- **Aggregated Window ($T = 5\,\text{s} = 50\,\text{slots}$)**: Telemetry features are aggregated over 5-second windows for high-level decision makers.
- **Model Forward Latency Penalty**:
  - Direct LM pass (S1, S3): Assigned $400\,\text{ms}$ latency penalty (4 slots of delayed action application).
  - Critique pass (S2): Two forward passes $\to 800\,\text{ms}$ latency penalty (8 slots).
  - Multi-Agent Governor (S4, S5): 5 specialist prompts run in parallel batch, followed by 1 orchestrator prompt $\to 800\,\text{ms}$ latency penalty (8 slots).
- **Governance Epoch ($T_{\text{gov}} = 30\,\text{s} = 6\,\text{windows} = 300\,\text{slots}$)**: The multi-agent specialist ensemble convenes every 30 seconds to adjust the DPP objective parameters.

---

## 🛡️ Deterministic Safety Guard & Action Clamping

Every candidate action proposed by any controller passes through an immutable, fail-closed safety gate (`safety.safe_action`) before affecting datapath queues:

```python
def safe_action(action, elephant_kbps):
    # Invariant 1: Alternate path projected load must not exceed 90%
    if action.routing == "alternate" and projected_alternate_load > 0.90 * C_ALTERNATE:
        return Action(routing="primary", metering="none"), "VETO: Alternate path near saturation"

    # Invariant 2: Metering floor >= 512 kbps, maximum reduction <= 20%
    if action.metering == "clamp":
        safe_rate = max(512.0, elephant_kbps * 0.80)
        return Action(routing=action.routing, rate_kbps=safe_rate), None

    return action, None
```

- **Guaranteed Loop-Freedom**: No circular route definitions.
- **Buffer Overflow Prevention**: Prevents aggressive rerouting from slamming the alternate queue into continuous drops.

---

## 📊 Workload Profiles & Seed Assignments

The benchmark evaluates 12 test seeds across 3 distinct workload regimes:

| Profile | Test Seeds | Description |
| :--- | :--- | :--- |
| **`steady_bursty`** | 2100, 2103, 2106, 2109 | Continuous 4 Mbps background UDP mice flows with Poisson-distributed 14 Mbps elephant bursts. |
| **`flash_crowd`** | 2101, 2104, 2107, 2110 | Sudden, sustained 14 Mbps burst at $T = 30\,\text{s}$ creating an immediate primary path bottleneck. |
| **`volatile_dpp`** | 2102, 2105, 2108, 2111 | Rapidly oscillating flow arrival rates challenging Lyapunov drift-plus-penalty tracking. |

- **Training Seeds**: 1000–1017 (18 seeds $\times$ 120 s = 21,600 slots) used exclusively for training the neural baselines (DQN and MARL).
- **Evaluation Seeds**: 2100–2111 (12 seeds $\times$ 180 s = 21,600 slots per configuration) strictly held out from training.

---

## 📐 Statistical Analysis & Multiple Testing Correction

### Profile-Stratified Mean Paired Difference
To prevent any single traffic profile from dominating the overall estimate, the primary outcome is calculated as the unweighted average across the 3 profile means:
$$\Delta = \frac{1}{3} \sum_{p=1}^3 \bar{d}_p, \quad \text{where } \bar{d}_p = \frac{1}{4} \sum_{s \in \text{Seed}_p} \left( \text{Delay}(S_5, s) - \text{Delay}(\text{Baseline}, s) \right)$$

### Welch-Satterthwaite Paired Student's t-Test
The variance of the stratified estimator accounts for profile-specific variance components:
$$s^2(\Delta) = \frac{1}{9} \sum_{p=1}^3 \frac{s_p^2}{4}, \quad t = \frac{\Delta}{s(\Delta)}$$
Degrees of freedom are computed via the Welch–Satterthwaite formula:
$$\nu = \frac{\left( \sum_{p=1}^3 s_p^2 \right)^2}{\sum_{p=1}^3 \frac{(s_p^2)^2}{n_p - 1}}$$

### Holm-Bonferroni Step-Down Correction
To control the Family-Wise Error Rate (FWER) across all $M = 13$ comparisons against $S_5$:
1. Sort raw p-values in ascending order: $p_{(1)} \le p_{(2)} \le \dots \le p_{(M)}$.
2. Compute adjusted p-values:
   $$p_{(k)}^{\text{adj}} = \min\left( 1.0, \, \max_{j \le k} \big( (M - j + 1) \cdot p_{(j)} \big) \right)$$
3. An arm is declared statistically significant at $\alpha = 0.05$ if $p_{(k)}^{\text{adj}} < 0.05$.

### 20,000-Draw Stratified Bootstrap Resampling
In addition to parametric t-tests, empirical confidence intervals are estimated via $B = 20,000$ stratified bootstrap draws (`selfx/eval/revision_analysis.py`).

---

## 🏆 Scientific Attribution & Key Empirical Findings

```
====================================================================================================
                        EMPIRICAL PERFORMANCE SUMMARY (180s Traces)
====================================================================================================
 Configuration               Mean Delay (ms)   Delta Delay (ms)   Holm-Adjusted p   Significance
----------------------------------------------------------------------------------------------------
 S0 (Static Default)             80.88             -20.34            < 0.0001          *** (p < 0.001)
 S1 (Base LM at 5s)              78.42             -17.88            < 0.0001          *** (p < 0.001)
 S2 (Base LM + Critique)         78.42             -17.88            < 0.0001          *** (p < 0.001)
 S3 (LoRA Policy at 5s)          75.10             -14.56            < 0.0001          *** (p < 0.001)
 S4 (Agentic at 5s)              71.77             -11.23            < 0.0001          *** (p < 0.001)
 S5 (SELF-X Complete)            60.54               0.00               --             (Reference)
 DQN (Deep Q-Network)            61.29              -0.75              0.0014          **  (p < 0.01)
 MARL (Two-Agent IQL)            61.29              -0.75              0.0014          **  (p < 0.01)
 DPP Only (Control Theory)       60.42              +0.12              0.0740          n.s. (p >= 0.05)
----------------------------------------------------------------------------------------------------
```

### Key Scientific Conclusions
1. **Decision Cadence Dominance**: Moving from a 5-second control cadence (S4) to a 100 ms fast-loop cadence (S5) accounts for a **15.65% reduction in delay** ($71.77\,\text{ms} \to 60.54\,\text{ms}$).
2. **Neural Guard Parity**: Although DQN and Two-Agent IQL propose different raw actions in 14.2% of control slots, the deterministic safety guard maps both to identical effective actions on the hardware. Their datapath delay and loss curves match 100%.
3. **Critique Zero-Revision Invariant**: In S2 (Base LM + Critique), across 432 critique requests and 420 non-empty historical memory prompts, the critique stage revised **zero** initial proposals. Performance differences between S1 and S2 are strictly zero.
4. **LoRA Parametric Efficiency**: The LoRA adapter ($r=8$) successfully steered the DPP prior across 2,920 control intervals without requiring full backbone parameter updates.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
