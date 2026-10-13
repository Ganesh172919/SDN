# Self-Improving SDN Flow-Management Agent (SELF-X)

> **Autonomous Software-Defined Network Flow Management with LLM Reflection, Few-Shot Memory, Governance, and DPP Control**
> *Course Project — EC466: Software Defined Networks | Team ID: SDN_07*

---

## 📌 Project Overview

This repository contains the current SELF-X project tracks and dashboard foundation. The implemented MVP is a single-agent LangGraph flow-management loop in `selfx/`; the `slow-loop/` directory contains a simulator-only governance and queue-control prototype; and `Web/` contains the authenticated dashboard with explicit Simulation and Live Network modes. The complete v2.0 target is a two-timescale system in which an LLM orchestrator and five specialists govern a fast Lyapunov drift-plus-penalty (DPP) controller. That final architecture is not yet integrated or fully implemented.

### Core Capabilities
- **Dashboard foundation**: The Web dashboard has Simulation Mode and Live Network Mode. Simulation data is labeled and is never presented as live telemetry; Live Network Mode shows only the current authenticated backend status and leaves unavailable metrics empty.
- **Dashboard authentication**: The server protects the dashboard and APIs with PBKDF2 password verification, expiring HTTP-only sessions, logout, and CSRF protection. Direct network-changing actions remain disabled.
- **Single-agent MVP**: `selfx/` contains a LangGraph state machine implementing `observe` -> `decide` -> `act` -> `wait` -> `observe_after` -> `compute_reward` -> `reflect` -> `memorize`.
- **Strict MVP 3-action space**:
  1. `reroute`: Dynamically re-routes elephant flows onto alternate, uncongested switch ports.
  2. `rate_limit`: Throttles aggressive flows using OpenFlow 1.3 meter tables.
  3. `no_op`: Keeps current forwarding state when network metrics are within healthy SLA thresholds.
- **Fail-Closed MVP safety gate**: `selfx/safety.py` rejects unsafe rate-limit and reroute proposals before the MVP attempts a REST operation. Its current configured thresholds are a maximum 20% flow drop, maximum 90% projected link utilization, and a 512 kbps rate floor; these are not the v2.0 DPP safety guarantee.
- **Verbal reflection and JSON memory**: The MVP computes latency/throughput/loss reward and prunes its JSON memory to 30 records. The slow-loop prototype separately has an in-memory replay buffer and deterministic reflection.
- **Not yet complete**: Multi-agent orchestration, live dashboard telemetry metrics, tool gateway, live DPP control, analytic backlog-bound validation, LoRA fine-tuning, non-regression promotion, A0-A5 experiments, and the full baseline study remain planned or partial.

---

## 🏛️ System Architecture

```
                       +---------------------------------------+
                       |       Current MVP: LangGraph Agent      |
                       |                                       |
                       |   +-----------+       +-----------+   |
                       |   |  OBSERVE  | ----> |  DECIDE   |   |
                       |   +-----------+       +-----------+   |
                       |         ^                   |         |
                       |         |                   v         |
                       |   +-----------+       +-----------+   |
                       |   |  REFLECT  | <---- |SAFETY_GATE|   |
                       |   +-----------+       +-----------+   |
                       |         |                   |         |
                       |         v                   v         |
                       |   [JSON Memory]       +-----------+   |
                       |   (Top 30 records)    |    ACT    |   |
                       |                       +-----------+   |
                       +-----------------------------|---------+
                                                     |
                                                     v (Flow-Mod / Meter REST API)
                       +---------------------------------------+
                       |            Ryu SDN Controller         |
                       |  (ryu.app.simple_switch_13, ofctl_rest)|
                       +---------------------------------------+
                                         | OpenFlow 1.3
                                         v
       +-------------------------------------------------------------------+
      |              Current MVP: Mininet SDN Testbed                    |
       |                                                                   |
       |   [h1]--\        Primary (10 Mbps, 5ms)       /--[h7 (Server)]    |
       |   [h2]---[s1]=====[s2]==================[s3]=====[s4]---[h8 (Server)]   |
       |                  \                      /                         |
       |                   Secondary (10 Mbps, 12ms)                       |
       |                                                                   |
       |   Traffic: Steady Load (h1->h7 @ 4M) + Elephant Bursts (h2->h8)   |
       +-------------------------------------------------------------------+
```

