# Self-Improving SDN Flow-Management Agent (SELF-X)

> **Production-Grade Autonomous Software-Defined Network Flow Management with LLM Reflection, High-Dimensional Episodic Memory, Process-Isolated Inference, and Deterministic Fail-Closed Safety**  
> *Course Project — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*  
> *Empirical Scope: 86,400 Control Windows | 9 Controllers | 8 Traffic Scenarios | 4,000-Draw Paired Bootstrap Resampling*

SELF-X watches traffic in a small network and decides every five seconds whether a large
burst should be left alone, moved to a second path, or slowed down. Every decision passes
an independent safety check before it is applied. The system remembers what happened after
each decision and uses that record to choose better next time. An AI language model can
suggest an action, but ordinary code validates the suggestion and builds the final rule.

![The SELF-X network operations console](selfx/output/explainer/07_live_console.png)

*The simulator console (`.\run.ps1 simulator`) shows traffic moving through the network,
the controller's step-by-step reasoning, and a comparison with a non-reactive network.*

---

## 📌 Master Documentation Portal

| Document | File Path | Focus & Key Contents |
| :--- | :--- | :--- |
| **Project Flow Manual** | [PROJECT_FLOW.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/PROJECT_FLOW.md) | Exhaustive 13-flow algorithmic, control-plane, and mathematical dataflow specification with paired Mermaid mindmaps and ASCII flows. |
| **Project Presentation** | [PROJECT_PRESENTATION.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/PROJECT_PRESENTATION.md) | Verbatim 20-slide slide companion, speaker notes, empirical data workbooks, and examiner Q&A defense. |
| **Project Explanation** | [PROJECT_EXPLANATION.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/PROJECT_EXPLANATION.md) | In-depth pedagogical guide explaining SDN, OpenFlow 1.3, Reflexion, fluid queue mathematics, and empirical attribution. |
| **System Architecture** | [selfx/docs/ARCHITECTURE.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/ARCHITECTURE.md) | Low-level subsystem architecture, interface definitions, Pydantic schemas, and state-transition guarantees. |
| **ASCII Control Flows** | [selfx/docs/CONTROL_FLOWS_ASCII.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/CONTROL_FLOWS_ASCII.md) | Complete encyclopedia of high-density ASCII sequence, architecture, and state diagrams. |
| **Mermaid Mindmaps** | [selfx/docs/SELF_IMPROVING_AGENT_MINDMAPS.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/SELF_IMPROVING_AGENT_MINDMAPS.md) | Master encyclopedia of visual Mermaid mindmaps across all system layers. |
| **Benchmark Suite v4** | [selfx/docs/BENCHMARKS_V4.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/BENCHMARKS_V4.md) | Full 86,400-window experimental evaluation, controller rankings, and bootstrap confidence intervals. |
| **Rule Demo & Veto Guide** | [selfx/docs/RULE_DEMO.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/RULE_DEMO.md) | Deep dive into OpenFlow 1.3 5s hard-timeouts and Gemini seed 1940 cycle 4 veto audit. |
| **Evaluator Guide** | [selfx/docs/PROJECT_GUIDE.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/PROJECT_GUIDE.md) | Quickstart verification manual for academic examiners and peer reviewers. |
| **Self-Improving Prototype** | [sdn-self-improving-agent/README.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/sdn-self-improving-agent/README.md) | Standalone Mininet topology, switch DPIDs, host addressing, and traffic generation specs. |
| **Slow-Loop Governor** | [slow-loop/README.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/slow-loop/README.md) | Two-timescale Lyapunov Drift-Plus-Penalty (DPP) governor and 5-specialist consensus engine. |
| **Public Dashboard & API** | [Web/README.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/Web/README.md) | Standard-library REST server, Cytoscape.js topology canvas, Chart.js time series, and security model. |
| **Visualizations Pipeline** | [visualizations/README.md](file:///c:/Users/RAVIPRAKASH/SDN/SDN/visualizations/README.md) | Matplotlib figure generation, telemetry time series, and asset synchronization. |

---

## 🎨 Colourful Architecture Mindmap

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#1E88E5', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#F3F4F6'}}}%%
flowchart TD
    classDef dataPlane fill:#00897B,stroke:#004D40,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef controlPlane fill:#1E88E5,stroke:#0D47A1,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef agentCore fill:#8E24AA,stroke:#4A148C,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef safetyGate fill:#E53935,stroke:#B71C1C,stroke-width:2px,color:#ffffff,font-weight:bold;
    classDef storage fill:#FB8C00,stroke:#E65100,stroke-width:2px,color:#ffffff;
    classDef presentation fill:#3949AB,stroke:#1A237E,stroke-width:2px,color:#ffffff;

    subgraph DataPlaneLayer ["Data Plane Network (Mininet & Open vSwitch)"]
        SW["4 Switches: s1 (Ingress), s2 (Core Splitter), s3 (Aggregator), s4 (Egress)"]:::dataPlane
        LINKS["Dual Bottlenecks: Primary (10M, 5ms, Q=40) | Secondary (10M, 12ms, Q=40)"]:::dataPlane
        HOSTS["8 Hosts: h1->h7 (Steady 4M UDP) | h2->h8 (Elephant Burst 14M UDP)"]:::dataPlane
    end

    subgraph ControlPlaneLayer ["Control Plane (Ryu SDN Controller)"]
        RYU["Ryu Controller (ofctl_rest, simple_switch_13)"]:::controlPlane
        TCAM["Switch TCAM: Table 0 Forwarding (Priority 1) + Elephant Override (Priority 100)"]:::controlPlane
        METERS["OpenFlow 1.3 Meter Tables: Token Bucket Ingress Clamping"]:::controlPlane
    end

    subgraph DecisionLayer ["Autonomous Cognitive Agent Core (selfx/)"]
        OBS["Telemetry Ingestion & 8D Feature Vector Extraction S(t)"]:::agentCore
        MEM["Caliper Episodic Memory (Delta <= 0.15 Caliper, Top-2 Neighbors)"]:::agentCore
        PROC["Subprocess-Isolated Inference Engine (3.8s Hard Watchdog Cutoff)"]:::agentCore
        LCB["Headroom Parameter Optimizer (Lower Confidence Bound: mu - 1.96*sigma)"]:::agentCore
    end

    subgraph SafetyLayer ["Deterministic Verification (selfx/safety.py)"]
        CAP["Invariant 1: Target Link Load <= 90%"]:::safetyGate
        THROT["Invariant 2: Flow Throttling <= 20.0%"]:::safetyGate
        FLOOR["Invariant 3: Rate Floor >= 512 kbps"]:::safetyGate
        FLOAT["IEEE-754 Arithmetic Repair (+1 kbps rounding adjustment)"]:::safetyGate
    end

    subgraph PersistenceLayer ["Experience & Artifact Lineage"]
        EXP[("Stratified Memory Bank (30 Records)")]:::storage
        BENCH[("86,400 Matrix Benchmark Traces (output/benchmarks/v4/)")]:::storage
    end

    subgraph PresentationLayer ["Public Web Visualizer & Operations (Web/)"]
        DASH["Standard-Library Web Server (server.py:5000)"]:::presentation
        CYTO["Cytoscape.js Topology Canvas"]:::presentation
        CHART["Chart.js Live Metrics Visualizer"]:::presentation
    end

    HOSTS --> SW
    SW --> LINKS
    SW <-->|OpenFlow 1.3 Flow-Mod & Stats| RYU
    RYU <-->|REST API /stats/port, /stats/flow| OBS
    OBS --> MEM
    MEM --> PROC
    PROC --> LCB
    LCB --> CAP & THROT & FLOOR & FLOAT
    CAP & THROT & FLOOR & FLOAT -->|Approved Action| RYU
    CAP & THROT & FLOOR & FLOAT -.->|Veto Fallback| RYU
    OBS & LCB --> EXP
    EXP --> BENCH
    BENCH --> DASH
    DASH --> CYTO & CHART
```

---

## 🏛️ End-to-End System Pipeline (ASCII Flow)

```
====================================================================================================
                                    END-TO-END SYSTEM PIPELINE
====================================================================================================

                       +---------------------------------------------------+
                       |             AUTONOMOUS SDN CONTROLLER             |
                       |                                                   |
                       |  +---------------------------------------------+  |
                       |  | Telemetry Ingestion & Feature Vector S(t)   |  |
                       |  |   8D: [u_pri, u_sec, q_pri, q_sec, ...]     |  |
                       |  +---------------------------------------------+  |
                       |                         |                         |
                       |                         v                         |
                       |  +---------------------------------------------+  |
                       |  | Caliper Memory Retrieval: Top-2 Neighbors   |  |
                       |  |   Filtered by Delta <= 0.15 & Regime Match  |  |
                       |  +---------------------------------------------+  |
                       |                         |                         |
                       |                         v                         |
                       |  +---------------------------------------------+  |
                       |  | Subprocess-Isolated Inference Engine        |  |
                       |  |   Parent Watchdog: 3.8s Cutoff (SIGKILL)    |  |
                       |  |   LLM Providers: Claude 3.5 / Gemini 2.5    |  |
                       |  |   Fallback Cascade: H2 -> H1 -> No-Op       |  |
                       |  +---------------------------------------------+  |
                       |                         |                         |
                       |                         v                         |
                       |  +---------------------------------------------+  |
                       |  | Deterministic Fail-Closed Safety Gate       |  |
                       |  |   1. Projected Target Load <= 90%           |  |
                       |  |   2. Flow Rate Drop <= 20% (+1 kbps Repair) |  |
                       |  |   3. Rate Limit Floor >= 512 kbps           |  |
                       |  +---------------------------------------------+  |
                       |                         |                         |
                       |                         v                         |
                       |  +---------------------------------------------+  |
                       |  | OpenFlow 1.3 Flow-Mod / Meter Dispatch      |  |
                       |  |   Priority 100 Elephant Override            |  |
                       |  |   Virtual Lease: hard_timeout = 5 seconds   |  |
                       |  +---------------------------------------------+  |
                       +-------------------------|-------------------------+
                                                 |
                                                 v OpenFlow 1.3 / REST API
                       +---------------------------------------------------+
                       |                 RYU SDN CONTROLLER                |
                       |        (ofctl_rest, simple_switch_13)             |
                       +---------------------------------------------------+
                                                 |
                                                 v OpenFlow 1.3 Channel
  +--------------------------------------------------------------------------------------------+
  |                             MININET DATA-PLANE NETWORK TOPOLOGY                            |
  |                                                                                            |
  |   [h1: 10.0.0.1]                                                           [h7: 10.0.0.7]  |
  |        |                                                                        |          |
  |   [h2: 10.0.0.2]---\          Primary Bottleneck Path (10M, 5ms)         /---[h8: 10.0.0.8]  |
  |        |            \                                                   /       |          |
  |   [h3: 10.0.0.3]----[s1]=============[s2]==================[s3]======[s4]----[h9: 10.0.0.9]  |
  |        |            /                                                   \       |          |
  |   [h4: 10.0.0.4]---/         Secondary Bottleneck Path (10M, 12ms)        \---[h10:10.0.0.10]|
  |                                                                                            |
  |   Traffic Profile: Steady Load (h1->h7 @ 4.0 Mbps) + Periodic Elephant Bursts (h2->h8)    |
  +--------------------------------------------------------------------------------------------+
====================================================================================================
```

---

## 📂 Complete Codebase File Index

```
SDN/
├── PROJECT_FLOW.md                   # 13 Operational & Algorithmic Flows (Mermaid & ASCII)
├── PROJECT_PRESENTATION.md           # 20-Slide Presentation Companion & Defense Guide
├── PROJECT_EXPLANATION.md            # Comprehensive Pedagogical Textbook Guide
├── README.md                         # Master Documentation Portal (This File)
├── SUBMISSION_READINESS_PLAN.md      # Acceptance Criteria Checklist & Submission Audit
│
├── sdn-self-improving-agent/         # Mininet Emulation Prototype Testbed
│   ├── README.md                     # Dedicated Testbed Guide with Topology Mindmaps
│   ├── topo.py                       # 4-switch linear OpenFlow 1.3 Mininet topology
│   └── traffic_gen.py                # iperf3 seeded burst generator with pattern [0,1,1,1,0,0,1,0]
│
├── selfx/                            # Core Autonomous SDN Agent Architecture
│   ├── README.md                     # Core Agent Engineering Manual & Architecture
│   ├── config.py                     # Central System Parameters, Thresholds, & Knobs
│   ├── topo.py                       # Mininet linear network topology implementation
│   ├── traffic_gen.py                # Burst schedule generator for live agent
│   ├── ryu_client.py                 # REST client for Ryu ofctl_rest telemetry & actuation
│   ├── latency_probe.py              # Sub-millisecond ping RTT probe harness
│   │
│   ├── agent/                        # Cognitive Control Subsystems
│   │   ├── bounded_control.py        # BoundedController with 3.8s watchdog & fallbacks
│   │   ├── deadline_provider.py      # Process-isolated provider worker with SIGKILL
│   │   ├── loss_aware_memory.py      # Caliper episodic memory & LCB headroom selection
│   │   ├── adaptive_memory.py        # Context vector extraction & regime classification
│   │   ├── fast_control.py           # Fast-path decision schema & action choice
│   │   ├── graph.py                  # LangGraph 8-node state machine implementation
│   │   ├── safety.py                 # Fail-closed deterministic safety gate & +1 kbps repair
│   │   ├── reward.py                 # Multi-objective normalized reward formulation
│   │   ├── metrics.py                # Telemetry delta calculus and 8D state embedding
│   │   ├── schemas.py                # Pydantic schemas for states, proposals, and actions
│   │   └── prompts.py                # Structured system prompts and few-shot formatting
│   │
│   ├── docs/                         # Authoritative Architectural Documents
│   │   ├── ARCHITECTURE.md           # Subsystem architecture, interfaces, and state guarantees
│   │   ├── BENCHMARKS_V4.md          # 86,400-window experimental benchmark suite and results
│   │   ├── CONTROL_FLOWS_ASCII.md    # Master encyclopedia of high-density ASCII flows
│   │   ├── SELF_IMPROVING_AGENT_MINDMAPS.md # Master encyclopedia of Mermaid architectural mindmaps
│   │   ├── PROJECT_FLOW.md           # Master project flow document
│   │   ├── PROJECT_PRESENTATION.md   # Presentation companion document
│   │   ├── PROJECT_EXPLANATION.md    # Master explanation document
│   │   ├── RULE_DEMO.md              # Step-by-step audit of Gemini seed 1940 cycle 4 veto
│   │   └── PROJECT_GUIDE.md          # Academic evaluator and reviewer guide
│   │
│   ├── eval/                         # Evaluation, Benchmarking & Statistical Verification
│   │   ├── benchmark_suite_v4.py     # 86,400-window multi-scenario matrix runner
│   │   ├── run_v4_benchmarks.py      # V4 suite execution harness across 10 held-out seeds
│   │   ├── paired_bootstrap_resampling.py # 4,000-draw non-parametric bootstrap resampling
│   │   ├── run_ablation.py           # Live A0/A1/A2 Mininet testbed ablation harness
│   │   ├── simulator.py              # Finite-buffer fluid queue simulator
│   │   └── plot_results.py           # Multi-metric plotting script
│   │
│   ├── tests/                        # Comprehensive Unit & Integration Test Suite
│   │   ├── test_core.py              # Schemas, metrics, and reward functions
│   │   ├── test_graph.py             # LangGraph state machine execution tests
│   │   ├── test_safety.py            # Safety gate invariants and +1 kbps floating-point tests
│   │   ├── test_adaptive_control.py  # Adaptive memory and regime stability tests
│   │   ├── test_v4_control.py        # Worker connection reuse and deadline cutoffs
│   │   └── test_meter_forwarding.py  # Meter table preservation and lease expirations
│   │
│   └── output/benchmarks/            # Raw Empirical Evidence & Trace Datasets
│       ├── v4/                       # 86,400-window raw JSON trace bundles
│       └── README.md                 # Evidence trace directory index and lineage
│
├── slow-loop/                        # Standalone Two-Timescale Lyapunov DPP Simulator
│   ├── README.md                     # Production-Grade Slow-Loop Architecture Guide
│   ├── run_benchmark.py              # CLI entry point for slow-loop evaluations
│   └── agentic/                      # Specialist agents, governor, replay, & fluid queue
│
├── Web/                              # Local Standard-Library Web Visualizer & REST Bridge
│   ├── README.md                     # Production REST API & Security Guide
│   ├── server.py                     # Zero-dependency threading HTTP server
│   ├── index.html                    # Cytoscape.js topology & Chart.js live visualizer
│   └── tests/                        # Public API and results integration tests
│
└── visualizations/                   # Visualization & Reporting Asset Pipeline
    ├── README.md                     # Automated Figure Generation & Asset Pipeline Guide
    └── create_visualizations.py      # Rebuilds figures and synchronizes with Web assets
```

---

## 💻 Key Implementation Modules & Annotated Code Snippets

### 1. Bounded Controller with Fallbacks (`selfx/agent/bounded_control.py`)

The `BoundedController` coordinates local heuristics, exact-context caching, episodic memory, and process-isolated LLM calls:

```python
class BoundedController:
    def __init__(self, provider='gemini', hybrid=True, model=None, budget_seconds=3.8):
        self.llm = DeadlineProvider(provider, model, budget_seconds)
        self.hybrid = hybrid
        self.cache = OrderedDict()
        self.last_explanation = {}

    def decide(self, net, summary, demand, memory, cycle):
        # 1. Synthesize local capacity-aware recommendation
        local, used = loss_aware_policy(net, summary, demand, memory, cycle)
        s = summary['simulation']
        signature = tuple(s[k] for k in ('capacity_mbps', 'buffer_mbit', 'primary_background_mbps',
                                         'alternate_background_mbps', 'elephant_mbps',
                                         'valid_reroute_out_port', 'current_output_port')) + tuple(s['queues_mbit'])
        
        # 2. Fast Bypasses: No-op for healthy network, episodic memory if supported
        if self.hybrid:
            if local.action == 'no_op':
                return local, 'healthy_bypass', used, ''
            scores, matched = memory.meter_estimates(summary, cycle)
            chosen = min(HEADROOMS, key=lambda h: abs(meter_decision(summary, demand, h).rate_limit_kbps - (local.rate_limit_kbps or 0)))
            supported = scores.get(chosen, {})
            if local.action == 'rate_limit' and supported.get('support', 0) >= 3 and supported.get('lower', 0) > .005:
                return local, 'episodic_memory', used, ''

        # 3. Process-Isolated LLM Call with 3.8s Watchdog
        try:
            choice = self.llm.choose(suggestion_messages(summary, memory.few_shot_examples(k=3, query=summary), local))
            # Rebuild flow parameters locally: Provider CANNOT install arbitrary rates!
            decision = local.model_copy(update={'rationale': choice['rationale']}) if choice['action'] == 'rate_limit' else decision_for(choice['action'], demand, choice['rationale'])
            guard = net.validate(demand, decision)
            if not guard.allowed:
                return local, 'validation_fallback', used, 'invalid_action_from_provider'
            return decision, 'api', used, ''
        except ProviderError as exc:
            return local, 'deadline_fallback' if str(exc) == 'local_deadline' else 'provider_fallback', used, str(exc)
```

### 2. Process-Isolated Provider IPC (`selfx/agent/deadline_provider.py`)

To prevent LLM API hangs from blocking the 5-second OpenFlow control cycle, worker processes execute inside an isolated child process guarded by a 3.8-second cutoff:

```python
class DeadlineProvider:
    def choose(self, messages):
        started = time.perf_counter()
        deadline = started + self.budget_seconds
        
        # Enforce rate-limiting gap (4.2s for Gemini, 3.1s for OpenRouter)
        gap = float(os.environ.get('GEMINI_REQUEST_GAP_SEC', '4.2'))
        delay = max(0, gap - (time.monotonic() - self.last_started.get(self.provider, 0)))
        if delay > 0 and delay > self.budget_seconds - 1.25:
            raise ProviderError('pacing_admission')
        if delay:
            time.sleep(delay)
            
        # Worker process execution and non-blocking IPC polling
        try:
            if self.process is None or not self.process.is_alive():
                self.close()
                parent, child = mp.get_context('spawn').Pipe()
                self.process = mp.get_context('spawn').Process(target=self.worker, args=(child, self.provider, self.model, messages), daemon=True)
                self.connection = parent
                self.process.start()
                child.close()
            else:
                self.connection.send(messages)
                
            while time.perf_counter() < deadline - 0.2:
                if self.connection.poll(max(0, min(0.05, deadline - 0.2 - time.perf_counter()))):
                    event = self.connection.recv()
                    if event['event'] == 'result':
                        return event['choice']
        finally:
            if result is None:
                self.close()  # Terminate and SIGKILL child worker immediately on timeout!
        raise ProviderError('local_deadline')
```

### 3. Fail-Closed Safety Gate & Floating-Point Repair (`selfx/safety.py` & `selfx/agent/loss_aware_memory.py`)

The deterministic safety verifier rejects unsafe rate limits or reroutes before OpenFlow Flow-Mod dispatch:

```python
def _check_rate_limit(ctx: SafetyContext) -> SafetyResult:
    # 1. Floor Invariant: Rate must be >= 512 kbps
    if ctx.proposed_rate_limit_kbps < config.SAFETY_MIN_RATE_LIMIT_KBPS:
        return SafetyResult(False, f"Rate {ctx.proposed_rate_limit_kbps:.0f} kbps is below 512 kbps floor", "no_op")

    # 2. Maximum Drop Invariant: Throttling must not exceed 20.0%
    dropped_pct = max(0.0, 100.0 * (ctx.target_flow_rate_kbps - ctx.proposed_rate_limit_kbps) / ctx.target_flow_rate_kbps)
    if dropped_pct > config.SAFETY_MAX_FLOW_DROP_PCT:
        return SafetyResult(False, f"Rate limit would drop {dropped_pct:.1f}% (> 20.0% limit)", "no_op")
    return SafetyResult(True, f"Rate limit drops only {dropped_pct:.1f}%", "rate_limit")

def meter_decision(summary, demand, headroom=0.1, reason='Capacity-aware meter'):
    s = summary['simulation']
    e = s['elephant_mbps']
    cap = max(0.8 * e, s['capacity_mbps'] - s['primary_background_mbps'] - headroom, 0.512)
    cap = min(e, cap)
    d = decision_for('rate_limit', demand, reason)
    d.rate_limit_kbps = math.ceil(cap * 1000)
    
    # IEEE-754 Bit Repair: Decimal 80% cap yields 20.000000000000004% after binary subtraction.
    # Add 1 extra kbps to prevent spurious safety vetoes without weakening the guard.
    if 100 * (e * 1000 - d.rate_limit_kbps) / (e * 1000) > 20:
        d.rate_limit_kbps += 1
    return d
```

---

## 🛠️ Step-by-Step Developer Guide: How to Build On This Project

### Tutorial 1: Adding a New LLM Provider (e.g., DeepSeek / Ollama / Local AI)

To add support for a new model provider (e.g., `ollama` or `deepseek`):
1. **Define Provider in [`selfx/agent/providers.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/providers.py)**:
   ```python
   class OllamaLLM:
       def __init__(self, model="llama3:8b", base_url="http://localhost:11434"):
           self.model = model
           self.base_url = base_url
           self.session = requests.Session()

       def with_structured_output(self, schema):
           self.schema = schema
           return self

       def invoke(self, messages):
           payload = {"model": self.model, "messages": messages, "format": "json", "stream": False}
           resp = self.session.post(f"{self.base_url}/api/chat", json=payload, timeout=2.5)
           data = resp.json()
           return self.schema.model_validate_json(data['message']['content'])
   ```
