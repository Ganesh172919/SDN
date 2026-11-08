# SELF-X SDN: Comprehensive Viva Defense & Technical Interrogation Guide

**Course:** EC466 Software Defined Networks (IIIT Dharwad)  
**Project:** SELF-X: Autonomous Flow-Management Agent  
**Team:** SDN_07 | **Student Presenter:** Harsh Raj (23BDS076)  
**Target:** 25 Rigorous Technical Interrogation Questions across 5 Engineering Domains  

---

## Domain 1: OpenFlow 1.3 Protocol & Datapath Mechanics

### Q1.1: Exactly how does OpenFlow 1.3 implement rate limiting, and why did you choose Meters over Queues?
**Harsh Raj Response:**
> "In OpenFlow 1.3, rate limiting can be implemented via **Meter Tables** (`OFPMeterMod`) or **Queue Properties** (`OFPPacketQueue`). 
> 
> We selected Meter Tables because Open vSwitch (OVS 2.13+) implements meters with per-flow granularity in the datapath flow table without requiring external Linux Traffic Control (`tc`) kernel reconfiguration. 
> 
> When our `ActionGateway` compiles a rate-limiting rule, it:
> 1. Injects an `OFPMeterMod` entry on switch `s2` specifying the meter ID, flags `OFPMC_KBPS` and `OFPMC_BURST`, and a drop band (`OFPMBT_DROP`) with rate in kbps and burst size in kilobits.
> 2. Injects an `OFPFlowMod` entry matching the elephant flow IP tuple (`ipv4_dst=10.0.0.2`), with an instruction `OFPIT_METER` binding the packet match to that meter ID.
> 
> Packets exceeding the meter bucket are dropped directly at the switch ingress pipeline before entering the shared buffer queue, preventing buffer bloat."

---

### Q1.2: What is the exact difference between `idle_timeout` and `hard_timeout` in your installed rules?
**Harsh Raj Response:**
> "In OpenFlow 1.3:
> - `idle_timeout`: The rule is purged from the switch TCAM if no matching packets arrive for the specified duration (we set this to $60\text{ s}$).
> - `hard_timeout`: The rule is unconditionally purged from the switch after the specified duration, regardless of whether packets are actively matching (we set this to $120\text{ s}$).
> 
> This provides an essential **fail-closed lease mechanism**: if the slow governor crashes or loses connectivity with the controller, any dynamic elephant reroutes or meters automatically expire within 120 seconds, and OVS reverts to the default static spanning tree, preventing permanent network misconfigurations."

---

### Q1.3: How does your system prevent rule installation race conditions when both the Fast Loop and Slow Loop execute?
**Harsh Raj Response:**
> "We enforce a strict separation of concerns through our **Delta Bridge** (`selfx/agent/delta_pi_bridge.py`):
> 1. The **Slow Governor never talks directly to OpenFlow switches**. It only emits an updated policy parameter tuple $\Delta\pi = (V, \mathbf{w}, \mathcal{M})$, representing the objective weights, trade-off constant, and allowed action mask.
> 2. The **Fast DPP Controller is the sole actuator** that translates $\Delta\pi$ into physical OpenFlow rules via the `ActionGateway`.
> 3. The Delta Bridge swaps the active policy reference using a Python `threading.Lock` pointer assignment in $< 10\ \mu\text{s}$. The fast loop reads the currently referenced policy atomically at the start of each 100 ms slot, guaranteeing zero lock contention and complete freedom from race conditions."

---

### Q1.4: How does `selfx/agent/rule_recovery.py` perform datapath readback verification?
**Harsh Raj Response:**
> "After the `ActionGateway` emits a `POST /stats/flowentry/add` request via Ryu's `ofctl_rest`, network latency or switch TCAM exhaustion could cause the rule installation to fail silently.
> 
> To prevent ghost actions:
> 1. `rule_recovery.py` assigns a unique 64-bit cryptographic `cookie` to every transaction.
> 2. It queries `GET /stats/flow/{dpid}` within 500 ms.
> 3. It parses the returned JSON array and verifies that a flow entry exists with the exact matching `cookie`, `table_id=0`, and matching IP tuples.
> 4. If the cookie is not present or if the switch returns an OpenFlow error code (e.g., `OFPFMFC_TABLE_FULL`), the system marks the transaction as failed and triggers an immediate rollback to baseline forwarding."

---

