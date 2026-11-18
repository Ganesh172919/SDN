# SELF-X Reproduction & Multi-Platform Installation Guide

**Team SDN_07 · EC466 Software Defined Networks · Indian Institute of Information Technology Dharwad (IIIT Dharwad)**  
*Project: SELF-X — A Three-Timescale Decomposition for Language-Model-Governed Flow Control in Software-Defined Networks*

---

## 1. Multi-Platform Prerequisites & System Installation

This project is fully cross-platform and has been verified on **Linux (Ubuntu, Debian, Fedora, Arch)**, **macOS (Sonoma, Sequoia; Apple Silicon M1/M2/M3 & Intel x86-64)**, and **Windows 10 / 11 (PowerShell & WSL2)**.

### A. Installing Python 3.12

#### Linux (Ubuntu / Debian / Raspberry Pi OS):
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl build-essential
python3 --version
```

#### Linux (Fedora / RHEL):
```bash
sudo dnf install -y python3.12 python3-pip git curl gcc
python3 --version
```

#### Linux (Arch Linux):
```bash
sudo pacman -Syu --noconfirm python python-pip git curl base-devel
python --version
```

#### macOS (Homebrew):
```bash
# Install Homebrew if not already installed:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.12:
brew update
brew install python@3.12 git curl
python3.12 --version
```

#### Windows 10 / 11 (via Windows Package Manager winget or PowerShell):
```powershell
# Open Windows Terminal or PowerShell as Administrator:
winget install Python.Python.3.12
winget install Git.Git

# Verify installation:
python --version
git --version
```

---

### B. Installing Node.js (v20 LTS) & npm

#### Linux (Ubuntu / Debian):
```bash
# Using official NodeSource repository for Node.js v20 LTS:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify:
node -v
npm -v
```

#### Linux (Fedora):
```bash
sudo dnf module install -y nodejs:20
node -v && npm -v
```

#### Linux (Arch Linux):
```bash
sudo pacman -S --noconfirm nodejs npm
node -v && npm -v
```

#### macOS (Homebrew):
```bash
brew install node@20
node -v
npm -v
```

#### Windows 10 / 11 (winget):
```powershell
winget install OpenJS.NodeJS.LTS
node -v
npm -v
```

---

### C. Installing Astral `uv` (Recommended Ultra-Fast Package Manager)

`uv` is the recommended Python package manager for SELF-X, installing environments in seconds with exact lockfile guarantees.

#### Linux & macOS:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
uv --version
```

#### Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

---

## 2. Setting Up the Repository & Virtual Environment

Clone the repository and set up the deterministic virtual environment:

### Linux / macOS:
```bash
git clone https://github.com/RAVIPRAKASH/SDN.git
cd SDN

# Sync virtual environment and dependencies using uv:
uv sync

# Or using standard python3.12 venv:
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell):
```powershell
git clone https://github.com/RAVIPRAKASH/SDN.git
cd SDN

# Sync virtual environment and dependencies using uv:
uv sync

# Or using standard python venv:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 3. Running the SELF-X Web Dashboard & Mission Control

The full-stack web dashboard provides interactive telemetry graphs, 14-controller benchmark visualizers, the automated Testing Studio, the Frontier Asian Models Hub, and the Codebase Explorer.

```bash
# Start the web server (listens on http://127.0.0.1:5000/):
uv run python Web/server.py

# Alternatively with active virtual environment:
python Web/server.py
```
Open your browser to: **`http://127.0.0.1:5000/`**

---

## 4. Running the Complete Automated Test Suite

Verify all unit, integration, safety gate, OpenFlow compiler, and multi-agent consensus tests:

```bash
# Run complete test suite (242 tests across control, safety, models, and web):
uv run pytest -q

# Run Web-specific endpoint and REST tests (94 tests):
uv run pytest Web/tests/ -q

# Run audited 14-controller comparison regression test:
uv run pytest selfx/tests/test_audited_comparison.py -q
```

---

## 5. Rerunning Manuscript Benchmarks & Generating Figures

To execute the audited 14-controller empirical benchmark evaluation and generate publication figures:

```bash
# 1. Run quick smoke evaluation:
uv run python selfx/eval/run_audited_comparison.py --smoke --output reproduced/smoke

# 2. Run full 14-controller audited evaluation (135,000 control slots):
uv run python selfx/eval/run_audited_comparison.py --output reproduced/full

# 3. Generate manuscript vector figures:
uv run python selfx/eval/plot_manuscript.py --effects reproduced/full/effects.json --output reproduced/full
uv run python selfx/eval/plot_expanded_paper.py --runs reproduced/full/runs.json --output reproduced/full

# 4. Verify reproduction against recorded runs:
uv run python selfx/eval/verify_manuscript_reproduction.py paper/comparison/runs.json reproduced/full/runs.json
```

---

## 6. Building Packaging & Course Submission Bundles

To generate sealed standalone submission archives with cryptographic checksums:

```bash
# Generate the complete IEEE submission bundle:
uv run python selfx/scripts/package_ieee_submission.py --dest submission

# Generate the Overleaf 1-click import bundle:
uv run python selfx/scripts/package_overleaf_full_bundle.py

# Verify SHA-256 cryptographic checksums across all 13 artifacts:
# On Linux/macOS:
cd submission && sha256sum -c SHA256SUMS.txt

# On Windows PowerShell:
Get-FileHash submission/* -Algorithm SHA256
```

---

## 7. Compiling the LaTeX IEEE Conference Paper

To compile the IEEE double-column conference paper from source:

```bash
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
# Compiled PDF generated at: paper/main.pdf (or root SELF_X_IEEE_Paper.pdf)
```

---

## 8. Academic Authors & Course Attribution

- **Course**: EC466 Software Defined Networks (Autumn 2026)
- **Institution**: Indian Institute of Information Technology Dharwad (IIIT Dharwad)
- **Team**: SDN_07
  - **Ganesh Reddy J** (`23bds024` · Dept. of Data Science & Artificial Intelligence)
  - **M Jagadeswar** (`23bds033` · Dept. of Data Science & Artificial Intelligence)
  - **Harsh Raj** (`23bds076` · Dept. of Data Science & Artificial Intelligence)
  - **C Sai Aravind** (`23bds075` · Dept. of Data Science & Artificial Intelligence)
  - **Koushik C** (`23bcs073` · Dept. of Computer Science & Engineering)
  - **Dhruv R Katti** (`23bec015` · Dept. of Electronics & Communication Engineering)


---

## 🚀 9. Comprehensive Master Execution Manual & Subsystem Runbook

> **Complete, Exhaustive, Copy-Pasteable Guide on How to Run Every Part of the SELF-X Autonomous SDN Control Platform**  
> *Follow these step-by-step instructions to run, test, benchmark, and verify every single subsystem on Windows, Linux, and macOS.*

```
========================================================================================================================
                                      MASTER SUBSYSTEM EXECUTION TAXONOMY
========================================================================================================================

  Subsystem                      Command / Entry Point                                Output Artifact / Endpoint
  ----------------------------------------------------------------------------------------------------------------------
  1. Web Mission Control         uv run python Web/server.py                          http://127.0.0.1:5000/
  2. Automated Web Test Suite    uv run pytest Web/tests/ -q                          94 Passed (100% Success)
  3. Complete Test Suite         uv run pytest -q                                     242 Passed (100% Success)
  4. 17-Section Diagnostic CLI   uv run pytest Web/tests/test_testing_studio.py -q    17 Verified Stages
  5. Asian Models Engine         uv run pytest Web/tests/test_asian_models.py -q      MLA & Reasoning Tests
  6. Multi-Agent Debate Loop     uv run pytest Web/tests/test_aqm_int_and_debate.py   Consensus Ratified
  7. Offline LoRA Adaptation     uv run python -m agent.self_improvement run          .models/candidate_checkpoint/
  8. 14-Controller Benchmarks    uv run python selfx/eval/run_audited_comparison.py   output/benchmarks/v4/metrics.csv
  9. Manuscript Plotters         uv run python selfx/eval/plot_manuscript.py          reproduced/figures/*.pdf
  10. Submission Package Build   uv run python selfx/scripts/package_ieee_submission.py submission/SELF_X_Submission.zip
  11. LaTeX Paper Compilation    cd paper && latexmk -pdf main.tex                    paper/main.pdf
========================================================================================================================
```

---

### A. Subsystem 1: Running the Production Web Dashboard & Mission Control

The central monitoring, verification, and interactive control interface is hosted at `http://127.0.0.1:5000/`.