2. **Register in [`selfx/agent/deadline_provider.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/deadline_provider.py)**:
   Add `'ollama'` to provider selection logic and configure the desired pacing gap (e.g., `0.5s`).
3. **Execute Benchmark with New Provider**:
   ```powershell
   python selfx/eval/run_v4_benchmarks.py --provider ollama --model "llama3:8b"
   ```

---

### Tutorial 2: Creating a New SDN Network Topology (e.g., Fat-Tree / Spine-Leaf)

To replace or extend the linear 4-switch topology with a 2-tier Spine-Leaf data center topology:
1. **Create Topology Class in `selfx/topo.py`**:
   ```python
   class SpineLeafTopo(Topo):
       def build(self, num_spines=2, num_leaves=4, hosts_per_leaf=2):
           spines = [self.addSwitch(f'spine{i+1}', protocols='OpenFlow13') for i in range(num_spines)]
           leaves = [self.addSwitch(f'leaf{i+1}', protocols='OpenFlow13') for i in range(num_leaves)]
           
           # Fully mesh Spines and Leaves
           for spine in spines:
               for leaf in leaves:
                   self.addLink(spine, leaf, bw=20, delay='1ms')
                   
           # Attach hosts to leaf switches
           for i, leaf in enumerate(leaves):
               for h in range(hosts_per_leaf):
                   host = self.addHost(f'h_{i}_{h}', ip=f'10.0.{i}.{h+1}/24')
                   self.addLink(host, leaf, bw=100, delay='1ms')
   ```
2. **Update Allowed Egress Ports in [`selfx/agent/graph.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/graph.py)**:
   Provide the candidate port set mapping for multi-path routing across the available spines.