### Q1.5: How do you mathematically guarantee that an LLM or policy recommendation will never cause a forwarding loop?
**Harsh Raj Response:**
> "We implement a strict topological loop invariant in `selfx/agent/action_gateway.py`. 
> 
> Before compiling any path $P = (u_1, u_2, \dots, u_m)$:
> 1. **Simple Path Invariant:** We verify $|P| == |\text{set}(P)|$. If any node appears twice, a loop exists, and the proposal is instantly rejected with a `LoopDetectedError`.
> 2. **Adjacency Matrix Invariant:** For every adjacent switch pair $(u_j, u_{j+1})$, we verify that $(u_j, u_{j+1}) \in E$ in the pre-verified network topology graph.
> 3. **Egress Port Verification:** The gateway cross-references the physical port binding for that edge from the verified topology manifest. 
> 
> Under no circumstances is raw LLM text ever parsed directly into an OpenFlow output port without this geometric graph verification."

---

## Domain 2: Stochastic Network Optimization & Lyapunov DPP

### Q2.1: Why did you choose a Quadratic Lyapunov function $L(Q) = \frac{1}{2}\sum Q_i^2$ instead of a Linear Lyapunov function $L(Q) = \sum Q_i$?
**Harsh Raj Response:**
> "A linear Lyapunov function $L(Q) = \sum Q_i$ has a constant gradient: $\nabla L = [1, 1, \dots, 1]^T$. This means a linear drift optimizer treats a queue with 100 packets identically to a queue with 1 packet.
> 
> In contrast, the quadratic Lyapunov function $L(Q) = \frac{1}{2}\sum Q_i^2$ has a gradient $\nabla L = [Q_1, Q_2, \dots, Q_K]^T$ that scales linearly with current queue depth. 
> 
> When we compute the drift $\Delta(L) \le B - \sum Q_i(\mu_i - A_i)$, the term $-Q_i \cdot \mu_i$ places maximal mathematical pressure on allocating service $\mu_i$ to the most congested buffer. This guarantees that small buffers are ignored while overflowing buffers receive immediate high-priority service, preventing tail-drop."

---

### Q2.2: What is the physical meaning of the constant $B = \frac{1}{2}\sum (A_{\max}^2 + \mu_{\max}^2)$?
**Harsh Raj Response:**
> "The constant $B$ represents the maximum possible variance (or discrete jump energy) that can occur in the Lyapunov function over a single time slot due to bursty arrivals and service clearing. 
> 
> Even if the controller allocates zero service ($\mu = 0$) and maximum traffic arrives ($A = A_{\max}$), the Lyapunov function can increase by at most $B$ plus cross terms. 
> 
> In our analytical bound $(B + V \cdot C)/\varepsilon$, $B$ represents the baseline backlog penalty incurred due to stochastic traffic variance. A smaller time slot $\tau$ reduces $A_{\max}$ and $\mu_{\max}$, shrinking $B$ and tightening the queue upper bound."

---

### Q2.3: Explain the fundamental $O(V), O(1/V)$ trade-off in Neely's Lyapunov Optimization.
**Harsh Raj Response:**
> "In Neely’s Theorem:
> 1. The time-average queue backlog satisfies: $\limsup_{T \to \infty} \frac{1}{T}\sum Q(t) \le \frac{B + V \cdot C_{\max}}{\varepsilon} = O(V)$.
> 2. The time-average operational cost satisfies: $\limsup_{T \to \infty} \frac{1}{T}\sum C(t) \le C^* + \frac{B}{V} = O(1/V)$, where $C^*$ is the theoretical optimal cost.
> 
> - If we set **$V \to 0$**: The controller prioritizes queue backlog minimization above all else, keeping latency near zero but potentially incurring higher flow reconfiguration or energy costs.
> - If we set **$V \to \infty$**: The controller minimizes operational cost, but queue backlogs grow linearly with $V$.
> 
> In our empirical sweep (Task T13, `dpp_v_tradeoff.json`), sweeping $V \in [1, 32]$ confirmed this exact relationship: mean backlog scaled monotonically from $0.013\text{ Mbit}$ ($V=1$) to $0.0434\text{ Mbit}$ ($V=32$)."

---

### Q2.4: What is the 'interior capacity slack $\varepsilon$', and what happens if $\varepsilon \le 0$?
**Harsh Raj Response:**
> "The interior capacity slack $\varepsilon > 0$ measures the distance between the offered traffic arrival vector $\mathbf{A}$ and the boundary of the physical network capacity region $\Lambda$. 
> 
> Specifically, it means the physical network has sufficient spare bandwidth such that $\mu_i - A_i \ge \varepsilon$ under some stabilizing policy.
> 
> If $\varepsilon \le 0$, the offered traffic exceeds the total physical capacity of the network (over-subscription). In that regime, no control policy can prevent queue backlogs from growing to infinity. 
> 
> When $\varepsilon \le 0$, our `ActionGateway` and DPP controller invoke flow admission control (`drop` or ingress `rate_limit`) to shed non-critical elephant traffic, artificially restoring $\varepsilon > 0$ for high-priority mice flows."

