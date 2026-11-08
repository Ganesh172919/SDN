# SELF-X Formal Lyapunov Drift-Plus-Penalty (DPP) Derivation & Bound Definition

**Document Identity:** Technical Derivation Document  
**Traceability:** Tasks T08, T10, T11 | Deliverable D2 | EC466 Team SDN_07  
**Date:** 05 November 2026 (IST)  
**Governing Specification:** `SELF-X_Problem_Statement_v2_Revised.docx` (Section 6)

---

## 1. System Model and Physical Units

Consider an SDN OpenFlow datapath where packet traffic is enqueued across $M$ bottleneck switch queues $i \in \{1, \dots, M\}$.
Control operates in discrete time slots $t \in \{0, 1, 2, \dots\}$ of fixed duration $\tau = 0.1\text{ s}$ ($100\text{ ms}$).

### 1.1 State Variables and Units
- **$Q_i(t)$**: Queue backlog of link/port $i$ at the beginning of slot $t$. Unit: **Megabits (Mbit)**.
- **$\lambda_i(t)$**: Total packet arrival rate offered to queue $i$ during slot $t$. Unit: **Mbps**.  
  Arrival volume during slot $t$ is $A_i(t) = \lambda_i(t) \cdot \tau\text{ Mbit}$.
- **$\mu_i(t)$**: Service (forwarding departure) rate allocated to queue $i$ during slot $t$, dictated by fast control action $a(t) \in \mathcal{A}$. Unit: **Mbps**.  
  Maximum service volume in slot $t$ is $S_i(t) = \mu_i(t) \cdot \tau\text{ Mbit}$.
- **$\mu_{i,\max}$**: Physical link transmission capacity. In the reference topology:
  - Primary bottleneck ($s2 \leftrightarrow s3$, Port 3): $C_1 = 10.0\text{ Mbps}$ ($1.0\text{ Mbit/slot}$).
  - Secondary detour ($s2 \leftrightarrow s3$, Port 4): $C_2 = 10.0\text{ Mbps}$ ($1.0\text{ Mbit/slot}$).

### 1.2 Queue Evolution
The discrete queue dynamics follow Lindley recursion:
$$Q_i(t+1) = \max\left[ Q_i(t) - S_i(t),\, 0 \right] + A_i(t)$$

Under finite switch buffer memory with capacity $Q_{\max} = 10.0\text{ Mbit}$ ($40$ packets of $1500\text{ bytes} \approx 0.48\text{ Mbit}$ physical or $10.0\text{ Mbit}$ fluid ceiling), any arrival exceeding buffer room is dropped as tail drop / explicit drop.

---

## 2. Mathematical Derivation of the Drift Bound

### 2.1 Lyapunov Function
Define the quadratic Lyapunov function:
$$L(Q(t)) \triangleq \frac{1}{2} \sum_{i=1}^M Q_i(t)^2$$
$L(Q(t))$ is a scalar measure of total queue congestion. If $L(Q(t))$ remains bounded, all queues remain bounded, guaranteeing network stability.

### 2.2 Conditional Lyapunov Drift
The one-slot conditional Lyapunov drift is:
$$\Delta(Q(t)) \triangleq \mathbb{E}\left[ L(Q(t+1)) - L(Q(t)) \;\middle|\; Q(t) \right]$$

From the queue dynamics:
$$Q_i(t+1)^2 = \left( \max[Q_i(t) - S_i(t), 0] + A_i(t) \right)^2$$
Using the algebraic inequality $(\max[x, 0] + y)^2 \le x^2 + y^2 + 2y\max[x, 0] \le x^2 + y^2 + 2yx$ for $x, y \ge 0$:
$$Q_i(t+1)^2 \le (Q_i(t) - S_i(t))^2 + A_i(t)^2 + 2 A_i(t) Q_i(t)$$
$$Q_i(t+1)^2 \le Q_i(t)^2 + S_i(t)^2 + A_i(t)^2 - 2 Q_i(t) (S_i(t) - A_i(t))$$

Summing over all queues $i \in \{1, \dots, M\}$ and multiplying by $1/2$:
$$L(Q(t+1)) - L(Q(t)) \le \frac{1}{2} \sum_{i=1}^M \left( S_i(t)^2 + A_i(t)^2 \right) - \sum_{i=1}^M Q_i(t) (S_i(t) - A_i(t))$$

### 2.3 Derivation of Constant $B$
Define the finite positive constant $B$:
$$B \triangleq \frac{1}{2} \sum_{i=1}^M \left( S_{i,\max}^2 + A_{i,\max}^2 \right)$$
For our 2-bottleneck system with slot duration $\tau = 0.1\text{ s}$:
- $S_{1,\max} = 10.0\text{ Mbps} \times 0.1\text{ s} = 1.0\text{ Mbit}$.
- $S_{2,\max} = 10.0\text{ Mbps} \times 0.1\text{ s} = 1.0\text{ Mbit}$.
- Maximum burst arrival $A_{\max} = 15.0\text{ Mbps} \times 0.1\text{ s} = 1.5\text{ Mbit}$.

$$B = \frac{1}{2} \left[ (1.0)^2 + (1.5)^2 + (1.0)^2 + (1.5)^2 \right] = \frac{1}{2} [1.0 + 2.25 + 1.0 + 2.25] = \frac{6.5}{2} = 3.25\text{ Mbit}^2$$

Taking conditional expectations:
$$\Delta(Q(t)) \le B - \sum_{i=1}^M Q_i(t) \mathbb{E}\left[ S_i(t) - A_i(t) \;\middle|\; Q(t) \right]$$

---

## 3. Drift-Plus-Penalty Optimization

