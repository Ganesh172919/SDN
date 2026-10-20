"""A0/A1/A2 result-bundle integration for the existing live harness."""

from __future__ import annotations

import os
import platform
import subprocess
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

try:
    from .result_schema import SCHEMA_VERSION
    from .result_writer import ResultWriter, utc_now
except ImportError:  # pragma: no cover - supports direct script compatibility
    from eval.result_schema import SCHEMA_VERSION
    from eval.result_writer import ResultWriter, utc_now

try:
    import config
except ImportError:  # pragma: no cover - supports imports from repository root
    from selfx import config


RESULT_PROVENANCE = "live"
DEFAULT_RESULTS_ROOT = Path(__file__).resolve().parents[1] / "output" / "testbed_results"


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runtime": platform.python_implementation(),
    }


def build_run_metadata(condition: str, duration_seconds: int, run_id: str | None = None) -> dict[str, Any]:
    if condition not in config.CONDITIONS:
        raise ValueError(f"unsupported A0/A1/A2 condition: {condition}")
    generated_id = run_id or f"{condition.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": generated_id,
        "created_at_utc": utc_now(),
        "git_commit": _git_commit(),
        "experiment": {
            "stage": condition,
            "controller_mode": "static_ryu" if condition == "A0" else "langgraph_single_agent",
        },
        "topology": {
            "id": "linear-4-switch-8-host",
            "switches": config.NUM_SWITCHES,
            "hosts": config.NUM_HOSTS,
            "openflow": config.OF_VERSION,
        },
        "workload": {
            "steady_mbps": config.IPERF_STEADY_MBPS,
            "burst_rate_mbps": [config.BURST_MIN_MBPS, config.BURST_MAX_MBPS],
            "burst_duration_seconds": [config.BURST_MIN_DURATION_SEC, config.BURST_MAX_DURATION_SEC],
            "traffic_generator": "selfx.traffic_gen",
        },
        "seed": config.TRAFFIC_SEED,
        "duration_seconds": duration_seconds,
        "environment": _environment(),
        "status": "running",
        "provenance": RESULT_PROVENANCE,
        "artifacts": {"run": "run.json", "metrics": "metrics.jsonl"},
    }


def _metric(value: Any, unit: str, source: str) -> dict[str, Any]:
    if value in (None, ""):
        return {"value": None, "unit": unit, "source": source, "status": "unavailable"}
    return {"value": float(value), "unit": unit, "source": source, "status": "available"}


def build_metric_record(run_id: str, sequence: int, row: Mapping[str, Any]) -> dict[str, Any]:
    action = row.get("installed_action") or "no_op"
    action_was_attempted = action not in {"", "no_op"}
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "sequence": sequence,
        "window_start_utc": row.get("window_start_utc", utc_now()),
        "window_seconds": config.CONTROL_LOOP_INTERVAL_SEC,
        "provenance": RESULT_PROVENANCE,
        "metrics": {
            "latency_ms": _metric(row.get("latency_ms"), "ms", "live_mininet_ping"),
            "p95_latency_ms": _metric(None, "ms", "not_collected_by_current_harness"),
            "throughput_kbps": _metric(row.get("throughput_kbps"), "kbps", "live_ryu_port_counters"),
            "loss_pct": _metric(row.get("loss_pct"), "%", "live_ryu_port_counters"),
            "queue_mbit": _metric(None, "Mbit", "not_collected_by_current_harness"),
            "reward": _metric(row.get("reward"), "unitless", "selfx_reward"),
        },
        "action": {
            "name": action,
            "requested": row.get("requested_action") or action,
            "attempted": action_was_attempted,
            "installed": False,
            "installation_status": "attempted_not_verified" if action_was_attempted else "not_applicable",
        },
    }


def _summary_metric(values: list[Any], unit: str) -> dict[str, Any]:
    available = [float(value) for value in values if value not in (None, "")]
    if not available:
        return {"value": None, "unit": unit, "source": "run_summary", "status": "unavailable"}
    return {"value": mean(available), "unit": unit, "source": "run_summary", "status": "available"}


def build_summary(run_id: str, rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "provenance": RESULT_PROVENANCE,
        "window_count": len(rows),
        "metrics": {
            "latency_ms": _summary_metric([row.get("latency_ms") for row in rows], "ms"),
            "p95_latency_ms": _summary_metric([], "ms"),
            "throughput_kbps": _summary_metric([row.get("throughput_kbps") for row in rows], "kbps"),
            "loss_pct": _summary_metric([row.get("loss_pct") for row in rows], "%"),
            "queue_mbit": _summary_metric([], "Mbit"),
            "reward": _summary_metric([row.get("reward") for row in rows], "unitless"),
        },
    }


def _safe_error(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": "experiment condition failed; inspect the process log for local diagnostics",
    }


class ExperimentResultRecorder:
    """Write validated records while preserving the existing harness outputs."""

    def __init__(self, condition: str, duration_seconds: int, results_root: str | os.PathLike[str] = DEFAULT_RESULTS_ROOT):
        self.writer = ResultWriter(results_root, build_run_metadata(condition, duration_seconds))
        self.rows: list[Mapping[str, Any]] = []

    @property
    def run_id(self) -> str:
        return self.writer.run_id

    @property
    def run_dir(self) -> Path:
        return self.writer.run_dir

    def record(self, row: Mapping[str, Any], trace: Mapping[str, Any] | None = None) -> None:
        sequence = len(self.rows)
        self.writer.append_metric(build_metric_record(self.run_id, sequence, row))
        if trace is not None:
            trace_record = {
                "schema_version": SCHEMA_VERSION,
                "run_id": self.run_id,
                "sequence": sequence,
                "timestamp_utc": row.get("window_start_utc", utc_now()),
                "event": "control_cycle",
                "provenance": RESULT_PROVENANCE,
                **dict(trace),
            }
            self.writer.append_trace(trace_record)
        self.writer.append_log(f"cycle={row.get('cycle', sequence)} action={row.get('installed_action', 'no_op')}")
        self.rows.append(dict(row))

    def complete(self) -> Path:
        return self.writer.finalize("completed", summary=build_summary(self.run_id, self.rows))

    def fail(self, exc: BaseException) -> Path:
        if self.writer.metadata["status"] != "running":
            return self.run_dir
        return self.writer.finalize("failed", error=_safe_error(exc))