The diagram describes the current `selfx/` MVP boundary, not the complete v2.0
architecture. The target adds an authenticated dashboard/API boundary, a slow
LLM governance layer, a validated update channel $\Delta\Pi=(V,w,\text{action mask})$,
and a live fast DPP controller between telemetry and OpenFlow.

---

## 📂 Repository Structure

```
sdn-self-improving-agent/        # Incomplete/original topology and traffic prototype
├── topo.py
└── traffic_gen.py

selfx/                           # Single-agent live-testbed MVP
├── config.py                     # MVP configuration
├── topo.py                       # Linear Mininet topology
├── traffic_gen.py                # Seeded iperf3 traffic and burst schedule
├── ryu_client.py                 # Ryu ofctl_rest telemetry and write wrappers
├── latency_probe.py              # Ping RTT measurement
├── safety.py                     # Deterministic MVP safety check
├── agent/                        # LangGraph, schemas, metrics, reward, memory, prompts
├── eval/                         # A0/A1/A2 live-testbed harness and plotting
└── tests/                        # Dependency-light MVP tests with fakes

slow-loop/                        # Governance and DPP-like simulator prototype
├── agentic/                      # Specialists, governor, replay, safety, reward, simulator
├── tests/                        # Unit tests for the simulator/governor track
└── run_benchmark.py              # Mock benchmark entry point

Web/                              # Authenticated dashboard and standard-library server
├── server.py                     # Login, sessions, CSRF, status, memory, ablation, Ryu GET proxy
├── login.html                    # Login page
├── index.html                    # Dashboard
├── CSS/Style.css                 # Dashboard and login styling
├── js/                           # UI, simulation, charts, agent view, topology view
└── tests/test_auth.py            # Authentication integration tests

PS_01_Problem_Statement.pdf       # v1.0 problem statement
SELF-X_Problem_Statement_v2_Revised.docx  # v2.0 authoritative specification
README.md                         # Project documentation and roadmap
```

No generated experiment logs, plots, datasets, or saved result files are currently
present in the repository. Do not treat dashboard demo values or README examples as
experimental evidence.

---

## ⚙️ Prerequisites & Environment Setup

The live testbed targets Linux or **Windows Subsystem for Linux (WSL2)** with Ubuntu 22.04 LTS. The dashboard and its authentication tests run on a normal Python installation and do not require Mininet, Ryu, or third-party Python packages.

### 1. System Packages
```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch iperf3 python3-pip curl net-tools
```

