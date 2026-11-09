# SELF-X SDN: Viva Examination & Live Demonstration Script

**Course:** EC466 Software Defined Networks (IIIT Dharwad)  
**Project:** SELF-X: Autonomous Flow-Management Agent  
**Team:** SDN_07 | Student Presenter: Harsh Raj (23BDS076)  
**Target Duration:** 10 Minutes Total (7 min Presentation/Demo + 3 min Technical Q&A)

---

## 1. Quick Rehearsal Checklist Before Stepping In

- [ ] Linux / Mininet Environment initialized or ready (`sudo mn -c` executed).
- [ ] Web Dashboard running: `python3 Web/server.py` on port 5000.
- [ ] Browser open at `http://localhost:5000` navigated to the **Results & Diagnostics** tab.
- [ ] Canonical testbed outputs verified in `selfx/output/`.
- [ ] Master acceptance suite executed: `python3 selfx/scripts/run_acceptance_suite.py` returns `ALL 12 TESTS PASSED`.

---

## 2. Timed Presentation & Demonstration Sequence

```
+---------------------------------------------------------------------------------------+
|  0:00 - 2:00  |  Part 1: The Problem & Two-Timescale Innovation                       |
+---------------------------------------------------------------------------------------+
|  2:00 - 5:00  |  Part 2: Live Closed-Loop Congestion Demo (CLI & Testbed)             |
+---------------------------------------------------------------------------------------+
|  5:00 - 7:00  |  Part 3: Web Dashboard, Formal Ablation (Table 2) & Baselines (Table 5)|
+---------------------------------------------------------------------------------------+
|  7:00 - 10:00 |  Part 4: Examiner Interrogation & Hard Technical Defense             |
+---------------------------------------------------------------------------------------+
```

---

### Part 1: The Problem & The Innovation (0:00 – 2:00)

**Spoken Script:**
> *"Good morning respected evaluators. Today I am presenting SELF-X, an autonomous flow-management agent for Software Defined Networks.*
>
> *Traditional SDN control planes face a critical dilemma: classic heuristics like static shortest path and reactive ECMP are rigid and cannot adapt to dynamic flash crowds, while modern reinforcement learning approaches like DQN and PPO suffer from slow cold-start convergence and unsafe exploration.*
>
> *Recently, researchers attempted to introduce Large Language Models into SDN control. However, our benchmark experiments show that purely prompt-based LLMs fail catastrophically: they have an inference latency of 800 to 2,000 milliseconds—far too slow for packet-level line rates—and they hallucinate invalid switch ports, create forwarding loops, and destabilize queue bounds.*
>
> *SELF-X resolves this fundamentally through a **Decoupled Two-Timescale Architecture**:*
> *1. A **Fast-Loop DPP Controller running at 100 milliseconds**, which uses polynomial-time Lyapunov drift-plus-penalty optimization to guarantee queue backlog stability in less than 1 millisecond.*
> *2. A **Slow-Loop Multi-Agent Governor running at 30 to 120 seconds**, where five specialized domain agents decompose network intent, evaluate policy non-regression via a Stress Gate, and perform weight-level self-improvement using Low-Rank Adaptation (LoRA)."*

---

### Part 2: Live Testbed & Congestion Injection Demo (2:00 – 5:00)

**Action 1: Trigger the Live Closed-Loop Demonstration**
In the terminal, run the integrated closed-loop demonstration:
```bash
python3 selfx/eval/run_integrated_30min.py --duration 120 --seed 42
```