---

### Q2.5: Why does your empirical bound compliance reach 100.0% instead of just meeting the $\ge 95\%$ target?
**Harsh Raj Response:**
> "Because the analytical bound $(B + V \cdot C)/\varepsilon = 18.05\text{ Mbit}$ is a **worst-case mathematical upper bound** derived under adversarial worst-case traffic arrivals where $A(t) = A_{\max}$ in every consecutive slot.
> 
> In realistic testbed conditions (even during elephant bursts and volatile traffic), traffic arrivals exhibit micro-pauses between packet bursts, and the fast DPP controller resolves congestion within $< 1$ ms by immediately redirecting traffic to the secondary trunk. 
> 
> Consequently, the maximum observed queue backlog in our testbed was $0.0434\text{ Mbit}$—far below the $18.05\text{ Mbit}$ ceiling—yielding 0 violations across 3,000 intervals ($100.0\%$ compliance)."

---

## Domain 3: Multi-Agent AI Governance & Safety Gating

### Q3.1: Why do you have five domain specialists instead of asking a single prompt to do everything?
**Harsh Raj Response:**
> "A single unspecialized prompt suffers from **context pollution** and conflicting objective dilution. 
> 
> When an LLM is asked to simultaneously optimize routing, detect anomalies, check security subnets, monitor QoS SLAs, and calculate meter burst rates:
> 1. It frequently prioritizes one metric (e.g., routing) while hallucinating or dropping constraints on another (e.g., tenant subnet isolation).
> 2. It produces lengthy, unstructured prose that cannot be reliably parsed into datapath primitives.
> 
> By modularizing into **5 Domain Specialists**:
> - Each specialist receives a focused sub-schema (e.g., the Security Specialist only inspects IP subnets and tenant tags; the Flow Sizing Specialist only inspects byte/duration histograms).
> - Each specialist emits a strictly typed JSON opinion bounded by numerical min/max limits.
> - The Orchestrator acts as a deterministic aggregation filter, resolving conflicts using explicit priority rules."

---

### Q3.2: Exactly how does the Orchestrator resolve conflicts when specialists disagree?
**Harsh Raj Response:**
> "We implement a hierarchical priority arbitration scheme in `slow-loop/agentic/six_agent_governor.py`:
> 1. **Security & Anomaly Overrides (Highest Priority):** If the Security Specialist flags an unauthorized subnet crossing or the Anomaly Specialist detects a DDoS flood, the candidate action mask $\mathcal{M}$ is restricted to drop or isolate. Routing recommendations from other specialists are rejected.
> 2. **Slicing Assurance Priority:** If mice flow latency exceeds 10 ms, the Slicing Specialist forces a reduction in elephant meter rates regardless of flow-sizing preferences.
> 3. **Convex Weight Aggregation:** For continuous parameters ($V$ and objective weights $\mathbf{w}$), the Orchestrator computes a normalized convex combination of specialist recommendations, projecting the resulting vector onto the unit simplex ($\sum w_k = 1, w_k \ge 0$) and clamping $|\Delta V| \le 8$."

---

### Q3.3: What happens if an LLM specialist times out or returns malformed JSON?
**Harsh Raj Response:**
> "The system adheres strictly to the **Fail-Closed Principle**:
> 1. Specialist execution is wrapped in a strict 2.0-second timeout.
> 2. Responses are validated against our Pydantic/dataclass schema. If JSON parsing fails or a value is out of bounds (e.g., $w_{\text{lat}} = -0.5$ or $\text{NaN}$), the opinion is flagged as `INVALID`.
> 3. The Orchestrator discards the invalid opinion and falls back to the deterministic default opinion for that role.
> 4. If the Orchestrator itself fails to form a consensus, the candidate policy update $\Delta\pi$ is aborted, and the fast DPP loop continues running the previously verified incumbent policy."

---

### Q3.4: How does the Stress Gate evaluate candidate policies without causing real network disruptions?
**Harsh Raj Response:**
> "The Stress Gate (`slow-loop/agentic/stress_gate.py`) evaluates candidate policies in an **isolated simulation sandbox** prior to promotion.
> 
> It subjects the candidate policy $\Delta\pi$ to frozen benchmark scenarios (e.g., a sudden 15 Mbps elephant burst on the primary trunk). It compares candidate performance against the incumbent policy across three criteria:
> 1. Does the candidate cause a p95 latency regression?
> 2. Does the candidate increase packet loss percentage?
> 3. Does the candidate violate the Lyapunov backlog bound?
> 
> If any criterion fails, the Stress Gate emits a `REJECT` decision and logs the regression. Only candidate policies achieving equal or superior Pareto performance are passed to the Delta Bridge."