### 2. Python Dependencies
For the `selfx/` MVP, create the documented agent environment and install:
```bash
cd selfx
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ryu, Mininet, Open vSwitch, and iperf3 are external system dependencies listed
in `selfx/requirements.txt`; they are not installed by that requirements file.
The `slow-loop/` track uses the Python 3.11+ standard library and has an optional
local OpenAI-compatible model endpoint. The Web server also uses only the standard
library.

### 3. Ryu Compatibility Fix
The root-level `patch_ryu.py` described by the older documentation is not present.
Use a compatible Ryu environment as described in `selfx/README.md`; do not run a
missing patch command.
```bash
# Verify the installed Ryu command in the dedicated Ryu environment.
ryu-manager --version
```

### 4. API Key and Dashboard Authentication Configuration
The `selfx/` MVP can integrate with Anthropic Claude via `ChatAnthropic`. Configure
the key locally only when running that MVP; never place it in this README or commit
it. The current MVP does not implement the deterministic no-key fallback claimed by
the older root README.
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

The Web dashboard requires a locally configured username and PBKDF2 password hash.
Use `.env.example` as a placeholder reference and generate the hash interactively:
```powershell
$env:SELFX_AUTH_USERNAME = "demo"
$env:SELFX_AUTH_PASSWORD_HASH = (python Web/server.py --hash-password)
```

The server does not automatically load `.env` files. Set environment variables in
the shell or deployment environment. `.env` is ignored by Git; real passwords,
hashes, and session values must remain local.

---

## 🚀 Step-by-Step Reproduction Guide

### Dashboard: Run the Authenticated Web UI
From the repository root, configure the local demo account as described above and
start the standard-library server:
```powershell
python Web/server.py
```

Open `http://localhost:5000/login`. The dashboard starts in Simulation Mode. Live
Network Mode only reports the authenticated `/api/status` response; it does not
invent live metrics when the controller is unavailable. Dashboard authentication
tests are run with:
```powershell
python -m unittest discover -s Web/tests -p "test_auth.py" -v
```
The login page, dashboard, protected APIs, session logout, and CSRF checks are
implemented. Direct network-changing action endpoints and Ryu POST proxy writes
remain disabled and return HTTP 409.

### Phase 0: Verify REST API Reconnaissance
The live-testbed reconnaissance belongs to the `selfx/` MVP. Run it only on a
Linux/WSL environment with Ryu, Mininet, Open vSwitch, and root privileges:
```bash
cd selfx
ryu-manager ryu.app.ofctl_rest ryu.app.simple_switch_13
```
This tests:
- `GET /stats/switches`
- `GET /stats/port/<dpid>`
- `GET /stats/flow/<dpid>`
- `POST /stats/flowentry/add`

With the controller and topology running, inspect the actual response shapes:
```bash
curl http://localhost:8080/stats/switches
curl http://localhost:8080/stats/flow/1
curl http://localhost:8080/stats/port/1
curl -X POST -d '{"dpid":1,"priority":100,"match":{"in_port":1},"actions":[{"type":"OUTPUT","port":2}]}' \
  http://localhost:8080/stats/flowentry/add
```

The last command changes the live MVP testbed. Do not run it against a production
controller; Phase 1 Web action endpoints remain disabled.

---

### Phase 1 & 2: Start Ryu Controller
Open a terminal (or run as background service):
```bash
cd selfx
ryu-manager --ofp-tcp-listen-port 6653 ryu.app.simple_switch_13 ryu.app.ofctl_rest
```

Verify that Ryu REST API is listening:
```bash
curl http://127.0.0.1:8080/stats/switches
```

Start the actual MVP topology from a second terminal:
```bash
cd selfx
sudo -E python3 topo.py
```

The `selfx/ryu_client.py` module documents and implements the available
`get_state`, flow-entry, meter-entry, and clear-flow calls. The root-level
`sdn-self-improving-agent/` directory does not contain this client.

---

### Phase 3 & 4: Run the Standalone Interactive Agent Loop
The implemented MVP is invoked from the `selfx/` package. There is no standalone
continuous `agent/graph.py` command at the root path documented by the old README;
the graph represents one cycle and is driven by the evaluation harness. To sanity-
check one cycle from an activated `selfx` environment:
```bash
cd selfx
python3 -m tests.test_core
python3 -m tests.test_graph
```

The `selfx/agent/graph.py` cycle polls `get_state()`, formats the observation and
memory examples, requests a structured action, applies `selfx/safety.py`, optionally
calls the MVP Ryu flow/meter wrappers, measures a later snapshot, computes reward,
and stores reflection. These tests use fake LLM/network functions; they do not prove
that a real Ryu/Mininet rule was installed.