---

### Tutorial 3: Implementing a Custom Traffic Engineering Controller

To implement a new control baseline (e.g., `H3_Reinforcement_Learning`):
1. **Implement Policy Function in [`selfx/agent/bounded_control.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/agent/bounded_control.py)**:
   ```python
   def rl_policy(summary, demand, model_weights):
       obs = extract_features(summary)
       action_idx = model_weights.predict(obs)
       return map_index_to_decision(action_idx, demand)
   ```
2. **Register Controller in [`selfx/eval/benchmark_suite_v4.py`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/eval/benchmark_suite_v4.py)**:
   Add `'H3_RL'` to `CONTROLLERS` dictionary.
3. **Run 86,400 Matrix Benchmark & Paired Bootstrap**:
   ```powershell
   python selfx/eval/run_v4_benchmarks.py --controllers H3_RL
   python selfx/eval/paired_bootstrap_resampling.py --controllerA A4 --controllerB H3_RL
   ```

---

## 🔬 Empirical Performance Matrix (86,400 Windows)

The comprehensive benchmark spans **86,400 windows** across **9 controllers** and **8 distinct traffic scenarios** (steady load, heavy contention, diurnal cycles, bursty Poisson arrivals, adversarial elephant bursts, asymmetric workloads, multi-bottlenecks, and stochastic jitter):

| Controller | Architecture & Policy | Mean Reward | Latency (ms) | Throughput (Mbps) | Packet Loss (%) | Deadline Misses |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **H2 (Matched Heuristic)** | Capacity-Aware Proportional Rate Limiting | **+0.0833** | 13.91 | 11.22 | **7.077%** | **0** |
| **A4 (Claude Reflexion)** | LLM Reflexion + Caliper Episodic Memory | **+0.0828** | 13.94 | 11.21 | **7.075%** | **0** |
| **A4 (Gemini Reflexion)** | LLM Reflexion + Caliper Episodic Memory | **+0.0819** | 14.02 | 11.19 | 7.081% | **0** |
| **A3 (Headroom Optimizer)**| Parametric LCB Headroom Clustering | **+0.0811** | 14.15 | 11.16 | 7.088% | **0** |
| **A2 (Memory Agent)** | Raw Few-Shot Memory without Verbal Reflection | **+0.0792** | 14.48 | 11.10 | 7.142% | **0** |
| **A1 (Zero-Shot Agent)** | Single-Shot LLM without Episodic Memory | **+0.0784** | 14.62 | 11.08 | 7.189% | **0** |
| **H1 (Reroute Heuristic)**| Greedy Least-Loaded Path Rerouting | **+0.0776** | 14.81 | 11.02 | 7.391% | **0** |
| **ECMP (Dynamic Hash)** | 5-Tuple Static Flow Hashing | **+0.0712** | 16.20 | 10.74 | 8.120% | **0** |
| **H0 (Static Switch)** | Default L2 Learning Switch (No Adaptation) | **+0.0684** | 17.05 | 10.51 | 8.845% | **0** |

### Key Scientific Finding: Empirical Attribution
- **Advantage over Reroute Heuristic H1:** Cognitive agents (`A4_Claude`, `A4_Gemini`) achieve statistically significant reductions in packet loss ($7.075\%$ vs $7.391\%$) and higher reward ($+0.0828$ vs $+0.0776$) over classic dynamic rerouting (`H1`).
- **Attribution via Matched Heuristic H2:** When compared to `H2` (a deterministic heuristic equipped with identical capacity-aware rate synthesis), `A4` and `H2` are statistically indistinguishable under a 4,000-draw paired bootstrap ($p = 0.421$, $95\%\text{ CI} = [-0.0018, +0.0007]$). This establishes that **capacity-aware rate synthesis** is the governing mechanism driving performance gains.

---

## ⚡ Provider Wall-Clock Latency & Subprocess Isolation

```
+--------------------------------------------------------------------------------------------------+
| PROVIDER LATENCY & TIMEOUT RELIABILITY AUDIT (Sample Size: 2,400 Invocations per Provider)        |
+----------------------+--------------------+--------------------+--------------------+------------+
| Metric / Controller  | Claude 3.5 Sonnet  | Gemini 2.5 Flash   | OpenAI GPT-4o-Mini | Heuristic  |
+----------------------+--------------------+--------------------+--------------------+------------+
| Mean Latency         | 1,420 ms           | 620 ms             | 810 ms             | < 1 ms     |
| P95 Latency          | 2,180 ms           | 1,150 ms           | 1,340 ms           | < 1 ms     |
| P99 Latency          | 3,110 ms           | 1,840 ms           | 2,210 ms           | < 1 ms     |
| Max Latency          | 3,740 ms           | 2,490 ms           | 2,980 ms           | 2 ms       |
| Deadline Misses (>3.8s)| 0 (100% on time) | 0 (100% on time)   | 0 (100% on time)   | 0 (0.00%)  |
| Safety Gate Vetoes   | 14 / 2,400 (0.58%) | 22 / 2,400 (0.92%) | 31 / 2,400 (1.29%) | 0 (0.00%)  |
+----------------------+--------------------+--------------------+--------------------+------------+
```

---

## 🚀 Production Quickstart & Verification

### 1. Execute Unit & Integration Tests (40 Tests, 100% Pass)
```powershell
Push-Location selfx; New-Item -ItemType Directory -Force -Path tmp; ..\selfx\.venv\Scripts\python.exe -m pytest tests/ -v; Pop-Location
```

### 2. Run Comprehensive v4 Benchmark (86,400 Windows)
```powershell
.\selfx\.venv\Scripts\python.exe selfx/eval/run_v4_benchmarks.py --all-scenarios
```

### 3. Run Paired Bootstrap Resampling Analysis (4,000 Draws)
```powershell
.\selfx\.venv\Scripts\python.exe selfx/eval/paired_bootstrap_resampling.py --draws 4000
```

### 4. Launch Local Web Dashboard & Replay Inspector
```powershell
python Web/server.py
```
*Open `http://localhost:5000/` in any browser to inspect cycle-by-cycle network replays, Cytoscape topology animations, and safety gate veto traces.*

---

## 👥 Team & Academic Credits

- **Course:** EC466 — Software Defined Networks
- **Institution:** Indian Institute of Information Technology (IIIT) Dharwad
- **Team ID:** SDN_07 (SELF-X Project)
- **Academic Session:** Autumn 2026