---

## Domain 4: Parametric LoRA Weight Adaptation & ML

### Q4.1: Why did you choose rank $r = 8$ and scaling factor $\alpha = 16$ for your LoRA architecture?
**Harsh Raj Response:**
> "In Low-Rank Adaptation [9], the update to policy matrix $W_0 \in \mathbb{R}^{d \times k}$ is parameterized as $\Delta W = \frac{\alpha}{r} B A$, where $B \in \mathbb{R}^{d \times r}$ and $A \in \mathbb{R}^{r \times k}$.
> 
> - Our feature dimension is $d = 8$ (queue depth, arrival rate, service rate, latency trend, loss, util primary, util secondary, active flows) and action preference dimension is $k = 4$.
> - Setting $r = 8$ preserves full intrinsic rank across this low-dimensional feature space while restricting parameter count to $(8 \times 8) + (8 \times 4) = 96$ trainable weights.
> - Setting $\alpha = 16$ establishes a scaling multiplier $\frac{\alpha}{r} = \frac{16}{8} = 2.0$, ensuring that weight updates during offline fine-tuning exert sufficient influence over policy logits without destabilizing base initialization."

---

### Q4.2: How do you prevent catastrophic forgetting during LoRA weight updates?
**Harsh Raj Response:**
> "We employ three specific mechanisms:
> 1. **Base Weight Freezing:** The original base weights $W_0$ are completely frozen and cannot be modified by gradient updates.
> 2. **Replay Dataset Regularization:** Training experiences in `selfx/agent/replay_pipeline.py` are drawn from a 70/15/15 split containing both steady-state baseline traffic and burst congestion events, preventing the model from overfitting solely to recent bursts.
> 3. **Adapter Validation Gate (`adapter_gate.py`):** Before newly fine-tuned weights $[A, B]$ are deployed, they are evaluated against held-out validation trajectories. If reward falls below the incumbent adapter, the new adapter is rejected."

---

### Q4.3: What is the exact mathematical loss function used in `run_lora_finetune.py`?
**Harsh Raj Response:**
> "We train the policy network using a policy-gradient MSE loss regularized by reward advantage:
> $$\mathcal{L}(\theta) = \frac{1}{N} \sum_{j=1}^{N} \left\| \pi_\theta(s_j) - \left( a_j^* \cdot \max(R_j, 0) \right) \right\|_2^2 + \lambda \|W - W_0\|_F^2$$
> where $s_j$ is the 8-dimensional telemetry feature vector, $a_j^*$ is the one-hot target action, $R_j$ is the observed multi-objective scalar reward, and $\lambda = 0.01$ is the Frobenius norm regularization penalty that prevents LoRA weights $B A$ from diverging excessively from baseline $W_0$."

---

## Domain 5: Experimental Evaluation, Topologies & Statistics

### Q5.1: Walk me through the numbers in Table 2 (Stage A0 vs Stage A5). What specifically drove the latency drop?
**Harsh Raj Response:**
> "In Table 2:
> - **Stage A0 (Static Baseline):** Mean latency was $8.89\text{ ms}$, P95 latency was $25.00\text{ ms}$, and packet loss was $12.48\%$. The static controller forced all traffic across the primary trunk, causing queue saturation and tail-drop.
> - **Stage A5 (Full SELF-X):** Mean latency dropped to $3.40\text{ ms}$ (**59.59% reduction**), P95 latency dropped to $9.50\text{ ms}$, and packet loss dropped to $0.81\%$.
> 
> **What drove this improvement:**
> 1. Moving from A0 to A2 (Reflection) reduced latency from $8.89\text{ ms} \to 4.88\text{ ms}$ by learning to reroute elephant flows.
> 2. Moving from A2 to A4 (LoRA) reduced latency to $3.75\text{ ms}$ by eliminating context window latency and internalizing numerical thresholds.
> 3. Moving from A4 to A5 (Fast DPP) delivered the final drop to $3.40\text{ ms}$ by adjusting meter rates every 100 ms at line rate, preventing queues from ever building up."

---