For one manually controlled cycle in a configured `selfx` environment:
```python
from agent.graph import AgentDeps, build_graph, run_cycle
from agent.memory import MemoryStore
from langchain_anthropic import ChatAnthropic

deps = AgentDeps(
  llm=ChatAnthropic(model="claude-sonnet-4-6"),
  memory=MemoryStore(path="scratch_memory.json"),
)
app = build_graph(deps)
result = run_cycle(app, cycle=0, raw_state_prev=None)
print(result["installed_action"], result["reward"], result["reflection"])
```

---

### Phase 5: Run the Current MVP A0/A1/A2 Benchmark

The evaluation harness evaluates three conditions under the identical traffic seed and topology:
- **A0 (Static Baseline)**: Default Ryu L2 switch forwarding rules, no adaptive agent.
- **A1 (Zero-Shot Agent)**: Active LLM agent, but memory is disabled and reflection is not carried forward each cycle.
- **A2 (Self-Improving Agent)**: Full reflection and few-shot memory loop enabled.

Run the implemented MVP harness for 600 seconds per condition:
```bash
cd selfx
sudo -E python3 -m eval.run_ablation --duration 600
```

This requires a live Ryu/Mininet environment and may install MVP flow/meter
requests through `selfx/ryu_client.py`. It is not the v2.0 A0-A5 evaluation.

---

### Visualizing Comparison Results
Generate side-by-side comparison plots across all three conditions:
```bash
cd selfx
python3 -m eval.plot_results
```

Generated outputs are written under `selfx/eval/logs/` and `selfx/eval/plots/`:
- `latency_comparison.png`: End-to-end packet latency comparison.
- `throughput_comparison.png`: Network throughput under elephant-flow contention.
- `loss_comparison.png`: Packet loss percentage across conditions.
- `reward_trend.png`: A2 self-improvement trajectory showing visible reward growth from early to late cycles.
- The current plotting script produces latency, throughput, loss, and reward-trend plots; it does not produce the older `summary_dashboard.png` claim.

---

## 📊 Evaluation & Acceptance Criteria

| Criteria | Target | Verification Method |
| :--- | :--- | :--- |
| **Dashboard authentication** | Login, protected dashboard/API, logout, expiry, and CSRF checks work | `python -m unittest discover -s Web/tests -p "test_auth.py" -v` |
| **Dashboard safety** | Simulation values are not presented as live; network-changing Web actions remain disabled | Select both dashboard modes and verify live failure states; authenticated write regression test returns HTTP 409 |
| **MVP stability** | $\ge 10$ minutes unattended without crashing | `selfx/eval/run_ablation.py --duration 600` on a configured Linux/WSL testbed; result currently unverified |
| **MVP self-improvement** | A2 rolling reward trend improves over A1 | Compare saved `selfx/eval/plots/reward_trend.png`; no result files are currently present |
| **MVP latency reduction** | $\ge 20\%$ reduction vs static A0 during congestion | Compare saved A0/A2 logs and plots; no result files are currently present |
| **MVP safety compliance** | No unsafe accepted action under configured 20% flow-drop / 90% projected-utilization limits | MVP safety tests and saved live audit evidence; live compliance is unverified |
| **v2.0 stability evidence** | Backlog bound holds in at least 95% of at least 1,000 intervals across three traffic profiles | Future DPP bound-evaluation harness and saved raw results |
| **v2.0 ablation** | A0-A5 progression plus required baseline comparison | Future six-stage harness, metrics, plots, and evidence bundle |

---

## 🔬 Mathematical Reward Formulation

The multi-objective reward $R(t)$ at control step $t$ is calculated over the observation window $\Delta t$:

$$R(t) = w_{\text{lat}} \cdot \tilde{\Delta}\text{latency} + w_{\text{tput}} \cdot \tilde{\Delta}\text{throughput} - w_{\text{loss}} \cdot \tilde{\Delta}\text{loss}$$

