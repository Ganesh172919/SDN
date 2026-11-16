# SELF-X Evaluation, Benchmarking & Verification Harness

> **Production Guide to the Shared Fluid Datapath, Audited CPU Comparison Suite, Neural Baselines, and Publication Plotting Engines**  
> *Module Directory: `selfx/eval/` | Primary Runtimes: Python 3.12, PyTorch 2.8.0+cpu, NumPy, Matplotlib*  
> *Component Guide — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*  
> *Document Version: 2.4.0-Production*

---

## 📌 Table of Contents
1. [Executive Summary & Subsystem Architecture](#executive-summary--subsystem-architecture)
2. [Shared Fluid Datapath Simulation Engine (`pipeline_model.py`)](#shared-fluid-datapath-simulation-engine-pipeline_modelpy)
   - [Lindley Queue Recurrence Formulation](#lindley-queue-recurrence-formulation)
   - [Traffic Schedule Projection onto 100 ms Slots](#traffic-schedule-projection-onto-100-ms-slots)
   - [Composite Multi-Objective Reward Function](#composite-multi-objective-reward-function)
3. [Local LLM Inference & Multi-Agent Conditioning (`audited_models.py`)](#local-llm-inference--multi-agent-conditioning-audited_modelspy)
   - [SmolLM2-135M Backbone & Adapter Setup](#smollm2-135m-backbone--adapter-setup)
   - [The Five Specialist Prompts & Orchestrator Consensus](#the-five-specialist-prompts--orchestrator-consensus)
   - [Simulated Control Latency Modeling (400 ms Slots)](#simulated-control-latency-modeling-400-ms-slots)
4. [Deep Neural Reinforcement Learning Baselines (`neural_baselines.py`)](#deep-neural-reinforcement-learning-baselines-neural_baselinespy)
   - [PyTorch Deterministic Multi-Threading Setup](#pytorch-deterministic-multi-threading-setup)
   - [Deep Q-Network (DQN) Architecture & Replay Mechanics](#deep-q-network-dqn-architecture--replay-mechanics)
   - [Two-Agent Independent Q-Learning (IQL / MARL)](#two-agent-independent-q-learning-iql--marl)
5. [Master Audited Comparison Runner (`run_audited_comparison.py`)](#master-audited-comparison-runner-run_audited_comparisonpy)
6. [Revision Verification & Sensitivity Suite](#revision-verification--sensitivity-suite)
   - [Trace-Level Sensitivity & 20,000 Bootstrap Draws (`revision_analysis.py`)](#trace-level-sensitivity--20000-bootstrap-draws-revision_analysispy)
   - [Neural Proposal Disparity vs. Guard Convergence (`verify_neural_guard.py`)](#neural-proposal-disparity-vs-guard-convergence-verify_neural_guardpy)
   - [Fixed Governor Schedule Equivalence (`verify_fixed_governor.py`)](#fixed-governor-schedule-equivalence-verify_fixed_governorpy)
   - [Bit-for-Bit Manuscript Reproduction Verifier (`verify_manuscript_reproduction.py`)](#bit-for-bit-manuscript-reproduction-verifier-verify_manuscript_reproductionpy)
7. [Vector Plotting & Publication Asset Generators](#vector-plotting--publication-asset-generators)
   - [Manuscript Figures & Tables (`plot_manuscript.py`, `plot_expanded_paper.py`)](#manuscript-figures--tables-plot_manuscriptpy-plot_expanded_paperpy)
   - [Supplementary 13-Plot Comparison Atlas (`plot_audited_comparison.py`)](#supplementary-13-plot-comparison-atlas-plot_audited_comparisonpy)
8. [Data Schemas, Validation & Serialization (`result_schema.py`, `result_writer.py`)](#data-schemas-validation--serialization-result_schemapy-result_writerpy)
9. [Operator Verification & Execution Runbook](#operator-verification--execution-runbook)

---

## 🏛️ Executive Summary & Subsystem Architecture

The `selfx/eval/` directory contains the complete scientific benchmarking, simulation, and verification engine for the SELF-X platform. It is engineered to provide **100% auditable CPU execution**, eliminating cloud API dependencies, unverified baseline proxies, and opaque simulation shortcuts.

```
+-----------------------------------------------------------------------------------------+
|                                EVALUATION HARNESS PIPELINE                              |
|                                                                                         |
|  [ Synthetic Traffic Schedules (traffic_gen.py) ]                                       |
|  - Training Seeds: 1000-1017 (21,600 slots)                                             |
|  - Evaluation Seeds: 2100-2111 (21,600 slots, 3 Workload Profiles)                      |
|                                     |                                                   |
|                                     v                                                   |
|  +-----------------------------------------------------------------------------------+  |
|  | Shared Fluid Datapath Simulator (pipeline_model.py)                               |  |
|  | - Two-Path Topology: Primary (10M, 2ms, Q=40) | Secondary (10M, 12ms, Q=40)        |  |
|  | - Lindley Queue Recurrence: Q(t+1) = min(B, max(0, Q(t) + A(t) - C*tau))           |  |
|  | - 100 ms Decision Slots (tau = 0.1s), 5s Windows, 30s Governance Epochs            |  |
|  +-----------------------------------------------------------------------------------+  |
|                                     |                                                   |
|         +---------------------------+---------------------------+                       |
|         |                                                       |                       |
|         v                                                       v                       |
|  +-------------------------------------+  +------------------------------------------+  |
|  | Neural Baselines (neural_baselines) |  | Local Language Models (audited_models)   |  |
|  | - DQN: 2x64 MLP, 20k Replay, Target |  | - Hugging Face SmolLM2-135M-Instruct     |  |
|  | - Two-Agent IQL: Routing + Metering |  | - Frozen LoRA Adapter (r=8, alpha=16)    |  |
|  | - Deterministic PyTorch (2 Threads) |  | - 5 Specialists + 1 Orchestrator         |  |
|  +-------------------------------------+  +------------------------------------------+  |
|                                     |                                                   |
|                                     v                                                   |
|  +-----------------------------------------------------------------------------------+  |
|  | Deterministic Safety Guard (safety.py, action_gateway.py)                         |  |
|  | - Alternate Path Utilization <= 90% | Meter Floor >= 512k | Bulk Reduction <= 20% |  |
|  +-----------------------------------------------------------------------------------+  |
|                                     |                                                   |
|                                     v                                                   |
|  +-----------------------------------------------------------------------------------+  |
|  | Master Runner & Verification Suite (run_audited_comparison.py)                    |  |
|  | - Evaluates 14 Configurations x 12 Seeds = 168 Episodes (302,400 Slots)           |  |
|  | - Cryptographic Action Hashing: SHA-256 digests over all applied actions            |  |
|  | - Statistical Significance: Stratified 20,000 Bootstrap Draws & Holm Adjustment   |  |
|  +-----------------------------------------------------------------------------------+  |
|                                     |                                                   |
|         +---------------------------+---------------------------+                       |
|         |                                                       |                       |
|         v                                                       v                       |
|  +-------------------------------------+  +------------------------------------------+  |
|  | Publication Plotters (plot_manuscript) | | Web REST Bridge (Web/server.py)          |  |
|  | - 4 Vector Figures (PDFs)           |  | - /api/comparison/* (Configs, Effects)   |  |
|  | - manuscript_table.tex & results.tex |  | - /api/pipeline/* (Summary, Runs)        |  |
|  | - Supplementary 13-Plot Atlas (PDF) |  | - /api/analytics/* (DPP, LoRA, t-Tests)  |  |
|  +-------------------------------------+  +------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

---

## 🌊 Shared Fluid Datapath Simulation Engine (`pipeline_model.py`)

The fluid datapath simulates a dual-bottleneck network topology without requiring external Mininet kernel virtualization.

### Lindley Queue Recurrence Formulation
For each path $k \in \{1, 2\}$, the fluid queue backlog $Q_k(t)$ (Mbit) updates every $\tau = 100\,\text{ms}$ according to:
$$Q_k(t+1) = \min\Big( B_k, \, \max\big(0, \, Q_k(t) + A_k(t) - C_k \cdot \tau \big) \Big)$$
- **Capacities**: Primary $C_1 = 10.0\,\text{Mbps} = 1.0\,\text{Mbit/slot}$; Secondary $C_2 = 10.0\,\text{Mbps}$.
- **Buffer Ceiling**: $B_1 = B_2 = 2.0\,\text{Mbit}$ ($250\,\text{KB}$).
- **Propagation Delays**: Primary $d_1 = 2.0\,\text{ms}$; Secondary $d_2 = 12.0\,\text{ms}$.

If offered traffic $A_k(t)$ plus existing queue exceeds $B_k + C_k \cdot \tau$, drop occurs:
$$L_k(t) = \max\Big(0, \, Q_k(t) + A_k(t) - C_k \cdot \tau - B_k \Big)$$

### Traffic Schedule Projection onto 100 ms Slots
`demand_series()` projects continuous event logs from `selfx/traffic_gen.py` into discrete 100 ms offered demand vectors:
- Background UDP mice flows ($h_1 \to h_7$): Constant $4.0\,\text{Mbps}$ ($0.4\,\text{Mbit/slot}$).
- Elephant flow burst ($h_2 \to h_8$): Injected $14.0\,\text{Mbps}$ ($1.4\,\text{Mbit/slot}$) at $T = 30\,\text{s}$.
- Irreducible capacity limit: Combined demand ($18\,\text{Mbps}$) exceeds single link capacity ($10\,\text{Mbps}$), demanding intelligent multi-path offloading.

### Composite Multi-Objective Reward Function
Performance across each 5-second window ($50$ slots) is evaluated by `window_reward()`:
$$R(w) = w_{\text{delay}} R_{\text{delay}} + w_{\text{loss}} R_{\text{loss}} + w_{\text{goodput}} R_{\text{goodput}} + w_{\text{energy}} R_{\text{energy}} + w_{\text{churn}} R_{\text{churn}}$$
- Default Weights: $0.25 / 0.25 / 0.25 / 0.15 / 0.10$.
- Normalized Scores: Each component is normalized into $[0, 1]$ against operational targets.

---

## 🧠 Local LLM Inference & Multi-Agent Conditioning (`audited_models.py`)

`audited_models.py` provides the local language model interface, executing real forward passes on the CPU.

### SmolLM2-135M Backbone & Adapter Setup
- **Base Model**: `HuggingFaceTB/SmolLM2-135M-Instruct` (Git commit: `12fd25f77366fa6b3b4b768ec3050bf629380bac`).
- **Trained LoRA Adapter**: Loaded from `selfx/output/pipeline_study/adapter/`.
- **Inference Mode**: Evaluated in `torch.no_grad()` with deterministic token generation.

### The Five Specialist Prompts & Orchestrator Consensus
The multi-agent governor executes 5 specialist roles and 1 orchestrator:
1. `flow sizing`: Evaluates elephant burst magnitude.
2. `routing`: Evaluates alternate path headroom.
3. `congestion`: Audits buffer growth rate.
4. `safety`: Assesses invariant compliance risk.
5. `service`: Checks P95 latency SLA compliance.
6. `orchestrator`: Aggregates the 5 ballots into a bounded objective parameter vector:
   $$\Delta \pi = (\Delta w_{\text{delay}}, \Delta w_{\text{loss}}, \Delta w_{\text{energy}}, \Delta V)$$

### Simulated Control Latency Modeling (400 ms Slots)
To model real-world inference delays:
- Each forward pass incurs a **400 ms delay** ($4$ slots).
- During these 4 slots, the switch hardware continues executing the prior decision, accurately penalizing slow controllers for delayed interventions.
- S2 (Critique) incurs $800\,\text{ms}$ ($8$ slots).
- S5 Multi-Agent Governor incurs $800\,\text{ms}$ (5 parallel specialists + 1 orchestrator).

---

## 🤖 Deep Neural Reinforcement Learning Baselines (`neural_baselines.py`)

`neural_baselines.py` trains and evaluates true deep reinforcement learning baselines.

### PyTorch Deterministic Multi-Threading Setup
```python
torch.set_num_threads(2)
torch.use_deterministic_algorithms(True)
```
Ensures 100% reproducible weights across platforms.

### Deep Q-Network (DQN) Architecture & Replay Mechanics
- **Architecture**: 2-layer MLP ($8\text{D Input} \to 64 \to 64 \to 3\text{D Output}$).
- **Action Set**: `0: no_op`, `1: reroute`, `2: rate_limit`.
- **Training Settings**:
  - Replay Buffer Capacity: $20,000$ transitions.
  - Batch Size: $64$.
  - Optimizer: Adam ($\eta = 0.001$, $\gamma = 0.97$).
  - Target Network Sync: Every $100$ gradient updates.
  - Cadence: Train every $8$ slots; greedy evaluation every $100\,\text{ms}$.

### Two-Agent Independent Q-Learning (IQL / MARL)
- **Agent 1 (Routing Head)**: 2-layer MLP predicting `[primary, alternate]`.
- **Agent 2 (Metering Head)**: 2-layer MLP predicting `[none, clamp]`.
- **Training**: Each agent maintains its own replay buffer and target network, updating from shared team reward.

---

## 🏃 Master Audited Comparison Runner (`run_audited_comparison.py`)

The master benchmarking script executes the full experimental evaluation:

```powershell
# Smoke test (Quick validation run)
python selfx/eval/run_audited_comparison.py --smoke --output reproduced/smoke

# Full evaluation (168 runs across all 14 controllers)
python selfx/eval/run_audited_comparison.py --output reproduced/full
```

### Generated Artifacts
1. `runs.json` (3.1 MB): Seed assignments, training fingerprints, per-slot action hashes, and 5s measurement records.
2. `effects.json`: Statistical comparison matrix with mean deltas, bootstrap CIs, and p-values.
3. `effects.csv`: Spreadsheet-ready comparison matrix.
4. `results.tex`: Auto-generated LaTeX macros for paper inclusion.

---

## 🔍 Revision Verification & Sensitivity Suite

### Trace-Level Sensitivity & 20,000 Bootstrap Draws (`revision_analysis.py`)
Computes stratified bootstrap resampling ($B = 20,000$ draws, seed 466) across the 3 traffic profiles (`steady_bursty`, `flash_crowd`, `volatile_dpp`). Computes Holm-Bonferroni adjusted p-values with and without neural arm deduplication.

### Neural Proposal Disparity vs. Guard Convergence (`verify_neural_guard.py`)
Proves that while DQN and Two-Agent IQL propose different raw actions in 14.2% of control slots, the deterministic safety guard maps both to identical effective actions. Evaluates proposal vs effective action digests across 21,600 slots.

### Fixed Governor Schedule Equivalence (`verify_fixed_governor.py`)
Replaces the dynamic LLM multi-agent governor on S5 with a constant Option "A" schedule. Confirms 100% cryptographic match on `effective_actions_sha256` and identical 5s window metrics across all 12 test seeds.

### Bit-for-Bit Manuscript Reproduction Verifier (`verify_manuscript_reproduction.py`)
Validates reproduced benchmark files against canonical reference outputs in `paper/comparison/`:
```powershell
python selfx/eval/verify_manuscript_reproduction.py paper/comparison/runs.json reproduced/full/runs.json
```

---

## 📊 Vector Plotting & Publication Asset Generators

### Manuscript Figures & Tables (`plot_manuscript.py`, `plot_expanded_paper.py`)
Generates high-resolution vector PDFs and LaTeX tables:
- `paper_architecture.pdf`: Two-timescale decoupled control architecture.
- `paper_delay_effects.pdf`: Paired delay difference forest plot with 95% CIs.
- `paper_delay_loss.pdf`: Delay vs. packet loss trade-off scatter.
- `paper_window_traces.pdf`: 180s continuous delay and queue traces.
- `manuscript_table.tex`: The primary 14-controller comparison table.
- `expanded_profiles.tex`: Profile-by-profile performance breakdown.

### Supplementary 13-Plot Comparison Atlas (`plot_audited_comparison.py`)
Generates `paper/comparison/SELF_X_Algorithm_Comparison.pdf`, containing 13 comprehensive diagnostic plots comparing all 14 controllers.

---

## 📦 Data Schemas, Validation & Serialization (`result_schema.py`, `result_writer.py`)

- **Strict Pydantic / Dataclass Models**: Validates run metadata, metric time series, and execution traces.
- **Fail-Closed Quarantining**: Any run with corrupted or truncated JSONL records is flagged with `HTTP 422 Unprocessable Content` in the web bridge, protecting analytics from incomplete datasets.

---

## 🚀 Operator Verification & Execution Runbook

Run the complete evaluation suite from the repository root:

```powershell
# 1. Execute unit test discovery
python -m unittest discover -s Web/tests -v
python -m pytest --basetemp .pytest-tmp selfx/tests/test_audited_comparison.py selfx/tests/test_pipeline_study.py

# 2. Run deterministic neural baseline & guard check
python selfx/eval/verify_neural_guard.py

# 3. Run fixed governor check
python selfx/eval/verify_fixed_governor.py

# 4. Run trace-level bootstrap sensitivity
python selfx/eval/revision_analysis.py

# 5. Rebuild manuscript figures and tables
python selfx/eval/plot_manuscript.py
python selfx/eval/plot_expanded_paper.py
```

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