### Q5.2: How did you prove that your results are statistically significant and not just random seed variation?
**Harsh Raj Response:**
> "We executed a formal **Paired Student's t-Test** (`selfx/eval/run_statistical_tests.py`) across $N = 10$ matched random seeds comparing Condition A1 (zero-shot LLM) against Condition A5 (Full SELF-X):
> - Mean Difference in cumulative reward: $\bar{D} = 137.76$
> - Standard Error: $SE = 9.56$
> - **Calculated $t\text{-statistic} = 14.4101$**
> - **Two-tailed $p\text{-value} = 0.000000 < 0.05$**
> - **Cohen's $d$ effect size = 4.557**
> 
> Because $p \ll 0.05$ and Cohen's $d > 0.8$, we decisively reject the null hypothesis $H_0$, proving that the performance gains of SELF-X are statistically robust and reproducible across random seeds."

---

### Q5.3: Explain how your zero-shot transfer test worked on the unseen mesh topology.
**Harsh Raj Response:**
> "To test out-of-distribution generalization without retraining (Task T32):
> 1. We trained the policy strictly on the linear dual-bottleneck topology (`linear`).
> 2. We froze all LoRA weights and policy parameters.
> 3. We deployed this frozen policy onto an **Unseen 10-Node Mesh Topology** (`unseen_mesh`, 10 switches, 15 meshed links) under volatile traffic.
> 4. We calculated effective gain retention using the audit's normalized formula:
> $$\text{Retention} = 100 \times \frac{\text{Gain}_{\text{mesh}} / |R_{\text{static, mesh}}|}{\text{Gain}_{\text{train}} / |R_{\text{static, train}}|}$$
> 5. The policy achieved **103.77% effective retention**, exceeding the project requirement of $\ge 90\%$. This proves the Lyapunov DPP formulation optimizes fundamental graph-theoretic flow balance rather than memorizing static switch IDs."

---

### Q5.4: Why did you test on Ryu 4.34 if ONOS was also mentioned in the problem statement?
**Harsh Raj Response:**
> "As detailed in [`selfx/docs/ONOS_METHODOLOGY_CROSS_CHECK.md`](file:///Users/harshraj/Projects/SDN/selfx/docs/ONOS_METHODOLOGY_CROSS_CHECK.md):
> 1. **Wire-Level Equivalence:** Both Ryu and ONOS communicate with Open vSwitch using standard OpenFlow 1.3 protocol wire frames over TCP port 6653. Open vSwitch executes identical hardware TCAM matching regardless of controller identity.
> 2. **Controller Neutrality:** All control mutations in SELF-X flow through our `ActionGateway` abstraction, which maps high-level reroute/meter actions to controller REST endpoints.
> 3. **Engineering Practicality:** Ryu runs natively in Python 3.9+ with $<65\text{ MB}$ RAM overhead and boots in 450 ms, enabling automated execution of our 12-test acceptance suite in $< 2\text{ seconds}$. ONOS requires a full Java OSGi Karaf container consuming $3.5\text{ GB}$ RAM and requiring 30 seconds per restart, which would make rapid automated unit testing impractical on standard evaluation workstations."

---

### Q5.5: What are the 12 tests in your Master Acceptance Suite, and how do we verify them right now?
**Harsh Raj Response:**
> "You can verify the entire project right now by running:
> ```bash
> python3 selfx/scripts/run_acceptance_suite.py
> ```
> 
> The suite automatically verifies:
> 1. Stack Environment & Shell Script Availability
> 2. Topologies Manifests (Linear, Leaf-Spine, Unseen Mesh)
> 3. Deterministic Traffic Schedules (Steady, Bursty, Volatile)
> 4. Metric Contracts & Unit Tests (15/15 passing in `selfx/eval/tests`)
> 5. Action Gateway Loop Prevention & Rule Compilation
> 6. Formal Lyapunov DPP Empirical Bound Compliance (100.0% $\ge 95\%$)
> 7. DPP V-Tradeoff Empirical Verification ($O(V)$ backlog, $O(1/V)$ cost)
> 8. Multi-Agent Governance & Stress Gate Failure Modes (6/6 passing)
> 9. LoRA Weight Self-Improvement & Adapter Lifecycle (+706.5% gain)
> 10. Table 2 Architectural Ablation Matrix (All 6 stages A0..A5 verified across 5 seeds)
> 11. Table 5 Industry Baseline Comparison Matrix (All 6 controllers verified across 5 seeds)
> 12. Statistical Rigor (Paired t-test $p < 0.05$, latency targets $\ge 20\%$ & $\ge 10\%$, zero-shot mesh retention $\ge 90\%$)
> 
> All 12 tests pass with zero warnings, outputting a signed JSON report to `selfx/output/acceptance_report.json`."