**Spoken Commentary during execution:**
> *"Here we are observing the live closed-loop execution across our OpenFlow 1.3 testbed.*
>
> *1. **Sub-millisecond Fast DPP Decisions:** Notice that for every 100 ms time slot, the Lyapunov optimizer evaluates the link queue depths and service rates. When traffic surges, it solves the linearized Drift-Plus-Penalty problem: $\min [\Delta(L) + V \cdot \text{Cost}]$ in under 0.8 ms, immediately emitting safe OpenFlow meter and reroute commands.*
>
> *2. **The 6-Agent Slow Governor:** Every 30 seconds, the Slow Governor wakes up. It aggregates windowed telemetry and engages 5 specialized agents: Flow Sizing, Path Routing, Anomaly Detection, Security Slicing, and Slicing Assurance.*
>
> *3. **Stress Gating & Fail-Closed Safety:** Before any policy update $\Delta\pi$ is installed onto the datapath, it is evaluated across our frozen stress test cases. If latency regressions or backlog bound breaches are detected, the policy is immediately rejected and rolled back."*

---

### Part 3: Live Web Dashboard & Experimental Validation (5:00 – 7:00)

**Action 2: Switch to the Browser at `http://localhost:5000`**
Click on the **Results & Diagnostics** tab.

**Spoken Walkthrough:**
> *"On our live web dashboard, you can observe our formal empirical verification:*
>
> *1. **Empirical DPP Bound Compliance:** Over 3,000 continuous testbed evaluation intervals across steady, flash crowd, and volatile traffic, our queues maintained **100.0% empirical compliance** with the theoretical Lyapunov upper bound $(B + V \cdot C)/\varepsilon$, exceeding the required 95% threshold.*
>
> *2. **Table 2 Component-Wise Ablation (A0 to A5):** Moving from Static OpenFlow (A0) to our Full Two-Timescale architecture (A5), mean packet latency drops from **13.88 ms to 5.61 ms**—a **59.6% latency reduction**, with packet loss falling from **2.21% to 0.42%** and zero stability violations.*
>
> *3. **Table 5 Industry Comparison:** Compared to Deep Q-Networks (DQN) which achieved 6.82 ms, SELF-X achieves **5.61 ms (a 17.7% reduction)** while completely eliminating the unsafe exploration crashes typical of deep reinforcement learning.*
>
> *4. **Zero-Shot Mesh Generalization:** When evaluated zero-shot on an unseen 10-node mesh topology without retraining, the agent preserved **103.8% effective gain retention**, well above the 90% project requirement."*

---

## 3. Defense Against Hard Technical Examiner Questions (7:00 – 10:00)

### Q1: "Why can't an LLM directly emit OpenFlow rules at 100 ms intervals?"
**Harsh Raj Response:**
> *"Examiner, modern generative LLMs—even quantized 7B or 8B parameter models running on high-end GPUs—require between 400 and 1,800 milliseconds for a forward inference pass and autoregressive decoding. In high-speed SDN networks with 1 Gbps or 10 Gbps links, a microburst fills a switch buffer in less than 10 milliseconds.*
>
> *If an LLM were in the critical packet path, buffers would overflow hundreds of times before the model emitted its first token. Furthermore, autoregressive text generation is non-deterministic; prompt drift can cause syntax errors or invalid port assignments.*
>
> *In SELF-X, the critical 100 ms loop is strictly mathematical (Lyapunov DPP) running in C/Python in <1 ms, while the LLM/multi-agent framework operates asynchronously in the 30–120 s background loop."*

---

### Q2: "How do you formally guarantee that the agent does not cause routing loops or blackholes?"
**Harsh Raj Response:**
> *"We enforce a multi-layered fail-closed safety gate implemented in `selfx/agent/action_gateway.py` and `selfx/safety.py`:*
> *1. **Topological Loop Checking:** Every candidate path $P = (u_1, u_2, \dots, u_k)$ must satisfy the simple path invariant: $|P| = |\text{set}(P)|$, and every directed edge $(u_i, u_{i+1})$ must exist in the verified network adjacency matrix.*
> *2. **Invariant Limits:** No flow rate drop may exceed 20%, and no candidate reroute may place a link above 90% utilization.*
> *3. **Datapath Readback & Rollback:** After emitting OpenFlow rules, `rule_recovery.py` queries `/stats/flow/{dpid}`. If the switch flow table does not reflect the exact cookie within 500 ms, or if link drop rates spike, the transaction immediately fails closed, restoring the deterministic baseline forwarding tree."*

