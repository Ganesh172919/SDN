# SELF-X Public Dashboard & REST Bridge: Complete API Reference Manual

> **Production-Grade Standard-Library REST Bridge Specification**  
> *Module: `Web/server.py` | Protocol: HTTP/1.1 | Encoding: UTF-8 / JSON*  
> *Target System: SELF-X Autonomous SDN Control Platform | IIIT Dharwad — Team SDN_07*  
> *Current Version: 2.4.0-Production | Concurrency: ThreadingTCPServer*

---

## 📌 Table of Contents
1. [Architectural Overview & Security Invariants](#architectural-overview--security-invariants)
2. [Global Headers & Error Response Contracts](#global-headers--error-response-contracts)
3. [Live Control Plane & Telemetry Endpoints](#live-control-plane--telemetry-endpoints)
   - [GET /api/status](#get-apistatus)
   - [GET /api/memory](#get-apimemory)
   - [GET /api/ablation](#get-apiablation)
4. [Algorithm Comparison Studio Endpoints](#algorithm-comparison-studio-endpoints)
   - [GET /api/comparison/configs](#get-apicomparisonconfigs)
   - [GET /api/comparison/effects](#get-apicomparisoneffects)
   - [GET /api/comparison/runs](#get-apicomparisonruns)
5. [Multi-Topology & Workload Studio Endpoints](#multi-topology--workload-studio-endpoints)
   - [GET /api/topologies](#get-apitopologies)
   - [GET /api/topologies/{topology_id}](#get-apitopologiestopology_id)
   - [GET /api/traffic/schedules](#get-apitrafficschedules)
   - [GET /api/traffic/schedules/{profile}](#get-apitrafficschedulesprofile)
6. [Formal Theory & Advanced Analytics Endpoints](#formal-theory--advanced-analytics-endpoints)
   - [GET /api/analytics/dpp](#get-apianalyticsdpp)
   - [GET /api/analytics/statistics](#get-apianalyticsstatistics)
   - [GET /api/analytics/lora](#get-apianalyticslora)
7. [Paper Evidence & Pipeline Study Endpoints](#paper-evidence--pipeline-study-endpoints)
   - [GET /api/pipeline/summary](#get-apipipelinesummary)
   - [GET /api/pipeline/runs](#get-apipipelineruns)
   - [GET /api/pipeline/significance](#get-apipipelinesignificance)
   - [GET /api/pipeline/vsweep](#get-apipipelinevsweep)
   - [GET /api/pipeline/transfer](#get-apipipelinetransfer)
   - [GET /api/pipeline/adapter](#get-apipipelineadapter)
8. [Validated Benchmark Archive Endpoints](#validated-benchmark-archive-endpoints)
   - [GET /api/results](#get-apiresults)
   - [GET /api/results/{run_id}/summary](#get-apiresultsrun_idsummary)
   - [GET /api/results/{run_id}/metrics](#get-apiresultsrun_idmetrics)
   - [GET /api/results/{run_id}/trace](#get-apiresultsrun_idtrace)
   - [GET /api/results/compare](#get-apiresultscompare)
9. [Disabled Mutation Endpoints (Fail-Closed)](#disabled-mutation-endpoints-fail-closed)
   - [POST /api/action/reroute](#post-apiactionreroute)
   - [POST /api/action/rate_limit](#post-apiactionrate_limit)
   - [ANY /api/ryu/*](#any-apiryu)
10. [User Authentication & Role-Based Access Control (RBAC)](#user-authentication--role-based-access-control-rbac)
   - [POST /api/auth/register](#post-apiauthregister)
   - [POST /api/auth/login](#post-apiauthlogin)
   - [GET /api/auth/me](#get-apiauthme)
   - [POST /api/auth/logout](#post-apiauthlogout)
   - [GET /api/auth/status](#get-apiauthstatus)
11. [Interactive Testing Studio & Diagnostic Endpoints](#interactive-testing-studio--diagnostic-endpoints)
   - [POST /api/studio/verify](#post-apistudioverify)
   - [POST /api/studio/traffic-stress](#post-apistudiotraffic-stress)
   - [POST /api/studio/chaos-matrix](#post-apistudiochaos-matrix)
   - [POST /api/studio/flow-mod/inject](#post-apistudioflow-modinject)
   - [GET /api/studio/flow-mod/rules](#get-apistudioflow-modrules)
   - [POST /api/studio/lyapunov-tune](#post-apistudiolyapunov-tune)
   - [GET /api/studio/export-report](#get-apistudioexport-report)
   - [GET /api/studio/telemetry-stream](#get-apistudiotelemetry-stream)
   - [GET /api/studio/link-impairment/status](#get-apistudiolink-impairmentstatus)
   - [POST /api/studio/link-impairment/set](#post-apistudiolink-impairmentset)
   - [POST /api/studio/link-impairment/reset](#post-apistudiolink-impairmentreset)
   - [POST /api/studio/benchmark-run](#post-apistudiobenchmark-run)
   - [GET /api/studio/sla-audit](#get-apistudiosla-audit)
   - [POST /api/studio/flow-mod/flush](#post-apistudioflow-modflush)
   - [POST /api/studio/flow-mod/delete](#post-apistudioflow-moddelete)
12. [Frontier Asian Foundation Models Hub Endpoints](#frontier-asian-foundation-models-hub-endpoints)
   - [GET /api/asian-models/catalog](#get-apiasian-modelscatalog)
   - [POST /api/asian-models/query](#post-apiasian-modelsquery)
   - [GET /api/asian-models/benchmark](#get-apiasian-modelsbenchmark)
   - [POST /api/asian-models/arena](#post-apiasian-modelsarena)
   - [POST /api/asian-models/mla-calculator](#post-apiasian-modelsmla-calculator)
   - [POST /api/asian-models/consensus](#post-apiasian-modelsconsensus)

---

## 🔒 Architectural Overview & Security Invariants

The SELF-X web service is designed as an immutable, zero-privilege REST bridge. It serves live telemetry, theoretical validation data, and historical benchmark artifacts directly from local storage and upstream SDN controllers without executing dangerous mutations or requiring unverified runtime dependencies.

### Security Guarantees
1. **Zero-Privilege Read-Only Safety**: All datapath mutation requests (`POST /api/action/*`, `POST /api/ryu/*`) are intercepted by the security gate and fail-closed with `HTTP 409 Conflict`. No arbitrary flow modifications or meter configurations can be injected via the public dashboard.
2. **Directory Traversal Defense (Defense-in-Depth)**:
   - Path parameters (`topology_id`, `profile`, `run_id`) are validated against strict whitelisting regular expressions:
     - Resource IDs: `^[A-Za-z0-9_-]{1,64}$`
     - Run IDs: `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`
   - Target filesystem paths are fully resolved with `.resolve()` and checked against base directories using `os.path.commonpath` or `.is_relative_to()` to strictly prevent escaping the sandboxed result trees.
3. **MIME-Type & Frame Isolation**:
   - Every HTTP response automatically issues hardened browser security headers to eliminate Clickjacking, MIME confusion, and speculative side-channel attacks.

---

## 🌐 Global Headers & Error Response Contracts

### Standard Security Headers Emitted
All HTTP responses include the following headers:
```http
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: same-origin
Content-Type: application/json; charset=utf-8
```

### Standard Error Payloads

#### 400 Bad Request
Returned when input parameters violate formatting regexes or query string parameters are invalid:
```json
{
  "error": "invalid_resource_name",
  "detail": "Resource identifier must match ^[A-Za-z0-9_-]{1,64}$"
}
```

#### 403 Forbidden
Returned if a path attempts to escape bounded storage boundaries:
```json
{
  "error": "access_denied",
  "detail": "Path resolution outside bounded directory."
}
```

#### 404 Not Found
Returned when the requested resource, run record, or pre-recorded profile does not exist:
```json
{
  "error": "not_found",
  "detail": "Topology 'unknown_mesh' not found in selfx/output/topologies/"
}
```

#### 409 Conflict
Returned when attempting to invoke disabled datapath modification actions:
```json
{
  "success": false,
  "error": "network_control_disabled",
  "message": "Network mutation actions are disabled on this public dashboard (reroute).",
  "mode": "read_only"
}
```

#### 422 Unprocessable Content
Returned when an experiment result file is corrupted, malformed, or fails strict Pydantic/dataclass schema verification:
```json
{
  "error": "corrupted_run",
  "details": "Schema validation failed: missing required field 'mean_latency_ms'"
}
```

---

## 📡 Live Control Plane & Telemetry Endpoints

### GET /api/status
Performs an active health check on the dashboard server and probes the upstream Ryu SDN controller (`http://127.0.0.1:8080/stats/switches` with a 1.2s timeout).

- **Method**: `GET`
- **Path**: `/api/status`
- **Query Parameters**: None
- **Response**: `200 OK`
```json
{
  "status": "online",
  "mode": "read_only",
  "server_time": 1731580231.42,
  "ryu_controller": "connected",
  "connected_switches": [
    "0000000000000001",
    "0000000000000002",
    "0000000000000003",
    "0000000000000004"
  ],
  "switch_count": 4,
  "capabilities": {
    "live_polling": true,
    "fluid_datapath": true,
    "ablation_comparison": true,
    "formal_analytics": true
  }
}
```
- **CLI Example**:
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/status" -Method GET
```
```bash
curl -s http://localhost:5000/api/status | jq .
```

---

### GET /api/memory
Retrieves the episodic reflection memory log produced by the slow-loop governor (`agent_memory.json`).

- **Method**: `GET`
- **Path**: `/api/memory`
- **Query Parameters**: None
- **Response**: `200 OK`
```json
{
  "count": 30,
  "retrieval_strategy": "stratified_caliper",
  "caliper_radius": 0.15,
  "entries": [
    {
      "cycle": 1,
      "traffic_state": {
        "ingress_kbps": 14200.0,
        "queue_occupancy": 38,
        "packet_loss_rate": 0.042
      },
      "action_taken": "reroute_flow_h2_to_path2",
      "delta_latency_ms": -18.4,
      "reward": 0.118,
      "reflection": "Primary path bottleneck mitigated. Latency dropped within target SLA."
    }
  ]
}
```

---

### GET /api/ablation
Serves live statistical comparison rows across evaluation runs A0 (Static Default), A1 (Reactive Reflexion), and A2 (Parametric Adaptive).

- **Method**: `GET`
- **Path**: `/api/ablation`
- **Response**: `200 OK`
```json
{
  "headers": ["stage", "description", "mean_delay_ms", "goodput_mbps", "loss_pct", "p95_delay_ms", "composite_reward"],
  "rows": [
    ["A0", "Static Baseline (No Adaptation)", 34.82, 7.84, 8.12, 58.40, 0.421],
    ["A1", "Verbal Reflection (Fast Loop)", 26.15, 8.91, 3.40, 42.10, 0.684],
    ["A2", "Full SELF-X (Two-Timescale + LoRA)", 18.24, 9.68, 0.48, 24.30, 0.912]
  ]
}
```

---

## 📊 Algorithm Comparison Studio Endpoints

### GET /api/comparison/configs
Returns the registry of all 14 evaluated SDN control architectures evaluated across the empirical study.

- **Method**: `GET`
- **Path**: `/api/comparison/configs`
- **Response**: `200 OK`
```json
{
  "configs": [
    {
      "id": "S0",
      "name": "Static Default",
      "family": "Baseline",
      "mechanism": "Single shortest path (ECMP hash), zero dynamic adaptation",
      "color": "#9ca3af"
    },
    {
      "id": "S5",
      "name": "SELF-X (Complete)",
      "family": "Self-Improving",
      "mechanism": "Two-timescale Lyapunov DPP + LoRA fine-tuned specialist ensemble",
      "color": "#10b981"
    }
  ],
  "total": 14,
  "baseline_reference": "S0"
}
```

---

### GET /api/comparison/effects
Provides the complete statistical comparison matrix containing effect sizes, differences ($\Delta$), 95% bootstrap confidence intervals, and p-values computed against `S0` or between configurations.

- **Method**: `GET`
- **Path**: `/api/comparison/effects`
- **Data Source**: `paper/comparison/effects.json`
- **Response**: `200 OK`
```json
{
  "baseline": "S0",
  "comparisons": {
    "S5": {
      "name": "SELF-X (Complete)",
      "family": "Self-Improving",
      "delta_mean_delay_ms": -16.58,
      "delta_mean_delay_ci": [-17.42, -15.74],
      "delta_p95_delay_ms": -34.10,
      "delta_p95_delay_ci": [-36.20, -32.00],
      "delta_goodput_mbps": 1.84,
      "delta_goodput_ci": [1.68, 2.00],
      "delta_loss_pct": -7.64,
      "delta_loss_ci": [-8.20, -7.08],
      "delta_mean_queue": -22.40,
      "delta_mean_queue_ci": [-24.10, -20.70],
      "delta_reward": 0.491,
      "delta_reward_ci": [0.465, 0.517],
      "p_value_delay": 0.000042,
      "p_value_goodput": 0.000018,
      "significant": true
    }
  }
}
```

---

### GET /api/comparison/runs
Serves aligned per-window time series across matched random seeds (60 windows $\times$ 3 seconds = 180 seconds).

- **Method**: `GET`
- **Path**: `/api/comparison/runs`
- **Query Parameters**:
  - `configs` *(optional, string)*: Comma-separated list of controller IDs (e.g. `?configs=S0,S5`). Filters output to requested controllers.
  - `summary_only` *(optional, boolean)*: Set to `true` to omit the heavy per-window array and return only aggregate metrics.
- **Response**: `200 OK`
```json
{
  "total_runs": 14,
  "filtered_configs": ["S0", "S5"],
  "runs": {
    "S0": {
      "config_id": "S0",
      "name": "Static Default",
      "metrics_summary": {
        "mean_delay": 34.82,
        "mean_goodput": 7.84,
        "mean_loss": 8.12
      },
      "windows": [
        {"window": 1, "time_s": 3.0, "delay_ms": 12.4, "goodput_mbps": 9.8, "queue_depth": 4},
        {"window": 2, "time_s": 6.0, "delay_ms": 38.2, "goodput_mbps": 7.2, "queue_depth": 36}
      ]
    }
  }
}
```

---

## 🗺️ Multi-Topology & Workload Studio Endpoints

### GET /api/topologies
Lists all network fabrics available in the active network studio and testbed manifest directory (`selfx/output/topologies/`).

- **Method**: `GET`
- **Path**: `/api/topologies`
- **Response**: `200 OK`
```json
{
  "topologies": [
    {
      "id": "linear",
      "name": "Linear Tandem (4 Switches)",
      "switches": 4,
      "hosts": 8,
      "links": 3,
      "description": "Standard 4-switch pipeline with dual bottleneck paths between core nodes."
    },
    {
      "id": "leaf_spine",
      "name": "Leaf-Spine 2x4 Data Center Fabric",
      "switches": 6,
      "hosts": 8,
      "links": 8,
      "description": "2 Spine switches, 4 Leaf switches with full bisectional cross-connects."
    },
    {
      "id": "unseen_mesh",
      "name": "Augmented 6-Switch Mesh",
      "switches": 6,
      "hosts": 8,
      "links": 9,
      "description": "Arbitrary meshed topology used for out-of-distribution generalization testing."
    }
  ]
}
```

---

### GET /api/topologies/{topology_id}
Fetches the complete topology manifest containing switches, OpenFlow DPIDs, host addresses, interface port numbers, and physical link constraints.

- **Method**: `GET`
- **Path**: `/api/topologies/{topology_id}`
- **Path Parameters**:
  - `topology_id` *(string, required)*: Identifier matching `^[A-Za-z0-9_-]{1,64}$` (e.g. `linear`, `leaf_spine`, `unseen_mesh`).
- **Response Codes**:
  - `200 OK`: Manifest found and returned.
  - `400 Bad Request`: `topology_id` contains invalid characters or directory traversal syntax.
  - `404 Not Found`: Fabric manifest not found on disk.
- **Response**: `200 OK`
```json
{
  "topology_id": "leaf_spine",
  "name": "Leaf-Spine 2x4 DC Fabric",
  "switches": [
    {"id": "spine1", "dpid": "0000000000000101", "tier": "spine", "ports": [1, 2, 3, 4]},
    {"id": "spine2", "dpid": "0000000000000102", "tier": "spine", "ports": [1, 2, 3, 4]},
    {"id": "leaf1", "dpid": "0000000000000201", "tier": "leaf", "ports": [1, 2, 3, 4]}
  ],
  "hosts": [
    {"id": "h1", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "connected_switch": "leaf1", "port": 3}
  ],
  "links": [
    {
      "src": "spine1", "src_port": 1,
      "dst": "leaf1", "dst_port": 1,
      "capacity_mbps": 10.0,
      "delay_ms": 2.0,
      "loss_rate": 0.0
    }
  ]
}
```

---

### GET /api/traffic/schedules
Returns all pre-compiled deterministic traffic generation schedules available in `selfx/output/traffic/`.

- **Method**: `GET`
- **Path**: `/api/traffic/schedules`
- **Response**: `200 OK`
```json
{
  "schedules": [
    {
      "id": "flash_crowd",
      "name": "Flash Crowd Workload",
      "duration_s": 600,
      "flows": 8,
      "seed": 42,
      "description": "Sudden 14 Mbps elephant flow surge between h2 and h8 under high cross-traffic."
    },
    {
      "id": "steady_bursty",
      "name": "Steady Bursty Flow Mix",
      "duration_s": 600,
      "flows": 12,
      "seed": 42,
      "description": "Continuous background mice flows combined with periodic Poisson bursts."
    },
    {
      "id": "volatile_dpp",
      "name": "Volatile DPP Stress Workload",
      "duration_s": 600,
      "flows": 16,
      "seed": 42,
      "description": "Rapidly varying arrival rates designed to challenge Lyapunov drift minimization."
    }
  ]
}
```

---

### GET /api/traffic/schedules/{profile}
Serves the complete time-stamped packet and flow event sequence for a given workload profile.

- **Method**: `GET`
- **Path**: `/api/traffic/schedules/{profile}`
- **Path Parameters**:
  - `profile` *(string, required)*: Identifier matching `^[A-Za-z0-9_-]{1,64}$`.
- **Response**: `200 OK`
```json
{
  "profile": "flash_crowd",
  "seed": 42,
  "duration_s": 600,
  "event_count": 4,
  "events": [
    {
      "time_s": 0.0,
      "flow_id": "flow_mice_bg",
      "src": "h1",
      "dst": "h7",
      "rate_kbps": 4000.0,
      "protocol": "UDP",
      "type": "constant"
    },
    {
      "time_s": 30.0,
      "flow_id": "flow_elephant_surge",
      "src": "h2",
      "dst": "h8",
      "rate_kbps": 14000.0,
      "protocol": "UDP",
      "type": "burst"
    }
  ]
}
```

---

## 🧮 Formal Theory & Advanced Analytics Endpoints

### GET /api/analytics/dpp
Retrieves the mathematical proof verification records and parameter sweep results for the Lyapunov Drift-Plus-Penalty (DPP) control loop.

- **Method**: `GET`
- **Path**: `/api/analytics/dpp`
- **Mathematical Bound**:
  $$\limsup_{T \to \infty} \frac{1}{T} \sum_{t=0}^{T-1} \sum_{i} \mathbb{E}[Q_i(t)] \le \frac{B + V \cdot C_{\max}}{\epsilon}$$
- **Response**: `200 OK`
```json
{
  "acceptance_test": "PASSED",
  "evaluated_intervals": 3000,
  "compliance_rate": 1.0,
  "compliance_target": 0.95,
  "theoretical_bound": {
    "B_constant": 14.2,
    "epsilon_slack": 0.85,
    "V_parameter": 10.0,
    "C_max": 2.5,
    "upper_backlog_bound": 46.12
  },
  "empirical_metrics": {
    "max_observed_backlog": 39.4,
    "mean_observed_backlog": 18.2,
    "sla_violation_rate": 0.000
  },
  "v_sweep": [
    {"V": 0.1, "mean_delay_ms": 14.1, "mean_queue_pkts": 8.2, "tcam_churn": 42},
    {"V": 1.0, "mean_delay_ms": 16.4, "mean_queue_pkts": 12.5, "tcam_churn": 28},
    {"V": 10.0, "mean_delay_ms": 18.2, "mean_queue_pkts": 18.2, "tcam_churn": 14},
    {"V": 50.0, "mean_delay_ms": 24.8, "mean_queue_pkts": 31.0, "tcam_churn": 5}
  ]
}
```

---

### GET /api/analytics/statistics
Serves formal hypothesis testing verification results, comparing paired random seeds across controllers.

- **Method**: `GET`
- **Path**: `/api/analytics/statistics`
- **Response**: `200 OK`
```json
{
  "test_type": "Paired Two-Sample Student's t-Test",
  "sample_pairs": 10,
  "degrees_of_freedom": 9,
  "t_statistic": 14.412,
  "p_value": 3.84e-7,
  "hypothesis_rejected": true,
  "significance_alpha": 0.01,
  "effect_size": {
    "cohens_d": 4.557,
    "classification": "Huge (d > 2.0)",
    "mean_difference": 16.58,
    "std_difference": 3.64
  },
  "seed_pairs": [
    {"seed": 42, "static_delay": 35.1, "selfx_delay": 18.4, "delta": -16.7},
    {"seed": 100, "static_delay": 34.2, "selfx_delay": 17.9, "delta": -16.3},
    {"seed": 1940, "static_delay": 36.8, "selfx_delay": 19.1, "delta": -17.7}
  ]
}
```

---

### GET /api/analytics/lora
Provides model architecture parameters, low-rank decomposition properties, and the training step trajectory for the SmolLM2-135M policy backend.

- **Method**: `GET`
- **Path**: `/api/analytics/lora`
- **Response**: `200 OK`
```json
{
  "base_model": "HuggingFaceTB/SmolLM2-135M",
  "target_modules": ["q_proj", "v_proj"],
  "rank_r": 8,
  "alpha": 16,
  "dropout": 0.05,
  "total_parameters": 134500000,
  "trainable_parameters": 460800,
  "parameter_efficiency_pct": 0.342,
  "training_epochs": 3,
  "final_train_loss": 0.142,
  "final_val_loss": 0.168,
  "promotion_gate_passed": true,
  "training_loss_steps": [
    {"step": 10, "loss": 2.451, "gradient_norm": 1.42},
    {"step": 50, "loss": 0.842, "gradient_norm": 0.68},
    {"step": 100, "loss": 0.312, "gradient_norm": 0.24},
    {"step": 200, "loss": 0.142, "gradient_norm": 0.09}
  ]
}
```

---

## 📑 Paper Evidence & Pipeline Study Endpoints

These endpoints read the earlier archived pipeline study. The audited paper uses the files served by `/api/comparison/*`.

| Endpoint | Data File | Description |
| :--- | :--- | :--- |
| `GET /api/pipeline/summary` | `pipeline_summary.json` | Aggregated statistical measures for all configurations. |
| `GET /api/pipeline/runs` | `pipeline_runs.json` | Granular per-window metrics for all runs. |
| `GET /api/pipeline/significance` | `significance.json` | Paired t-tests, Wilcoxon signed-rank, cluster bootstrap. |
| `GET /api/pipeline/vsweep` | `v_tradeoff.json` | Parameter $V$ sweep evaluating backlog vs queue stability. |
| `GET /api/pipeline/transfer` | `transfer.json` | Zero-shot generalization metrics on held-out topologies. |
| `GET /api/pipeline/adapter` | `adapter/training.json` | LoRA training curve, gradient metrics, and gate verdict. |

---

## 📦 Validated Benchmark Archive Endpoints

All run records in `/api/results/*` are subjected to strict schema checks. If an experiment folder has corrupted metadata or truncated JSONL files, it is quarantined and flagged with `422 Unprocessable Content`.

### GET /api/results
Returns the registry of all saved benchmark runs.
- **Method**: `GET`
- **Path**: `/api/results`
- **Response**: `200 OK`
```json
{
  "total": 3,
  "runs": [
    {
      "run_id": "a0-20261114T101237Z-6f7ed749",
      "stage": "A0",
      "created_at": "2026-11-14T10:12:37Z",
      "status": "completed",
      "summary": {
        "mean_latency_ms": 34.82,
        "throughput_mbps": 7.84,
        "packet_loss_rate": 0.0812
      }
    }
  ]
}
```

---

### GET /api/results/{run_id}/summary
Returns the statistical aggregate summary of a validated run.

- **Method**: `GET`
- **Path**: `/api/results/{run_id}/summary`
- **Path Parameters**:
  - `run_id` *(string, required)*: Matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.
- **Response**: `200 OK`
```json
{
  "run_id": "a2-20261114T101237Z-16c61392",
  "stage": "A2",
  "duration_s": 180,
  "mean_latency_ms": 18.24,
  "p95_latency_ms": 24.30,
  "throughput_mbps": 9.68,
  "packet_loss_rate": 0.0048,
  "composite_reward": 0.912,
  "verified_invariant_violations": 0
}
```

---

### GET /api/results/compare?run_ids=runA,runB
Compares two or more validated runs side-by-side.

- **Method**: `GET`
- **Path**: `/api/results/compare?run_ids={runA},{runB}`
- **Query Parameters**:
  - `run_ids` *(string, required)*: Comma-separated list of valid run IDs.
- **Response**: `200 OK`
```json
{
  "count": 2,
  "comparison": [
    {
      "metric": "Mean Latency (ms)",
      "a0-20261114T101237Z-6f7ed749": 34.82,
      "a2-20261114T101237Z-16c61392": 18.24,
      "delta": -16.58,
      "percentage_change": "-47.6%"
    },
    {
      "metric": "Packet Loss (%)",
      "a0-20261114T101237Z-6f7ed749": 8.12,
      "a2-20261114T101237Z-16c61392": 0.48,
      "delta": -7.64,
      "percentage_change": "-94.1%"
    }
  ]
}
```

---

## 🚫 Disabled Mutation Endpoints (Fail-Closed)

In accordance with safety invariant rules, network-mutating calls are unconditionally rejected.

### POST /api/action/reroute
- **Method**: `POST`
- **Path**: `/api/action/reroute`
- **Response**: `409 Conflict`
```json
{
  "success": false,
  "error": "network_control_disabled",
  "message": "Network mutation actions are disabled on this public dashboard (reroute).",
  "mode": "read_only"
}
```

### POST /api/action/rate_limit
- **Method**: `POST`
- **Path**: `/api/action/rate_limit`
- **Response**: `409 Conflict`
```json
{
  "success": false,
  "error": "network_control_disabled",
  "message": "Network mutation actions are disabled on this public dashboard (rate_limit).",
  "mode": "read_only"
}
```

### ANY /api/ryu/*
- **Method**: `ANY (POST, PUT, DELETE)`
- **Path**: `/api/ryu/*`
- **Response**: `409 Conflict`
```json
{
  "success": false,
  "error": "network_control_disabled",
  "message": "Network mutation actions are disabled on this public dashboard (ryu).",
  "mode": "read_only"
}
```

---

## 🔐 User Authentication & Role-Based Access Control (RBAC)

The authentication system employs PBKDF2-HMAC-SHA256 password hashing (100,000 iterations) and 24-hour cryptographic session tokens. Four operational roles are supported: `Admin`, `Operator`, `Researcher`, `Auditor`.

### POST /api/auth/register
- **Method**: `POST`
- **Path**: `/api/auth/register`
- **Body**:
  ```json
  {
    "username": "operator_iiit",
    "password": "SecurePassword123!",
    "email": "operator@iiitdwd.ac.in",
    "role": "operator"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "success": true,
    "token": "sess_f89a7b...",
    "user": {
      "username": "operator_iiit",
      "email": "operator@iiitdwd.ac.in",
      "role": "operator",
      "display_role": "NOC Lead"
    }
  }
  ```

### POST /api/auth/login
- **Method**: `POST`
- **Path**: `/api/auth/login`
- **Body**:
  ```json
  {
    "username": "operator_iiit",
    "password": "SecurePassword123!"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "token": "sess_f89a7b...",
    "user": { ... }
  }
  ```

### GET /api/auth/me
- **Method**: `GET`
- **Path**: `/api/auth/me`
- **Headers**: `Authorization: Bearer <session_token>`
- **Response**: `200 OK` Returns active profile and permissions, or Guest (`Read Only`).

### POST /api/auth/logout
- **Method**: `POST`
- **Path**: `/api/auth/logout`
- **Headers**: `Authorization: Bearer <session_token>`
- **Response**: `200 OK` Invalidates session token.

### GET /api/auth/status
- **Method**: `GET`
- **Path**: `/api/auth/status`
- **Response**: `200 OK` Returns system auth configuration, user count, and active session count.

---

## 🧪 Interactive Testing Studio & Diagnostic Endpoints

The Web Testing Studio provides a full-stack automated diagnostic verification pipeline, link impairment injection, traffic burst generators, formal safety validation, and comparative benchmark execution.

### POST /api/studio/verify
- **Method**: `POST`
- **Path**: `/api/studio/verify`
- **Response**: `200 OK`
  Executes the 6-stage end-to-end diagnostic pipeline:
  1. Physical Port & Controller Handshake
  2. OpenFlow 1.3 Telemetry Ingestion
  3. Fast DPP Lyapunov Solver (14.2 µs decision time)
  4. Mid-Level LoRA Policy Head (460,800 parameters)
  5. Slow-Loop Multi-Agent Governor (&Delta;&pi; formulation)
  6. Deterministic Fail-Closed Safety Gate (100% volume conservation)

### POST /api/studio/traffic-stress
- **Method**: `POST`
- **Path**: `/api/studio/traffic-stress`
- **Body**: `{"burst_type": "elephant_8m"}` (`elephant_8m`, `elephant_12m`, `elephant_25m`, `mice_storm`, `flash_crowd`)
- **Response**: `200 OK` Reports packets injected, peak bandwidth (Mbps), and ingress port.

### POST /api/studio/chaos-matrix
- **Method**: `POST`
- **Path**: `/api/studio/chaos-matrix`
- **Body**: `{"phase": 1}` (1 to 4)
- **Response**: `200 OK` Executes link drop, queue flap, flow mutation, or microburst wave, verifying sub-5ms failover and safety veto.

### POST /api/studio/flow-mod/inject
- **Method**: `POST`
- **Path**: `/api/studio/flow-mod/inject`
- **Body**:
  ```json
  {
    "dpid": "0000000000000001",
    "match": {"in_port": 1, "eth_type": 2048, "ipv4_dst": "10.0.0.4"},
    "actions": [{"type": "OUTPUT", "port": 4}],
    "priority": 100
  }
  ```
- **Response**: `200 OK` Injects verified flow modification into Table 0 after formal safety gate evaluation.

### GET /api/studio/flow-mod/rules
- **Method**: `GET`
- **Path**: `/api/studio/flow-mod/rules?dpid=0000000000000001`
- **Response**: `200 OK` Lists active Table 0 OpenFlow rules installed on the target switch.

### POST /api/studio/lyapunov-tune
- **Method**: `POST`
- **Path**: `/api/studio/lyapunov-tune`
- **Body**: `{"V": 12.0, "w_delay": 1.0, "w_loss": 5.0, "w_churn": 0.2}`
- **Response**: `200 OK` Dynamically updates Lyapunov trade-off parameters and recalculates theoretical backlog bounds.

### GET /api/studio/export-report
- **Method**: `GET`
- **Path**: `/api/studio/export-report`
- **Response**: `200 OK` Returns JSON diagnostic report with SHA-256 integrity signature and team attribution.

### GET /api/studio/telemetry-stream
- **Method**: `GET`
- **Path**: `/api/studio/telemetry-stream`
- **Response**: `200 OK` Streams live throughput, queue depth, packet loss, and Lyapunov objective value.

### GET /api/studio/link-impairment/status
- **Method**: `GET`
- **Path**: `/api/studio/link-impairment/status`
- **Response**: `200 OK`
  ```json
  {
    "active_link": "s1-s2",
    "latency_ms": 0.0,
    "loss_pct": 0.0,
    "bandwidth_mbps": 10.0,
    "status": "nominal",
    "recommended_path": "s1 -> s2 -> s4"
  }
  ```

### POST /api/studio/link-impairment/set
- **Method**: `POST`
- **Path**: `/api/studio/link-impairment/set`
- **Body**:
  ```json
  {
    "link": "s1-s2",
    "latency_ms": 45.0,
    "loss_pct": 8.0,
    "bandwidth_mbps": 3.0
  }
  ```
- **Response**: `200 OK`
  Dynamically injects calibrated link latency, packet loss, and bandwidth restriction, computing alternate path recommendation (`s1 -> s3 -> s4`).

### POST /api/studio/link-impairment/reset
- **Method**: `POST`
- **Path**: `/api/studio/link-impairment/reset`
- **Response**: `200 OK` Restores all physical trunk links to nominal baseline state (0ms added delay, 0% loss, 10 Mbps).

### POST /api/studio/benchmark-run
- **Method**: `POST`
- **Path**: `/api/studio/benchmark-run`
- **Body**:
  ```json
  {
    "duration_slots": 50,
    "traffic_pattern": "flash_crowd"
  }
  ```
- **Response**: `200 OK`
  Runs an automated comparative evaluation comparing `S0_STATIC`, `S5_SELFX`, and `DPP_ONLY` over matched slots, returning mean latencies, loss rates, and slot-by-slot trajectories.

### GET /api/studio/sla-audit
- **Method**: `GET`, `POST`
- **Path**: `/api/studio/sla-audit`
- **Response**: `200 OK`
  Audits active fluid datapath telemetry against telecommunications SLA criteria (mean delay < 15ms, P95 delay < 25ms, loss < 0.5%, jitter < 3ms, backlog < 2Mbit, <= 20% discard cap, TCAM < 80%), returning composite score (99.88%), MTBF, MTTR, and cryptographic SHA-256 fingerprint.

### POST /api/studio/flow-mod/flush
- **Method**: `POST`
- **Path**: `/api/studio/flow-mod/flush`
- **Response**: `200 OK`
  Flushes all dynamically injected OpenFlow 1.3 flow rules from switch flow tables, safely preserving default baseline forwarding entries.

### POST /api/studio/flow-mod/delete
- **Method**: `POST`
- **Path**: `/api/studio/flow-mod/delete`
- **Body**: `{"rule_id": "flow-s1-usr-1714859"}`
- **Response**: `200 OK`
  Deletes specified rule from switch Table 0 by unique rule identifier.

---

## 🧠 Frontier Asian Foundation Models Hub Endpoints

Frontier Asian foundation models are evaluated for edge-proximate SDN control plane governance, featuring DeepSeek-R1 (verifiable reasoning), DeepSeek-V3, Qwen 2.5 72B / Coder 32B, Yi-Lightning, and GLM-4.

### GET /api/asian-models/catalog
- **Method**: `GET`
- **Path**: `/api/asian-models/catalog`
- **Response**: `200 OK` Returns model specifications, context windows, pricing, and Multi-Head Latent Attention (MLA) cache reduction statistics.

### POST /api/asian-models/query
- **Method**: `POST`
- **Path**: `/api/asian-models/query`
- **Body**:
  ```json
  {
    "model_id": "deepseek/deepseek-r1",
    "prompt": "Evaluate buffer occupancy q1=1.75 Mbit on switch s1."
  }
  ```
- **Response**: `200 OK` Returns chain-of-thought mathematical reasoning trace and policy delta $\Delta\pi = (\Delta V, \Delta\mathbf{w}, M)$.

### GET /api/asian-models/benchmark
- **Method**: `GET`
- **Path**: `/api/asian-models/benchmark`
- **Response**: `200 OK` Returns 12-controller empirical benchmark matrix comparing P95 latency, loss, and inference cost.

### POST /api/asian-models/arena
- **Method**: `POST`
- **Path**: `/api/asian-models/arena`
- **Body**:
  ```json
  {
    "workload_type": "flash_crowd"
  }
  ```
- **Response**: `200 OK`
  Executes a 4-way parallel evaluation across DeepSeek-R1, DeepSeek-V3, Qwen 2.5 72B, and Yi-Lightning, reporting latencies, token consumption, KV cache footprint, and formulated policy deltas.

### POST /api/asian-models/mla-calculator
- **Method**: `POST`
- **Path**: `/api/asian-models/mla-calculator`
- **Body**:
  ```json
  {
    "context_len": 8192,
    "batch_size": 16
  }
  ```
- **Response**: `200 OK`
  Computes exact KV cache memory footprint across Standard MHA, GQA (8 heads), and MLA (512-dim latent vector), returning percentage savings and GPU concurrency multiplier.

### POST /api/asian-models/consensus
- **Method**: `POST`
- **Path**: `/api/asian-models/consensus`
- **Body**:
  ```json
  {
    "scenario": "core_trunk_congestion"
  }
  ```
- **Response**: `200 OK`
  Executes multi-agent consensus protocol among 3 specialist frontier models: Queue Backlog Specialist (DeepSeek-R1), Traffic Engineering Specialist (Qwen 2.5 72B), and Safety Invariant Auditor (DeepSeek-V3), synthesizing a Pareto-optimal Lyapunov policy delta $\Delta\pi^* = (V^*, \mathbf{w}^*, M^*)$ with verifiable consensus score (98.0%).

### GET / POST /api/studio/dpi-inspection
- **Method**: `GET` or `POST`
- **Path**: `/api/studio/dpi-inspection`
- **Body**:
  ```json
  {
    "dpid": "s1",
    "flow_type": "elephant",
    "limit": 6
  }
  ```
- **Response**: `200 OK`
  Returns hardware-in-the-loop wire-level frame dissection for Ethernet II (VLAN tag), IPv4 (DSCP EF-46, ECN), Transport (TCP/UDP iperf3), and OpenFlow 1.3 Table 0/1/2 match-action pipeline with CRC32 verification.

### POST /api/studio/autonomous-healing
- **Method**: `POST`
- **Path**: `/api/studio/autonomous-healing`
- **Body**:
  ```json
  {
    "anomaly_type": "microburst_synchronization"
  }
  ```
- **Response**: `200 OK`
  Injects operational testbed anomalies (`microburst_synchronization`, `silent_buffer_leak`, `tcam_hash_collision`) and executes closed-loop autonomous remediation with sub-5ms MTTR, reducing queue backlogs with zero dropped frames.

### GET / POST /api/studio/aqm-profiler
- **Method**: `GET` or `POST`
- **Path**: `/api/studio/aqm-profiler`
- **Body**:
  ```json
  {
    "algorithm": "ecn_dctcp",
    "ecn_threshold_kb": 32.0,
    "traffic_load_mbps": 45.0,
    "target_sojourn_ms": 5.0
  }
  ```
- **Response**: `200 OK`
  Profiles RFC 8257 coupled dual-queue ECN marking, CoDel AQM (RFC 8289), PIE (RFC 8033), and RED baseline. Returns instantaneous vs smoothed queue depths, CE marking percentage, zero packet drops under DCTCP, and sojourn time distribution (P50, P95, P99).

### GET / POST /api/studio/int-telemetry
- **Method**: `GET` or `POST`
- **Path**: `/api/studio/int-telemetry`
- **Body**:
  ```json
  {
    "path": "s1_s3_s4"
  }
  ```
- **Response**: `200 OK`
  Dissects RFC 9197 In-Band Network Telemetry (INT-MD v2.1) probe packet headers across switch topology paths, reporting hop-by-hop ingress/egress $\mu\text{s}$ timestamps, queue backlogs, egress port Tx utilization, and bottleneck switch identification.

### POST /api/asian-models/reasoning-trace
- **Method**: `POST`
- **Path**: `/api/asian-models/reasoning-trace`
- **Body**:
  ```json
  {
    "model": "deepseek/deepseek-r1",
    "scenario": "core_trunk_saturation"
  }
  ```
- **Response**: `200 OK`
  Extracts 4-phase verifiable chain-of-thought mathematical derivation of Lyapunov parameter adjustments ($\Delta V$, $\mathbf{w}$, $M$) and fail-closed safety gate validation.

### POST /api/asian-models/multi-agent-debate
- **Method**: `POST`
- **Path**: `/api/asian-models/multi-agent-debate`
- **Body**:
  ```json
  {
    "scenario": "conflicting_qos_demands"
  }
  ```
- **Response**: `200 OK`
  Executes a multi-round structured dialectic debate between DeepSeek-R1 (Queue Stability Specialist) and Qwen 2.5 72B (Throughput & SLA Preserver), adjudicated by DeepSeek-V3 into a Pareto-optimal compiled policy delta with bounded Lyapunov drift $\Delta L < 0$ and $>99\%$ consensus agreement.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*


---

## 9. PRODUCTION AUTHENTICATION & RBAC ENDPOINTS

### POST /api/auth/register
- **Method**: `POST`
- **Path**: `/api/auth/register`
- **Headers**: `Content-Type: application/json`
- **Body**:
  ```json
  {
    "username": "student_auditor_2026",
    "email": "auditor2026@iiitdwd.ac.in",
    "password": "PassWord_2026!",
    "role": "admin"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "success": true,
    "token": "3f8b91a2...",
    "role": "admin",
    "username": "student_auditor_2026",
    "message": "User registered and session token issued."
  }
  ```
- **Description**: Generates a 16-byte cryptographically secure random salt, computes PBKDF2-HMAC-SHA256 hash across 100,000 iterations, stores user in the JSON vault, and returns an authenticated 32-byte session token.

### POST /api/auth/login
- **Method**: `POST`
- **Path**: `/api/auth/login`
- **Headers**: `Content-Type: application/json`
- **Body**:
  ```json
  {
    "username": "student_auditor_2026",
    "password": "PassWord_2026!"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "token": "3f8b91a2...",
    "role": "admin",
    "username": "student_auditor_2026"
  }
  ```
- **Description**: Performs constant-time `hmac.compare_digest` verification. Returns authenticated session token valid for 24 hours.

### GET /api/auth/me
- **Method**: `GET`
- **Path**: `/api/auth/me`
- **Headers**: `Authorization: Bearer <session_token>`
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "authenticated": true,
    "username": "student_auditor_2026",
    "role": "admin",
    "permissions": {
      "can_override_params": true,
      "can_inject_chaos": true,
      "can_execute_studio_tests": true,
      "can_query_models": true,
      "can_export_reports": true,
      "can_manage_users": true
    }
  }
  ```

### POST /api/auth/logout
- **Method**: `POST`
- **Path**: `/api/auth/logout`
- **Headers**: `Authorization: Bearer <session_token>`
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "message": "Session invalidated."
  }
  ```

---

## 10. INTERACTIVE TESTING STUDIO ENDPOINTS

### POST /api/studio/verify
- **Method**: `POST`
- **Path**: `/api/studio/verify`
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "duration_ms": 0.51,
    "run_hash": "5ff45d1c543b1d16",
    "stages": [
      { "id": 1, "name": "Physical Port & Loopback Handshake", "status": "PASS", "latency_us": 412 },
      { "id": 2, "name": "OpenFlow 1.3 Telemetry Stream Ingestion", "status": "PASS", "latency_us": 680 },
      { "id": 3, "name": "Fast DPP Lyapunov Solver [Timescale 1]", "status": "PASS", "latency_us": 14.2 },
      { "id": 4, "name": "Mid-Level LoRA Policy Head [Timescale 2]", "status": "PASS", "latency_us": 4800 },
      { "id": 5, "name": "Slow Multi-Agent Governor [Timescale 3]", "status": "PASS", "latency_us": 12400 },
      { "id": 6, "name": "Deterministic Fail-Closed Safety Guardrail", "status": "PASS", "latency_us": 2.1 }
    ],
    "timestamp": 1794930000
  }
  ```

### POST /api/studio/stress
- **Method**: `POST`
- **Path**: `/api/studio/stress`
- **Body**:
  ```json
  {
    "scenario": "elephant_burst",
    "rate_mbps": 12.0,
    "duration_s": 5.0
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "scenario": "elephant_burst",
    "rate_mbps": 12.0,
    "meter_applied": 6.0,
    "lyapunov_delta_L": -1.45,
    "action": "detour_and_meter"
  }
  ```

### POST /api/studio/tune
- **Method**: `POST`
- **Path**: `/api/studio/tune`
- **Body**:
  ```json
  {
    "trade_off_V": 16.5,
    "delay_weight": 0.8,
    "loss_weight": 2.5
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "V": 16.5,
    "theoretical_bounds": {
      "backlog_bound_mbit": 4.225,
      "drift_penalty_bound": 0.0606
    }
  }
  ```

### GET /api/studio/report
- **Method**: `GET`
- **Path**: `/api/studio/report`
- **Response**: `200 OK (Content-Type: application/json)`
  Exports complete cryptographically signed audit report containing telemetry logs, stage pass rates, parameter vectors, and verification hashes.

---

## 11. FRONTIER ASIAN MODELS PLAYGROUND ENDPOINTS

### POST /api/models/asian/query
- **Method**: `POST`
- **Path**: `/api/models/asian/query`
- **Body**:
  ```json
  {
    "model": "deepseek/deepseek-r1",
    "system_prompt": "You are the SELF-X Multi-Agent Governor for an active OpenFlow 1.3 network.",
    "user_prompt": "Queue backlog on Switch 2 Port 3 exceeds 85%. Egress throughput 11.8 Mbps. Formulate policy delta."
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "model": "deepseek/deepseek-r1",
    "elapsed_ms": 564.42,
    "policy_delta": {
      "trade_off_V": -2.0,
      "delay_weight": 0.06,
      "loss_weight": 0.06,
      "meter_rate_mbps": 6.0,
      "rationale": "High-priority traffic rerouted to Port 4 secondary trunk; rate limit 6 Mbps active."
    },
    "tokens": {
      "prompt_tokens": 142,
      "completion_tokens": 68,
      "total_tokens": 210
    }
  }
  ```

### GET /api/models/asian/stats
- **Method**: `GET`
- **Path**: `/api/models/asian/stats`
- **Response**: `200 OK`
  Returns active model metrics, MLA memory savings ratios (93.3% VRAM compression), token pricing comparisons, and average inference latency.

---

## 12. CODEBASE EXPLORER ENDPOINTS

### GET /api/repo/tree
- **Method**: `GET`
- **Path**: `/api/repo/tree`
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "total_files": 4461,
    "total_lines": 3036247,
    "total_bytes": 934583210,
    "categories": ["paper", "selfx", "Web", "submission", "tests"],
    "files": [
      { "path": "README.md", "name": "README.md", "category": "root", "size": 23098, "ext": "md" },
      { "path": "Web/server.py", "name": "server.py", "category": "Web", "size": 178920, "ext": "py" }
    ]
  }
  ```

### POST /api/repo/file
- **Method**: `POST`
- **Path**: `/api/repo/file`
- **Body**:
  ```json
  {
    "path": "README.md"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "path": "README.md",
    "lines": 183,
    "bytes": 23098,
    "content": "# SELF-X · Autonomous Closed-Loop SDN Flow Control Platform..."
  }
  ```
- **Security Invariant**: Strictly validates `Path(path).resolve().is_relative_to(ROOT)`; rejects any attempt to traverse outside the workspace.

---
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
﻿
---

## 14. Automated Diagnostics, Chaos Injection & Testing Studio Endpoints

### GET /api/studio/diagnostics
- **Method**: `GET`
- **Path**: `/api/studio/diagnostics`
- **Description**: Runs the 6 automated system diagnostic health checks across switches, REST bridges, flow tables, meters, telemetry, and safety gates.
- **Response**: `200 OK`
  ```json
  {
    "status": "ALL_DIAGNOSTICS_PASSED",
    "timestamp": 1731902400.12,
    "stages": [
      { "stage_id": 1, "name": "Switch DPID Reachability", "passed": true, "latency_ms": 1.2 },
      { "stage_id": 2, "name": "Ryu REST Bridge Socket", "passed": true, "latency_ms": 0.8 },
      { "stage_id": 3, "name": "TCAM Table 0 Active Rules", "passed": true, "rule_count": 8 },
      { "stage_id": 4, "name": "Meter Band Token Buckets", "passed": true, "active_meters": 2 },
      { "stage_id": 5, "name": "In-Band Telemetry Ingestion", "passed": true, "jitter_ms": 0.14 },
      { "stage_id": 6, "name": "Deterministic Safety Gate", "passed": true, "veto_count": 0 }
    ]
  }
  ```

### POST /api/studio/burst
- **Method**: `POST`
- **Path**: `/api/studio/burst`
- **Description**: Triggers an instantaneous elephant burst (12.0 Mbps) into the primary path to evaluate Timescale 1 Lyapunov DPP dynamic rerouting.
- **Request Body**:
  ```json
  {
    "burst_rate_mbps": 12.0,
    "duration_slots": 50,
    "target_flow": "iperf_flow_1"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "burst_injected": true,
    "offered_rate_mbps": 12.0,
    "active_route": "detour_port_4",
    "reroute_latency_us": 14.2
  }
  ```

### POST /api/studio/chaos
- **Method**: `POST`
- **Path**: `/api/studio/chaos`
- **Description**: Injects edge link down chaos (Port 3 severed) to trigger and verify OpenFlow 1.3 Fast Failover Group 1 sub-10ms hardware path switching.
- **Request Body**:
  ```json
  {
    "action": "cut_link",
    "target_port": 3,
    "switch_dpid": "0000000000000001"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "success": true,
    "chaos_applied": "port_down",
    "switch_dpid": "0000000000000001",
    "fast_failover_triggered": true,
    "failover_latency_ms": 6.8,
    "in_flight_loss_packets": 0
  }
  ```

---

## 15. Asian Foundation Models & MLA KV Cache Compression Endpoints

### GET /api/models/list
- **Method**: `GET`
- **Path**: `/api/models/list`
- **Description**: Enumerates supported frontier Asian foundation models on OpenRouter with active context lengths, inference pricing, and latency profiles.
- **Response**: `200 OK`
  ```json
  {
    "models": [
      {
        "id": "deepseek/deepseek-r1-distill-qwen-32b",
        "name": "DeepSeek-R1 Distill Qwen 32B",
        "context_tokens": 131072,
        "input_price_per_1m": 0.14,
        "output_price_per_1m": 0.28,
        "mla_supported": true
      },
      {
        "id": "qwen/qwen-2.5-72b-instruct",
        "name": "Qwen 2.5 72B Instruct",
        "context_tokens": 131072,
        "input_price_per_1m": 0.35,
        "output_price_per_1m": 0.40,
        "mla_supported": true
      }
    ]
  }
  ```

### POST /api/models/mla-calc
- **Method**: `POST`
- **Path**: `/api/models/mla-calc`
- **Description**: Computes dynamic Multi-Head Latent Attention (MLA) Key-Value cache memory footprint reduction versus standard Multi-Head Attention (MHA).
- **Request Body**:
  ```json
  {
    "context_tokens": 27000,
    "num_layers": 60,
    "num_heads": 128,
    "head_dim": 128,
    "latent_dim": 512
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "context_tokens": 27000,
    "mha_kv_cache_mb": 5062.5,
    "mla_kv_cache_mb": 79.1,
    "memory_reduction_ratio": 64.0,
    "memory_reduction_percentage": 98.44
  }
  ```

---

## 16. Production Client Integration Examples in Python, Go, and cURL

### Python `urllib` Client Example

```python
import urllib.request
import json

def fetch_telemetry_snapshot(server_url: str = "http://127.0.0.1:5000") -> dict:
    req = urllib.request.Request(
        f"{server_url}/api/results",
        headers={"User-Agent": "SELF-X-Audit-Client/1.0"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    data = fetch_telemetry_snapshot()
    print("Fetched controller results:", len(data.get("controllers", [])))
```

### cURL CLI Example

```bash
# Retrieve live testbed ablation results
curl -s http://127.0.0.1:5000/api/ablation/table2 | jq .

# Trigger sub-10ms fast failover chaos test
curl -s -X POST http://127.0.0.1:5000/api/studio/chaos \
  -H "Content-Type: application/json" \
  -d '{"action": "cut_link", "target_port": 3}' | jq .
```

---
*Authored by Team SDN_07 — EC466: Software Defined Networks • IIIT Dharwad*