#### Step 1: Start the Server
From the repository root:
```powershell
# Windows PowerShell:
uv run python Web/server.py

# Linux / macOS:
uv run python Web/server.py
```
*Expected Terminal Output:*
```
======================================================================
  SELF-X Production Web Platform & Telemetry Bridge
  Listening on http://127.0.0.1:5000/
  Multi-Threaded Concurrency: socketserver.ThreadingTCPServer
  Authentication: PBKDF2-HMAC-SHA256 (4 RBAC Roles)
  Theme: Pure White (#ffffff) / High Contrast (#0f172a)
======================================================================
```

#### Step 2: Open in Your Web Browser
Navigate to **`http://127.0.0.1:5000/`** in Google Chrome, Microsoft Edge, Mozilla Firefox, or Safari.

#### Step 3: Authenticate with Built-in Demo Credentials
Click the **User Profile** icon in the top-right header to open the authentication modal:
- **Admin Role** (`Full Controller Access & Chaos Studio`): Username `admin` | Password `admin` (or click `Demo Admin`)
- **Operator Role** (`Network Operations Lead`): Username `operator` | Password `operator` (or click `Demo Operator`)
- **Researcher Role** (`SDN Research Fellow`): Username `researcher` | Password `researcher` (or click `Demo Researcher`)
- **Auditor Role** (`Academic Auditor`): Username `auditor` | Password `auditor` (or click `Demo Auditor`)

---

### B. Subsystem 2: Running the 17-Section Testing Studio Diagnostics

The Testing Studio provides one-click and CLI execution of 17 hardware-in-the-loop and control plane checks.

#### Method 1: Web Interface (Visual Inspection)
1. In `http://127.0.0.1:5000/`, click **Testing Studio** in the Floating Quick Navigation Dock (`#tab-studio`).
2. Scroll to Section 1 and click the **Run Complete 17-Section Diagnostic Suite** button.
3. Observe all 17 diagnostic sections execute sequentially with green **VERIFIED** / **PASS** indicators:
   - Section 01: Physical Switch Handshake & Port Status
   - Section 02: OpenFlow 1.3 Telemetry Ingestion Vector
   - Section 03: Fast Lyapunov DPP Solver (14.2 µs Decision)
   - Section 04: Mid-Level LoRA Policy Head Preference Inference
   - Section 05: Slow-Loop Multi-Agent Consensus Adjudication
   - Section 06: Deterministic Fail-Closed Safety Verification (100/100)
   - Section 07: 4-Phase Chaos Matrix (Link Drop, Flap, Mutation, Microburst)
   - Section 08: Dynamic Link Impairment Matrix with Real-Time Detour Routing
   - Section 09: 14-Controller Automated Comparative Benchmark Runner
   - Section 10: Carrier-Grade SLA Compliance Auditor (Score: 99.88%)
   - Section 11: Real-Time Wire Deep Packet Inspection (VLAN 100, DSCP EF-46)
   - Section 12: Closed-Loop Autonomous Healing Watchdog (MTTR: 3.95 ms)
   - Section 13: Coupled Dual-Queue ECN/DCTCP & CoDel AQM Marking
   - Section 14: P4 In-Band Network Telemetry (INT) Metadata Dissector
   - Section 15: Hardware OpenFlow 1.3 TCAM Flow Table Utilization Profiler
   - Section 16: Cryptographic Control Plane Attestation (HMAC-SHA256)
   - Section 17: Multi-Queue Deficit Round Robin (DRR) Hardware Scheduler

#### Method 2: Command-Line CLI Execution
```bash
# Run Testing Studio automated validation test:
uv run pytest Web/tests/test_testing_studio.py -v

# Run Chaos Matrix & Impairment tests:
uv run pytest Web/tests/test_studio_chaos_matrix.py Web/tests/test_arena_and_impairment.py -v

# Run Wire DPI, Healing Watchdog, AQM & P4 INT tests:
uv run pytest Web/tests/test_dpi_and_healing.py Web/tests/test_aqm_int_and_debate.py -v
```

---

### C. Subsystem 3: Querying Frontier Asian Foundation Models & MLA

#### Method 1: Web Interface (Visual Inspection)
1. Click **Asian Models** in the Floating Navigation Dock (`#tab-asian-models`).
2. Under Section 5 (Reasoning Trace), click **Inspect Verifiable Reasoning Trace**:
   - Inspect DeepSeek-R1's 4-phase reasoning trace on fluid state, Lyapunov drift, meter formulation, and formal safety verification.
   - Inspect the **Compiled Verified Policy Delta**: $\Delta V = -2.5$, Target Path $s1 	o s3 	o s4$, Ingress Meter $7.5\,	ext{Mbps}$.