The implemented `selfx/agent/reward.py` uses signed changes from before to after,
with characteristic scales of 50 ms, 5,000 kbps, and 20 percentage points. Its
configured weights are -0.4 for latency change, +0.4 for throughput change, and
-0.2 for loss change. The v2.0 specification expands the objective to latency,
loss, energy, and resource cost under the governed DPP controller; that formulation
and its stability bound are not yet implemented in the live MVP.

## 🧭 Implementation Roadmap

The phases below are ordered by dependency. A phase is complete only when its
acceptance evidence is saved and reviewable. The v2.0 target must not be inferred
from simulator output, dashboard demo values, or source filenames alone.

### Phase 1 - Repository and dashboard foundation (complete)
- **Objective:** Preserve the existing dashboard while making simulation/live state explicit and protecting access.
- **Directories/files:** `Web/`, `.gitignore`, `.env.example`.
- **Dependencies:** Python standard library.
- **Deliverables:** Authenticated login page, PBKDF2 credential verification, expiring HTTP-only sessions, CSRF protection, logout, mode safeguards, and disabled network-changing Web actions.
- **Acceptance:** `Web/tests/test_auth.py` passes; `git diff --check` is clean; browser verification confirms simulation values are labeled and live failures remain empty/disconnected.
- **Status:** Complete in commit `3c4ae3a`; review and maintenance continue.

### Phase 2 - Integration foundation (planned)
- **Objective:** Define stable interfaces among the dashboard, backend/API, Ryu/ONOS controller, telemetry, agentic layer, and fast controller.
- **Directories/files:** `Web/server.py`, `Web/js/`, `selfx/ryu_client.py`, `selfx/agent/`, future integration modules.
- **Dependencies:** Phase 1; controller and testbed availability; design decision on Ryu versus ONOS/RESTCONF support.
- **Deliverables:** Versioned telemetry schema, authenticated read-only API contract, actuator boundary, correlation IDs, error semantics, and a clear simulation/live data provenance field.
- **Acceptance:** Contract tests cover success, empty, disconnected, stale, and malformed responses; no dashboard control can bypass the actuator safety boundary.
- **Status:** Planned. The current Web status endpoint reports controller health only; it is not a live metrics stream.

### Phase 3 - Fast-timescale DPP control loop (planned)
- **Objective:** Implement and evaluate the v2.0 Lyapunov drift-plus-penalty controller before connecting it to an LLM.
- **Directories/files:** `slow-loop/agentic/simulator.py` as a prototype reference; future DPP controller and tests; `selfx/ryu_client.py` for later actuation reuse.
- **Dependencies:** Phase 2 telemetry/action contracts; queue and flow state design; explicit assumptions for arrivals, service, boundedness, and capacities.
- **Deliverables:** Per-flow/per-switch queue representation, queue dynamics, arrival/service estimates, $L(Q)=\frac{1}{2}\sum_i Q_i^2$, drift-plus-penalty action selection, OpenFlow mapping, and analytic constants $B$, $C$, and $\epsilon$.
- **Acceptance:** At least 1,000 control intervals across three traffic profiles, with the backlog-bound violation rate and raw interval data saved; no formal guarantee is claimed before these assumptions and results are reviewed.
- **Status:** Planned. `slow-loop/agentic/simulator.py` has bounded fluid queues and a heuristic `drift + V * penalty` score, but not the formal DPP controller or bound validation.

### Phase 4 - Slow-timescale governance (planned/partial prototype)
- **Objective:** Implement the orchestrator and five specialists that emit a validated policy update $\Delta\Pi=(V,w,\text{action mask})$.
- **Directories/files:** `slow-loop/agentic/agents.py`, `governor.py`, `schemas.py`, `prompts.py`, and `model_client.py`.
- **Dependencies:** Phase 2 telemetry schema and Phase 3 policy contract.
- **Deliverables:** Orchestrator, flow-sizing, routing/traffic-engineering, anomaly, security, and slicing specialists; structured proposal parsing; policy versioning and an explicit slow-to-fast update channel.
- **Acceptance:** Real or declared mock model inputs produce auditable proposals; invalid proposals are rejected; accepted updates are consumable by the fast controller without changing its drift math.
- **Status:** Partial prototype. The current track uses deterministic specialist rules or one local OpenAI-compatible client and only simulates the governed controller; it is not connected to `selfx/` or Ryu.