Let $\text{cost}(t) \in [0, C]$ be the multi-objective cost:
$$\text{cost}(t) = w_{\text{lat}} \cdot \frac{\text{latency}(t)}{40\text{ ms}} + w_{\text{loss}} \cdot \frac{\text{loss}(t)}{20\%} + w_{\text{en}} \cdot \text{energy}(t) + w_{\text{res}} \cdot \text{resource}(t) - w_{\text{tp}} \cdot \frac{\text{throughput}(t)}{10\text{ Mbps}}$$
where $C = \max_{a} \text{cost}(a) \le 2.0$.

Adding the penalty term $V \cdot \mathbb{E}[\text{cost}(t) \mid Q(t)]$ where $V \ge 0$ is governed by the slow LLM layer:
$$\Delta(Q(t)) + V \cdot \mathbb{E}[\text{cost}(t) \mid Q(t)] \le B + V \cdot \mathbb{E}[\text{cost}(t) \mid Q(t)] - \sum_{i=1}^M Q_i(t) \mathbb{E}\left[ S_i(t) - A_i(t) \;\middle|\; Q(t) \right]$$

### 3.1 Per-Slot Greedy Decision Law
To minimize the upper bound on drift-plus-penalty at every slot $t$, the fast controller greedily selects action $a(t) \in \mathcal{A}$:
$$\min_{a \in \mathcal{A}} \left[ \sum_{i=1}^M Q_i(t) \left( A_i(t, a) - S_i(t, a) \right) + V \cdot \text{cost}(a) \right]$$
This requires evaluating at most $|\mathcal{A}| = 5$ candidate actions (`admit`, `reroute`, `rate_limit`, `drop`, `no_op`), solvable in $O(1)$ sub-millisecond polynomial time.

---

## 4. Reconciling Bound Shorthand: $\frac{B + V \cdot C}{\varepsilon}$ vs $B + V \cdot C$

### 4.1 Interior Capacity Slack $\varepsilon$
By Slater's interior condition, if the offered traffic lies strictly within the network capacity region with slack $\varepsilon > 0$:
$$\mathbb{E}[S_i(t) - A_i(t) \mid Q(t)] \ge \varepsilon \quad \forall i$$
Then:
$$\Delta(Q(t)) + V \cdot \mathbb{E}[\text{cost}(t) \mid Q(t)] \le B + V \cdot C - \varepsilon \sum_{i=1}^M Q_i(t)$$

Summing over $t = 0, \dots, T-1$ and telescoping:
$$\mathbb{E}[L(Q(T))] - \mathbb{E}[L(Q(0))] + V \sum_{t=0}^{T-1} \mathbb{E}[\text{cost}(t)] \le T(B + V \cdot C) - \varepsilon \sum_{t=0}^{T-1} \sum_{i=1}^M \mathbb{E}[Q_i(t)]$$
Since $\mathbb{E}[L(Q(T))] \ge 0$ and $\text{cost}(t) \ge 0$:
$$\frac{1}{T} \sum_{t=0}^{T-1} \sum_{i=1}^M \mathbb{E}[Q_i(t)] \le \frac{B + V \cdot C}{\varepsilon} + \frac{\mathbb{E}[L(Q(0))]}{\varepsilon T}$$

Taking $T \to \infty$:
$$\limsup_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \sum_{i=1}^M \mathbb{E}[Q_i(t)] \le \frac{B + V \cdot C}{\varepsilon}$$
and
$$\limsup_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \mathbb{E}[\text{cost}(t)] \le \text{cost}^* + \frac{B}{V}$$

### 4.2 Reconciliation Resolution
- **Analytical General Form (Section 6.2)**: $\text{Bound} = \frac{B + V \cdot C}{\varepsilon}$.
- **Normalized Shorthand (Table 4 / D2)**: Under calibrated unit capacity scaling where slack $\varepsilon = 1.0\text{ Mbit/slot}$ (i.e. secondary path provides $1.0\text{ Mbit/slot}$ drain headroom during bottleneck), the denominator equals unity:
  $$\frac{B + V \cdot C}{1.0} = B + V \cdot C$$
- **Operational Parameter Values**:
  - $B = 3.25\text{ Mbit}^2$
  - $C = 1.85$ (maximum normalized single-slot penalty)
  - $\varepsilon = 0.85\text{ Mbit/slot}$
  - For $V = 8.0$:
    $$\text{Bound}_{\text{exact}} = \frac{3.25 + (8.0 \times 1.85)}{0.85} = \frac{3.25 + 14.8}{0.85} = \frac{18.05}{0.85} \approx 21.23\text{ Mbit}$$
    $$\text{Bound}_{\text{normalized}} = B + V \cdot C = 3.25 + 14.8 = 18.05\text{ Mbit}$$

---

## 5. Finite-Sample $\ge 95\%$ Acceptance Check

While standard Lyapunov theorems apply asymptotically as $T \to \infty$, the EC466 deliverable D2 requires a finite-sample acceptance criterion over $N \ge 1,000$ discrete control slots.

### Acceptance Definition
For a test run of $N = 1,000$ consecutive control intervals (with warm-up $W_0 = 50$ slots):
Let the cumulative running time-average queue backlog at slot $k$ be:
$$\bar{Q}(k) \triangleq \frac{1}{k - W_0 + 1} \sum_{t=W_0}^k \left( Q_1(t) + Q_2(t) \right)$$

The acceptance compliance metric is:
$$\text{Compliance Rate} = \frac{1}{N - W_0 + 1} \sum_{k=W_0}^N \mathbf{1}\left\{ \bar{Q}(k) \le B + V \cdot C \right\} \ge 0.95 \; (95.0\%)$$

A profile passes if and only if empirical compliance is at least $95.0\%$.

