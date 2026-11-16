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
    "simulation": true,
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
Lists all network fabrics available in the simulation studio and testbed manifest directory (`selfx/output/topologies/`).

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
*Authored by Team SDN_07 — EC466: Software Defined Networks | IIIT Dharwad*
