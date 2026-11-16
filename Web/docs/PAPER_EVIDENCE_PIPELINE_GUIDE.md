# Earlier SELF-X pipeline study

> **Dashboard and REST API guide for the archived pipeline study**  
> *Module: `Web/pipeline.html` | Backend Route: `/api/pipeline/*` | Data Root: `selfx/output/pipeline_study/`*  
> *Component Guide — EC466: Software Defined Networks | Team ID: SDN_07 | IIIT Dharwad*  
> *Document Version: 2.4.0-Production*

---

## 📌 Table of Contents
1. [Study scope](#-study-scope)
2. [Dashboard Architecture (`pipeline.html`)](#dashboard-architecture-pipelinehtml)
   - [Zero-Framework Semantic DOM Engine](#zero-framework-semantic-dom-engine)
   - [Responsive Theme Support & CSS Design Tokens](#responsive-theme-support--css-design-tokens)
3. [REST API Pipeline Endpoints (`/api/pipeline/*`)](#rest-api-pipeline-endpoints-apipipeline)
   - [GET /api/pipeline/summary](#get-apipipelinesummary)
   - [GET /api/pipeline/runs](#get-apipipelineruns)
   - [GET /api/pipeline/significance](#get-apipipelinesignificance)
   - [GET /api/pipeline/vsweep](#get-apipipelinevsweep)
   - [GET /api/pipeline/transfer](#get-apipipelinetransfer)
   - [GET /api/pipeline/adapter](#get-apipipelineadapter)
4. [Security & Path Sanitization (Allowlist Isolation)](#security--path-sanitization-allowlist-isolation)
5. [Visual Presentation Components](#visual-presentation-components)
   - [Meta-Telemetry Chips Banner](#meta-telemetry-chips-banner)
   - [Headline Metric Cards with Dynamic Delta Offsets](#headline-metric-cards-with-dynamic-delta-offsets)
   - [Staged Ablation Table with Relative Proportional Bars](#staged-ablation-table-with-relative-proportional-bars)
   - [Control-Plane Decision Latency Breakdown](#control-plane-decision-latency-breakdown)
   - [Baseline Comparison Matrix](#baseline-comparison-matrix)
   - [Embedded Publication Figure Grid](#embedded-publication-figure-grid)
6. [Operator & Troubleshooting Playbook](#operator--troubleshooting-playbook)

---

## 🏛️ Study scope

This dashboard loads the earlier staged pipeline study from
`selfx/output/pipeline_study/` through the read-only `/api/pipeline/*` routes.
For the current manuscript's results, open the
[audited comparison](../../paper/COMPARISON.md) or follow
[REPRODUCE.md](../../REPRODUCE.md). The audited experiment uses a different
setup and its own evidence under `paper/comparison/`.

---

## 🎨 Dashboard Architecture (`pipeline.html`)

### Zero-Framework Semantic DOM Engine
The page is implemented as an ultra-lightweight, dependency-free HTML5/ES6 application:
- **Zero Third-Party JS**: Contains zero external JavaScript dependencies (no jQuery, React, Vue, or D3).
- **Asynchronous Lifecycle**: Fetches all evidence datasets concurrently using `Promise.all`:
  ```javascript
  const [summary, stats] = await Promise.all([get("summary"), get("significance")]);
  render(summary, stats);
  ```

### Responsive Theme Support & CSS Design Tokens
The design utilizes standard CSS custom properties with automatic dark/light theme switching:
```css
:root {
  --surface: #fcfcfb; --panel: #ffffff; --ink: #0b0b0b; --ink2: #52514e;
  --line: #e3e2de; --blue: #2a78d6; --aqua: #1baf7a; --red: #e34948;
  --ramp0: #c3dbf5; --ramp4: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surface: #1a1a19; --panel: #232322; --ink: #f0efec;
    --line: #34342f; --blue: #3987e5; --aqua: #199e70;
  }
}
```

---

## 📡 REST API Pipeline Endpoints (`/api/pipeline/*`)

All pipeline endpoints are served by `handle_pipeline()` in `Web/server.py`.

### 1. GET /api/pipeline/summary
Retrieves the aggregated statistical measures across all configurations evaluated in the pipeline study.

- **Data File**: `selfx/output/pipeline_study/pipeline_summary.json`
- **Response**: `200 OK`
```json
{
  "seeds": [1000, 1001, 1002, 1003, 1004],
  "windows_per_run": 60,
  "window_sec": 3.0,
  "tau_sec": 0.1,
  "governance_epoch_windows": 10,
  "max_conservation_error_mbit": 1.2e-6,
  "llm": {
    "total_decisions": 360,
    "served_fraction": 1.0,
    "declared_fallbacks": 0
  },
  "stages": [
    {
      "configuration": "S0",
      "name": "Static Default",
      "mean_latency_ms": 34.82,
      "loss_pct": 8.12,
      "mean_queue_mbit": 0.412,
      "oracle_floor_loss_pct": 0.0
    },
    {
      "configuration": "S5",
      "name": "SELF-X Full Pipeline",
      "mean_latency_ms": 18.24,
      "loss_pct": 0.48,
      "mean_queue_mbit": 0.084,
      "mean_fast_decision_us": 14.2,
      "p99_fast_decision_us": 48.6
    }
  ]
}
```

---

### 2. GET /api/pipeline/runs
Provides granular, per-window metrics across every seed and window.

- **Data File**: `selfx/output/pipeline_study/pipeline_runs.json`
- **Response**: `200 OK`
```json
{
  "runs": [
    {
      "seed": 1000,
      "configuration": "S5",
      "windows": [
        {
          "window": 1,
          "offered_mbit": 28.4,
          "served_mbit": 28.4,
          "dropped_mbit": 0.0,
          "mean_latency_ms": 14.1,
          "queue_mbit": 0.04
        }
      ]
    }
  ]
}
```

---

### 3. GET /api/pipeline/significance
Serves paired statistical significance metrics, Wilcoxon signed-rank tests, and seed-level cluster bootstrap distributions.

- **Data File**: `selfx/output/pipeline_study/significance.json`
- **Bootstrap Method**: Cluster bootstrap resampling at the seed level ($N = 10,000$ draws), respecting serial correlation within each trace.
- **Response**: `200 OK`
```json
{
  "reference": "S5",
  "comparisons": {
    "S0": {
      "metric": "mean_latency_ms",
      "delta": -16.58,
      "cluster_bootstrap_ci95": [-17.42, -15.74],
      "t_statistic": 14.41,
      "p_value": 0.000042,
      "significant": true
    }
  }
}
```

---

### 4. GET /api/pipeline/vsweep
Retrieves parameter sweep metrics evaluating the Lyapunov trade-off parameter $V \in [0.1, 50.0]$.

- **Data File**: `selfx/output/pipeline_study/v_tradeoff.json`
- **Theoretical Basis**: $\Delta L(Q) + V \cdot g(t) \le B + V \cdot C - \epsilon \sum Q_i(t)$
- **Response**: `200 OK`
```json
{
  "v_sweep": [
    {"V": 0.1, "mean_delay_ms": 14.1, "mean_backlog_mbit": 0.042, "rule_churn_per_min": 42},
    {"V": 1.0, "mean_delay_ms": 16.4, "mean_backlog_mbit": 0.065, "rule_churn_per_min": 28},
    {"V": 10.0, "mean_delay_ms": 18.2, "mean_backlog_mbit": 0.084, "rule_churn_per_min": 14},
    {"V": 50.0, "mean_delay_ms": 24.8, "mean_backlog_mbit": 0.142, "rule_churn_per_min": 5}
  ]
}
```

---

### 5. GET /api/pipeline/transfer
Provides zero-shot out-of-distribution evaluation results when the frozen policy backend is tested on unseen topologies and unobserved burst distributions.

- **Data File**: `selfx/output/pipeline_study/transfer.json`
- **Response**: `200 OK`
```json
{
  "held_out_profile": "volatile_dpp_stress",
  "held_out_topology": "unseen_mesh_6sw",
  "zero_shot_compliance_rate": 0.998,
  "mean_delay_ms": 21.4,
  "sla_violation_rate": 0.002
}
```

---

### 6. GET /api/pipeline/adapter
Serves the parameter-efficient adaptation training report for the SmolLM2-135M LoRA adapter.

- **Data File**: `selfx/output/pipeline_study/adapter_report.json`
- **Response**: `200 OK`
```json
{
  "base_model": "HuggingFaceTB/SmolLM2-135M",
  "rank": 8,
  "alpha": 16,
  "trainable_parameters": 460800,
  "training_loss_final": 0.142,
  "validation_loss_final": 0.168,
  "promotion_gate_passed": true
}
```

---

## 🔒 Security & Path Sanitization (Allowlist Isolation)

Unlike dynamic REST endpoints that accept arbitrary path variables, `handle_pipeline` uses a **strict allowlist lookup dictionary**:

```python
PIPELINE_FILES = {
    "summary": PIPELINE_DIR / "pipeline_summary.json",
    "runs": PIPELINE_DIR / "pipeline_runs.json",
    "significance": PIPELINE_DIR / "significance.json",
    "vsweep": PIPELINE_DIR / "v_tradeoff.json",
    "transfer": PIPELINE_DIR / "transfer.json",
    "adapter": PIPELINE_DIR / "adapter_report.json",
}

def handle_pipeline(self, name):
    target = PIPELINE_FILES.get(name)
    if target is None:
        self.send_json(404, {
            "error": "unknown pipeline resource",
            "available": sorted(PIPELINE_FILES)
        })
        return
```

### Security Benefits:
- **Zero CWE-22 Path Traversal Vulnerability**: Input string is matched against dictionary keys; no file path concatenation occurs.
- **Fail-Closed Hinting**: If a requested evidence file has not been produced yet, the server returns `HTTP 404` with a remediation command hint (`run scripts/run_all.ps1`).

---

## 📊 Visual Presentation Components

### Meta-Telemetry Chips Banner
Renders 8 real-time verification chips across the top:
- Seed Count
- Window Count & Duration
- Time Slot Resolution ($\tau = 100\,\text{ms}$)
- Governance Epoch Interval ($30\,\text{s}$)
- Model Decisions Served Fraction ($100.0\%$)
- Declared Fallbacks ($0$)
- Fluid Conservation Error ($< 10^{-6}\,\text{Mbit}$)

### Headline Metric Cards with Dynamic Delta Offsets
Displays 5 core performance cards comparing Full Pipeline ($S_5$) against Static Default ($S_0$):
1. **Mean Delay**: $18.2\,\text{ms}$ ($-47.6\%$ below static)
2. **Packet Loss**: $0.5\%$ ($-94.1\%$ below static)
3. **Mean Backlog**: $0.084\,\text{Mbit}$ ($-79.6\%$ below static)
4. **Fast-Loop Decision**: $14.2\,\mu\text{s}$ (P99: $48.6\,\mu\text{s}$)
5. **Irreducible Loss Floor**: $0.0\%$

### Staged Ablation Table with Relative Proportional Bars
Renders the six progressive ablation stages ($S_0 \to S_1 \to S_2 \to S_3 \to S_4 \to S_5$):
- Proportional CSS bar cells visually contrasting queue depth and latency.
- Highlights optimal row with `.best` class styling (emerald highlight).

### Embedded Publication Figure Grid
Renders the high-resolution vector figures published in the IEEE manuscript:
- `fig1_architecture.png`: Decoupled two-timescale control plane.
- `fig3_ablation.png`: 6-stage progressive ablation curves.
- `fig4_control_latency.png`: Decision latency vs period envelopes.
- `fig8_loss_decomposition.png`: Addressable vs floor loss.
- `fig6_v_tradeoff.png`: Lyapunov $V$-parameter sweep.
- `fig9_convergence.png`: Cumulative reward trajectory.

---

## 🛠️ Operator & Troubleshooting Playbook

### Error: `HTTP 404: pipeline summary not generated yet`
- **Root Cause**: The evaluation benchmark has not been run in `selfx/output/pipeline_study/`.
- **Remediation**:
  ```powershell
  python selfx/scripts/run_all.ps1
  ```

### Error: `HTTP 502: pipeline summary is malformed JSON`
- **Root Cause**: An experiment run was terminated unexpectedly during JSON serialisation.
- **Remediation**:
  1. Check disk integrity in `selfx/output/pipeline_study/`.
  2. Regenerate report: `python selfx/eval/run_pipeline_study.py --output selfx/output/pipeline_study`.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