---

### Q3: "Explain the mathematics behind your Lyapunov Drift-Plus-Penalty bound."
**Harsh Raj Response:**
> *"We define the Lyapunov function as $L(Q(t)) = \frac{1}{2} \sum_{i} Q_i(t)^2$, measuring total network congestion.*
>
> *The 1-step conditional Lyapunov drift is $\Delta(L(t)) = \mathbb{E}[L(Q(t+1)) - L(Q(t)) \mid Q(t)]$. Squaring the queue evolution equation $Q(t+1) = \max[Q(t) - \mu(t), 0] + A(t)$ yields:*
> $$\Delta(L(t)) \le B - \sum_{i} Q_i(t) \cdot \mathbb{E}[\mu_i(t) - A_i(t) \mid Q(t)]$$
> *where $B = \frac{1}{2} \sum_i (A_{\max}^2 + \mu_{\max}^2)$.*
>
> *Adding the penalty term $V \cdot \text{Cost}(t)$ and applying Neely’s Theorem over time horizon $T$ proves that the time-average backlog is strictly bounded by:*
> $$\limsup_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \sum_i \mathbb{E}[Q_i(t)] \le \frac{B + V \cdot C_{\max}}{\varepsilon}$$
> *where $\varepsilon$ is the interior capacity slack. This mathematically guarantees queue stability for all finite $V$."*

---

### Q4: "Why did you implement LoRA weight fine-tuning instead of just prompt engineering or in-context memory?"
**Harsh Raj Response:**
> *"In our Table 2 ablation experiments, verbal in-context reflection (Condition A2) improved cumulative reward from -48.2 (A1) to -26.3. However, verbal memory has two severe drawbacks: context window saturation (which causes latency degradation after several hundred cycles) and catastrophic forgetting of structural invariants.*
>
> *By implementing Low-Rank Adaptation (LoRA, Condition A4) with rank $r=8$ and $\alpha=16$ on the policy projection matrices ($W = W_0 + \frac{\alpha}{r} B A$), the policy compresses recurring traffic patterns into parametric weights.*
>
> *As shown in our LoRA attribution report, parametric adaptation yielded an additional **+706% cumulative reward improvement** over verbal reflection alone while eliminating context window bloat."*

---

### Q5: "What happens if the Ryu controller dies during operation?"
**Harsh Raj Response:**
> *"All installed OpenFlow flow rules specify finite lease expiration timeouts (`idle_timeout=60s`, `hard_timeout=120s`).*
>
> *Furthermore, Open vSwitch operates with fail-standalone mode configured: if the TCP connection to port 6653 drops, OVS continues forwarding existing active flows according to its local TCAM tables until leases expire, preventing immediate traffic disruption while triggering an alert in `selfx/agent/rule_recovery.py`."*

---

## 4. Summary Table of Key Memorized Metrics for Harsh Raj

| Metric | Measured Value | Minimum Success Requirement | Status |
| :--- | :--- | :--- | :--- |
| **DPP Empirical Compliance** | **100.0%** | $\ge 95.0\%$ across 3,000 intervals | **EXCEEDS** |
| **Latency Reduction vs. Static** | **59.6%** | $\ge 20.0\%$ reduction ($p < 0.05$) | **EXCEEDS** |
| **Latency Reduction vs. DQN** | **17.7%** | $\ge 10.0\%$ reduction | **EXCEEDS** |
| **Paired t-Test Significance** | $t = 14.41, p < 10^{-5}$ | $p < 0.05$ (Statistically Significant) | **EXCEEDS** |
| **Zero-Shot Retention (Mesh)** | **103.8%** | $\ge 90.0\%$ effective gain retention | **EXCEEDS** |
| **Fast DPP Solve Time** | **< 1.0 ms** | $< 10.0$ ms per slot | **EXCEEDS** |
| **Safety Violations (A5)** | **0.0** | 0 critical forwarding loops | **EXCEEDS** |