3. Under Section 6 (Multi-Agent Debate), click **Run Multi-Agent Consensus Debate**:
   - Inspect the real-time dialectic argument exchange between DeepSeek-R1 (Backlog), Qwen 2.5 72B (Throughput), and DeepSeek-V3 (Referee).
4. Under Section 7 (Flow-Mod Compiler), click **Generate & Compile Flow-Mod**:
   - Inspect operator natural language intent parsing into wire-compliant Ryu `ofctl_rest` JSON.

#### Method 2: Command-Line CLI Execution
```bash
# Verify Asian Models OpenRouter client & MLA equations:
uv run pytest Web/tests/test_asian_models.py -v

# Verify 4-way parallel model comparator:
uv run pytest Web/tests/test_asian_compare.py -v

# Verify Flow-Mod Compiler:
uv run pytest Web/tests/test_flow_mod.py -v
```

---

### D. Subsystem 4: Running the Offline Self-Improvement LoRA Adaptation

To train and evaluate a new parameter-efficient LoRA adapter on curated network observation replays:

```bash
# 1. Navigate to the selfx module:
cd selfx

# 2. Run the automated offline self-improvement pipeline:
uv run python -m agent.self_improvement run --output output/self_improvement/run_01 --steps 120 --cycles 48

# 3. Verify weight attribution and promotion gate:
uv run pytest tests/test_self_improvement.py -v
```
*Expected Outcomes:*
- Curates training episodes with reward $r \ge 0.00$.
- Trains LoRA matrices on `q_proj` and `v_proj` using PyTorch on CPU (zero GPU mandate).
- Replays candidate adapter across 4 stress workloads (Flash Crowd, Overload, Shift, Volatile).
- Verifies $\Delta r \ge 0.00$, zero discard violations, and CPU decision latency $\le 5.0\,	ext{ms}$.
- Atomically promotes candidate weights to `.models/` with SHA-256 manifest.

---

### E. Subsystem 5: Executing the 14-Controller Empirical Benchmark Suite

To reproduce the complete 135,000-window empirical evaluation comparing all 14 controllers:

```bash
# 1. Quick smoke test across all 14 controllers (evaluates seed 1740):
uv run python selfx/eval/run_audited_comparison.py --smoke --output reproduced/smoke

# 2. Full 14-controller audited evaluation (10 seeds, 8 scenarios, 135,000 slots):
uv run python selfx/eval/run_audited_comparison.py --output reproduced/full

# 3. Plot publication-grade vector figures:
uv run python selfx/eval/plot_manuscript.py --effects reproduced/full/effects.json --output reproduced/figures
uv run python selfx/eval/plot_expanded_paper.py --runs reproduced/full/runs.json --output reproduced/figures
```

---

### F. Subsystem 6: Compiling the Camera-Ready IEEE Research Paper

To build the double-column IEEE conference paper from LaTeX source:

```bash
# Change to paper directory and compile with latexmk:
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

# Output PDF generated at:
# paper/main.pdf
# Also synchronized to root: SELF_X_IEEE_Paper.pdf
```

---

### G. Subsystem 7: Packaging & Validating Submission Bundles

To generate the sealed course and conference submission archives with cryptographic checksums:

```bash
# 1. Package the complete IEEE submission bundle:
uv run python selfx/scripts/package_ieee_submission.py --dest submission

# 2. Package the Overleaf 1-click import bundle:
uv run python selfx/scripts/package_overleaf_full_bundle.py

# 3. Verify SHA-256 cryptographic digests across all artifacts:
# On Windows PowerShell:
Get-FileHash submission/* -Algorithm SHA256

# On Linux / macOS:
cd submission && sha256sum -c SHA256SUMS.txt
```

---

### H. Subsystem 8: Running All Automated Pytest Suites

```bash
# 1. Complete test suite (242 tests across control, safety, models, and web):
uv run pytest -q

# 2. Web server, REST API, Testing Studio, Auth, and Asian Models (94 tests):
uv run pytest Web/tests/ -q

# 3. Control plane, Lyapunov DPP, and two-timescale scheduler (148 tests):
uv run pytest selfx/tests/ -q
```
*Expected Result:*
$$\mathbf{100\%	ext{ Pass Rate Across All Suites}}$$

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | Indian Institute of Information Technology Dharwad (IIIT Dharwad)*
