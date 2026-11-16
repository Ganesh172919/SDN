# SELF-X Autonomous Control Plane: Agent Subsystem Specification

> **Production Guide to the Decoupled Two-Timescale Architecture, Fast Lyapunov DPP Loop, Multi-Agent Governor, and Parametric Self-Improvement**  
> *Module Directory: `selfx/agent/` | Primary Runtimes: Python 3.12 Standard Library, PyTorch, Hugging Face Transformers*  
> *Component Guide — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*  
> *Document Version: 2.4.0-Production*

---

## 📌 Table of Contents
1. [Architectural Overview & Two-Timescale Decoupling](#architectural-overview--two-timescale-decoupling)
2. [Fast-Timescale Control Loop (100 ms)](#fast-timescale-control-loop-100-ms)
   - [Quadratic Lyapunov Drift-Plus-Penalty Formulation](#quadratic-lyapunov-drift-plus-penalty-formulation)
   - [Candidate Routing & Ingress Clamping Evaluation](#candidate-routing--ingress-clamping-evaluation)
   - [Stability Proof & Backlog Bound Verification](#stability-proof--backlog-bound-verification)
3. [Slow-Timescale Multi-Agent Governor (30–120 s)](#slow-timescale-multi-agent-governor-30120-s)
   - [Six-Agent Specialist Hierarchy](#six-agent-specialist-hierarchy)
   - [Episodic Reflection & Stratified Caliper Retrieval](#episodic-reflection--stratified-caliper-retrieval)
   - [Subprocess-Isolated LLM Inference & Watchdog Cutoffs](#subprocess-isolated-llm-inference--watchdog-cutoffs)
4. [Atomic Inter-Loop Bridge (`delta_pi_bridge.py`)](#atomic-inter-loop-bridge-delta_pi_bridgepy)
5. [Action Gateway, Safety Invariants & Hardware Readback](#action-gateway-safety-invariants--hardware-readback)
   - [The Three Hard Mathematical Safety Invariants](#the-three-hard-mathematical-safety-invariants)
   - [OpenFlow 1.3 Rule Compilation & Lease Rollback](#openflow-13-rule-compilation--lease-rollback)
   - [Hardware Readback Audit](#hardware-readback-audit)
6. [Parametric Self-Improvement & LoRA Adaptation (`self_improvement/`)](#parametric-self-improvement--lora-adaptation-self_improvement)
   - [Replay Dataset Synthesis & Feature Normalization](#replay-dataset-synthesis--feature-normalization)
   - [SmolLM2-135M Low-Rank Adaptation (LoRA)](#smollm2-135m-low-rank-adaptation-lora)
   - [Fail-Closed Benchmark Stress Promotion Gate](#fail-closed-benchmark-stress-promotion-gate)
   - [Atomic Hot-Swapping & Instant Rollback](#atomic-hot-swapping--instant-rollback)
7. [Subsystem File Manifest & Component Responsibilities](#subsystem-file-manifest--component-responsibilities)

---

## 🏛️ Architectural Overview & Two-Timescale Decoupling

In software-defined networks carrying high-velocity traffic, flow bursts and queue buildup occur on millisecond timescales ($10\text{--}100\,\text{ms}$), while cognitive language model inference and multi-agent debate require several hundred milliseconds to seconds ($400\text{--}2,000\,\text{ms}$). Running language models directly in the packet forwarding path creates intolerable queuing delays, buffer overflows, and forwarding stalls.

SELF-X resolves this fundamental dilemma through a **Decoupled Two-Timescale Architecture**:

```
====================================================================================================
                        TWO-TIMESCALE DECOUPLED CONCURRENCY ARCHITECTURE
====================================================================================================

      SLOW-TIMESCALE GOVERNANCE LOOP (30 - 120 s)
      +------------------------------------------------------------------------------------------+
      |  Episodic Reflection & Root-Cause Diagnosis (SmolLM2-135M / Multi-Agent Ensemble)        |
      |  - Flow Sizing Specialist       - Congestion Specialist      - Security Specialist       |
      |  - Path Routing Specialist      - Safety Specialist          - Orchestrator Consensus    |
      |                                                                                          |
      |  Generates: Objective Weight Vector delta_pi = (w_delay, w_loss, w_energy, V_param)      |
      +------------------------------------------------------------------------------------------+
                                                   |
                                                   v  (Thread-Safe Atomic Pointer Swap)
      ====================================[ delta_pi_bridge.py ]==================================
                                                   |
                                                   v
      FAST-TIMESCALE WIRE-RATE CONTROLLER (100 ms Slot, < 1 ms Decision)
      +------------------------------------------------------------------------------------------+
      |  Lyapunov Drift-Plus-Penalty (DPP) Controller (dpp_controller.py)                        |
      |  - Ingests: 8D Feature Vector S(t) = (Q_1, Q_2, Ingress_rate, Drop_rate, ...)           |
      |  - Solves: argmin_{a} [ Delta L(Q(t)) + V * g(t, a) - LoRA_prior * 1_{preferred}(a) ]   |
      |  - Guaranteed Compliance: 100% of slots bounded below (B + V * C_max) / epsilon          |
      +------------------------------------------------------------------------------------------+
                                                   |
                                                   v
      +------------------------------------------------------------------------------------------+
      |  Deterministic Safety Guard & Action Gateway (action_gateway.py, safety.py)              |
      |  - Invariant 1: Alternate path load <= 90%                                               |
      |  - Invariant 2: Rate limit floor >= 512 kbps                                             |
      |  - Invariant 3: Maximum bulk reduction <= 20%                                            |
      +------------------------------------------------------------------------------------------+
                                                   |
                                                   v (OpenFlow 1.3 FlowMod & MeterMod)
                                    [ Switch TCAM & Hardware Tables ]
====================================================================================================
```

---

## ⚡ Fast-Timescale Control Loop (100 ms)

The fast-timescale engine (`dpp_controller.py`) executes every $\tau = 100\,\text{ms}$ in $<1\,\text{ms}$ per decision slot, operating directly on fluid queue measurements.

### Quadratic Lyapunov Drift-Plus-Penalty Formulation
Let $Q(t) = [Q_1(t), Q_2(t)]^T$ represent the queue backlogs across the primary and secondary network paths. The quadratic Lyapunov function is defined as:
$$L(Q(t)) = \frac{1}{2} \sum_{i=1}^2 Q_i(t)^2$$
The one-slot Lyapunov drift represents the expected change in quadratic queue backlog:
$$\Delta(Q(t)) = \mathbb{E}\big[ L(Q(t+1)) - L(Q(t)) \mid Q(t) \big]$$

Incorporating operational penalty $g(t)$ (a weighted sum of end-to-end delay, packet loss, energy consumption, and rule churn) weighted by the Lyapunov trade-off parameter $V > 0$, the controller solves the Drift-Plus-Penalty objective:
$$\min_{a \in \mathcal{A}} \Big[ \Delta(Q(t)) + V \cdot g(t, a) - \lambda_{\text{LoRA}} \cdot \mathbf{1}_{\{a = a_{\text{LoRA}}\}} \Big]$$
where $\lambda_{\text{LoRA}} = 0.20$ acts as a prior preference bonus if the proposed action is safe and feasible.

### Candidate Routing & Ingress Clamping Evaluation
In each 100 ms slot, the controller evaluates candidate actions $a = (\text{route}, \text{meter})$:
1. `no_op`: Maintain default forwarding on the primary path.
2. `reroute`: Move elephant flow burst to the secondary path ($d_2 = 12\,\text{ms}$).
3. `rate_limit`: Clamp ingress rate via OpenFlow 1.3 token bucket meter band.

### Stability Proof & Backlog Bound Verification
By the Lyapunov drift bound theorem, for all arrival rates within the network capacity region with slack $\epsilon > 0$:
$$\Delta_V(Q(t)) \le B + V \cdot C_{\max} - \epsilon \sum_{i=1}^2 Q_i(t)$$
Summing over $T$ slots and taking the limsup yields the formal backlog ceiling:
$$\limsup_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \sum_{i=1}^2 \mathbb{E}[Q_i(t)] \le \frac{B + V \cdot C_{\max}}{\epsilon}$$
- **Empirical Validation**: In our testbed evaluation of 3,000 intervals, the queue backlog achieved **100.0% compliance** with the upper bound ($Q_{\max} = 39.4 < 46.12$), with zero buffer overflows.

---

## 🧠 Slow-Timescale Multi-Agent Governor (30–120 s)

Operating completely out-of-band from packet forwarding, the slow-loop governor (`graph.py`, `prompts.py`) convenes every 30 to 120 seconds.

### Six-Agent Specialist Hierarchy
1. **Flow Sizing Specialist**: Analyzes ingress traffic distribution, identifying mice vs. elephant flow thresholds.
2. **Path Routing Specialist**: Evaluates inter-switch link utilization, bisectional bandwidth, and propagation delay trade-offs.
3. **Anomaly & Congestion Specialist**: Detects flash crowds, buffer bloat trends, and oscillating queue variances.
4. **Security Slicing Specialist**: Audits flow-level isolation and ingress rate adherence.
5. **Service Assurance Specialist**: Tracks SLA latency deadlines ($P_{95} \le 30\,\text{ms}$) and packet loss compliance.
6. **Orchestrator**: Conditions consensus on ballots from the 5 specialists and selects a bounded parameter delta:
   $$\Delta \pi = (\Delta w_{\text{delay}}, \Delta w_{\text{loss}}, \Delta w_{\text{energy}}, \Delta V)$$

### Episodic Reflection & Stratified Caliper Retrieval
The agent stores past interventions in an episodic memory bank (`adaptive_memory.py`). When analyzing current telemetry $S(t)$:
- Computes Euclidean distance in the normalized 8D feature space:
  $$\|S(t) - S_k\|_2 \le \delta_{\text{caliper}} = 0.15$$
- Retrieves top-2 nearest historical neighbors to condition the prompt with past successes and vetoed actions.

### Subprocess-Isolated LLM Inference & Watchdog Cutoffs
To prevent LLM API hangs, CUDA memory errors, or network socket timeouts from crashing the control plane:
- Inference runs in an **isolated OS subprocess** (`bounded_control.py`).
- Protected by a **3.8-second hard watchdog timer**.
- If the subprocess exceeds 3.8s or crashes, the system fails-closed to the active baseline policy with zero control plane interruption.

---

## 🌉 Atomic Inter-Loop Bridge (`delta_pi_bridge.py`)

Concurrency between the fast loop (100 ms) and slow loop (30–120 s) is mediated by `DeltaPiBridge`:
- **Thread-Safe Architecture**: Uses a mutual-exclusion lock (`threading.Lock`) guarding an internal immutable reference pointer.
- **Zero-Wait Wire Rate**: The fast loop reads the active policy parameters via atomic pointer dereference with **zero lock contention** ($< 20\,\text{ns}$).
- **Non-Blocking Hot-Swap**: When the slow-loop governor completes an epoch, it atomically swaps the parameter pointer without pausing the 100 ms tick loop.

---

## 🛡️ Action Gateway, Safety Invariants & Hardware Readback

The `ActionGateway` (`action_gateway.py`) translates abstract decisions into OpenFlow 1.3 protocol messages while enforcing three non-negotiable safety invariants.

### The Three Hard Mathematical Safety Invariants
1. **Invariant 1 (Link Utilization Ceiling)**:
   $$\hat{\rho}_{\text{alternate}} = \frac{U_{\text{current}} + R_{\text{elephant}}}{C_{\text{alternate}}} \le 0.90$$
   *Action is vetoed if rerouting would overload the alternate path beyond 90%.*
2. **Invariant 2 (Ingress Rate-Limit Floor)**:
   $$R_{\text{meter}} \ge R_{\text{floor}} = 512\,\text{kbps}$$
   *Prevents starvation of legitimate flows.*
3. **Invariant 3 (Maximum Bulk Throttling Ceiling)**:
   $$R_{\text{meter}} \ge R_{\text{current}} \cdot (1 - \Delta_{\max}) = R_{\text{current}} \cdot 0.80$$
   *Rate limits cannot reduce bandwidth by more than 20% in a single intervention.*

### OpenFlow 1.3 Rule Compilation & Lease Rollback
- Interventions install OpenFlow flow mods with an explicit `hard_timeout = 5\,\text{s}`.
- If the control plane fails or drops offline, all interventions automatically expire, safely reverting switches to default shortest-path forwarding.

### Hardware Readback Audit
After issuing a `FlowMod` or `MeterMod` via the Ryu REST client (`ryu_client.py`), `rule_recovery.py` queries `GET /stats/flow/{dpid}`:
- Verifies rule installation in TCAM Table 0 (Priority 100).
- Confirms packet counter increments.
- Rolls back immediately if hardware readback fails.

---

## 🔄 Parametric Self-Improvement & LoRA Adaptation (`self_improvement/`)

SELF-X implements true **parametric weight adaptation** rather than ephemeral prompt prompting:

```
[ Replay Buffer ] ---> [ Feature Normalizer ] ---> [ LoRA Fine-Tuner ]
                                                          |
                                                          v
                                               [ Stress Benchmark Gate ]
                                                 /                 \
                                           Passed                 Failed
                                            /                         \
                          [ Atomic Hot-Swap ]                 [ Quarantined ]
```

### Replay Dataset Synthesis & Feature Normalization
- Extracts state-action pairs from historical episodes achieving positive composite reward ($R(t) \ge 0.70$).
- Normalizes features into standard scale ($z = \frac{x - \mu}{\sigma}$) and tokenizes into prompt-completion pairs.

### SmolLM2-135M Low-Rank Adaptation (LoRA)
- Base Backbone: `HuggingFaceTB/SmolLM2-135M-Instruct` (134.5M parameters).
- Target Modules: Query and value attention projection matrices (`q_proj`, `v_proj`).
- Decomposition:
  $$W = W_0 + \frac{\alpha}{r} (B \cdot A), \quad r = 8, \; \alpha = 16$$
- Trainable Parameters: **460,800 parameters** ($0.342\%$ of backbone).
- Loss Function: Cross-entropy loss over target action tokens ($2.45 \to 0.14$).

### Fail-Closed Benchmark Stress Promotion Gate
Before any fine-tuned adapter is loaded into the datapath:
- Evaluated against a frozen test suite of 3 synthetic stress traffic profiles (`dataset.py`).
- Must satisfy:
  1. Validation loss reduction $\ge 15\%$.
  2. Zero safety invariant violations ($0$ vetoes).
  3. Latency SLA violation rate $\le 0.01\%$.
- If any check fails, the candidate adapter is rejected and quarantined.

### Atomic Hot-Swapping & Instant Rollback
- Approved adapters are loaded into the policy backend via atomic weight pointer swap.
- If operational telemetry indicates degradation over 3 consecutive governance epochs, `adapter_lifecycle.py` invokes instant rollback to the previous checkpoint.

---

## 📁 Subsystem File Manifest & Component Responsibilities

| Source File | Module Responsibility |
| :--- | :--- |
| `two_timescale_scheduler.py` | Non-blocking scheduler driving 100 ms fast ticks and 30–120 s slow governance cycles. |
| `delta_pi_bridge.py` | Thread-safe inter-loop bridge managing atomic policy parameter pointer swaps. |
| `dpp_controller.py` | Fast-loop quadratic Lyapunov Drift-Plus-Penalty queue optimization algorithm. |
| `dpp_stability.py` | Lyapunov backlog bound calculations and compliance verification routines. |
| `action_gateway.py` | OpenFlow 1.3 rule compiler, safety invariant validator, and hardware execution gateway. |
| `rule_recovery.py` | Hardware TCAM readback auditor and lease-based safety rollback coordinator. |
| `bounded_control.py` | Subprocess-isolated LLM execution environment with 3.8s hard watchdog timeout. |
| `adaptive_memory.py` | Stratified caliper-based episodic reflection retrieval engine. |
| `policy_backend.py` | Low-rank policy inference engine managing SmolLM2-135M forward passes. |
| `adapter_gate.py` | Frozen benchmark stress validation gate for candidate LoRA checkpoints. |
| `self_improvement/training.py` | PyTorch training loop for parameter-efficient LoRA fine-tuning. |
| `self_improvement/registry.py` | Checkpoint versioning, SHA-256 fingerprinting, and deployment rollback manager. |

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