### Phase 5 - Safety-gated adaptation (planned)
- **Objective:** Add candidate LoRA updates, validation gates, and non-regression promotion without conflating candidates with accepted policies.
- **Directories/files:** Future adaptation modules; `slow-loop/agentic/safety.py` as a policy-step reference; replay and benchmark paths.
- **Dependencies:** Phases 2-4; high-reward trajectory format; defined stress workloads and rollback semantics.
- **Deliverables:** Candidate artifact store, LoRA fine-tuning workflow, hard-safety checks, non-regression stress campaign, promotion/rollback decision, and audit trail.
- **Acceptance:** Every candidate is isolated, tested, either promoted or rejected, and linked to reproducible metrics; no candidate can affect the fast loop before promotion.
- **Status:** Planned. No LoRA implementation or non-regression campaign exists in the repository.

### Phase 6 - Experience and improvement (planned/partial prototype)
- **Objective:** Implement replay, reflection, self-critique, and the experience workflow required by v2.0.
- **Directories/files:** `selfx/agent/memory.py`, `selfx/agent/reward.py`, `selfx/agent/graph.py`, `slow-loop/agentic/replay.py`, and `slow-loop/agentic/reward.py`.
- **Dependencies:** Phase 2 schemas and Phase 5 candidate/promotion records.
- **Deliverables:** Shared experience schema, prioritized replay policy, reflection/self-critique records, retention/pruning rules, and provenance linking outcomes to accepted policies.
- **Acceptance:** Successes and failures are replayable; memory does not silently mix simulated and live evidence; reflection and reward records can reproduce a governance decision.
- **Status:** Partial. The MVP has JSON memory and LLM reflection; the slow-loop has bounded in-memory replay and deterministic reflection; neither is integrated with v2.0 adaptation.

### Phase 7 - Evaluation and evidence (planned; current MVP harness is A0-A2 only)
- **Objective:** Measure the complete v2.0 system against the staged A0-A5 progression, required baselines, stress tests, and specification targets.
- **Directories/files:** `selfx/eval/`, `slow-loop/agentic/benchmark.py`, future experiment harnesses, and generated result directories.
- **Dependencies:** Phases 2-6; reproducible topologies and traffic profiles; declared seeds and environment versions.
- **Deliverables:** A0 static control, A1 single LLM, A2 reflection, A3 LoRA, A4 multi-agent, A5 DPP; six specified baseline comparisons; at least three topologies, two traffic generators/profiles, backlog-bound evidence, latency/throughput/loss/energy/resource metrics, convergence time, control-plane overhead, and generalization results.
- **Acceptance:** Raw telemetry, configurations, logs, plots, statistical tests, and reproduction commands are saved with every claim; simulation results are labeled separately from live Mininet/Ryu results.
- **Status:** Partial MVP only. `selfx/eval/run_ablation.py` implements A0/A1/A2 and requires a real testbed; no saved results are currently present. `slow-loop/run_benchmark.py` is simulator-only and is not the v2.0 A0-A5 harness.

### Team workflow
Select one phase and record the focused files, dependency, acceptance check, and evidence location before editing. Avoid parallel edits to the same module. For every change: run the narrow tests first, review `git diff --check` and `git diff`, commit with a descriptive message, and push only after verification. Do not commit `.env`, passwords, password hashes, session tokens, generated logs, or unreviewed experiment output.

---

## 📝 Team & Credits
- **Course**: EC466 — Software Defined Networks (IIIT Dharwad)
- **Team ID**: SDN_07 (SELF-X Project)
- **Session**: Aug – Nov 2026
