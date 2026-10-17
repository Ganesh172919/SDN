"""Validation for versioned SELF-X experiment result records."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Mapping


class ResultValidationError(ValueError):
    """Raised when a result record is unsafe or does not match the schema."""


SCHEMA_VERSION = "selfx.result.v1"
PROVENANCE_VALUES = {"simulation", "recorded_testbed", "live"}
RUN_STATUSES = {"running", "completed", "failed"}
EXPERIMENT_STAGES = {"A0", "A1", "A2", "A3", "A4", "A5"}
KNOWN_METRICS = {
    "latency_ms": "ms",
    "p95_latency_ms": "ms",
    "throughput_mbps": "Mbps",
    "throughput_kbps": "kbps",
    "loss_pct": "%",
    "queue_mbit": "Mbit",
    "energy": "unitless",
    "resource_cost": "unitless",
    "sla_violations": "count",
    "reward": "unitless",
}
SECRET_KEY_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "passwd",
    "secret",
    "session",
    "token",
}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _fail(message: str) -> None:
    raise ResultValidationError(message)


def _check_finite(value: Any, path: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)) and not math.isfinite(value):
        _fail(f"{path} must be finite")


def _check_no_secrets(value: Any, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower().replace("-", "_")
            if any(part in key_text for part in SECRET_KEY_PARTS):
                _fail(f"secret-bearing field is not allowed: {path}.{key}")
            _check_no_secrets(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _check_no_secrets(child, f"{path}[{index}]")
        return
    _check_finite(value, path)


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{path} must be an object")
    return value


def _require_string(value: Any, path: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        _fail(f"{path} must be a non-empty string")
    return value


def _require_utc_timestamp(value: Any, path: str) -> str:
    text = _require_string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResultValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{path} must include a UTC offset")
    return text


def validate_provenance(value: Any) -> str:
    provenance = _require_string(value, "provenance")
    if provenance not in PROVENANCE_VALUES:
        _fail(f"invalid provenance: {provenance}")
    return provenance


def validate_artifact_path(value: Any, path: str = "artifact_path") -> str:
    artifact = _require_string(value, path)
    if "\\" in artifact or artifact.startswith("/") or re.match(r"^[A-Za-z]:", artifact):
        _fail(f"{path} must be a relative POSIX path")
    parts = PurePosixPath(artifact).parts
    if not parts or ".." in parts or "." in parts:
        _fail(f"{path} contains unsafe path components")
    return artifact


def _validate_artifacts(value: Any) -> dict[str, str]:
    artifacts = _require_mapping(value, "artifacts")
    return {
        str(key): validate_artifact_path(path, f"artifacts.{key}")
        for key, path in artifacts.items()
    }


def validate_run_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_require_mapping(metadata, "run"))
    _check_no_secrets(data)
    if data.get("schema_version") != SCHEMA_VERSION:
        _fail(f"schema_version must be {SCHEMA_VERSION}")
    run_id = _require_string(data.get("run_id"), "run_id")
    if not RUN_ID_RE.fullmatch(run_id):
        _fail("run_id contains unsafe characters")
    _require_utc_timestamp(data.get("created_at_utc"), "created_at_utc")
    _require_string(data.get("git_commit"), "git_commit")
    experiment = _require_mapping(data.get("experiment"), "experiment")
    stage = _require_string(experiment.get("stage"), "experiment.stage")
    if stage not in EXPERIMENT_STAGES:
        _fail(f"invalid experiment stage: {stage}")
    _require_string(experiment.get("controller_mode"), "experiment.controller_mode")
    _require_mapping(data.get("topology"), "topology")
    _require_mapping(data.get("workload"), "workload")
    if not isinstance(data.get("seed"), int) or isinstance(data.get("seed"), bool):
        _fail("seed must be an integer")
    if not isinstance(data.get("duration_seconds"), (int, float)) or data["duration_seconds"] <= 0:
        _fail("duration_seconds must be positive")
    _require_mapping(data.get("environment"), "environment")
    status = _require_string(data.get("status"), "status")
    if status not in RUN_STATUSES:
        _fail(f"invalid run status: {status}")
    validate_provenance(data.get("provenance"))
    data["artifacts"] = _validate_artifacts(data.get("artifacts"))
    error = data.get("error")
    if status == "failed" and not isinstance(error, Mapping):
        _fail("failed runs require an error object")
    if status == "completed" and error is not None:
        _fail("completed runs cannot contain an error")
    if error is not None:
        _require_string(_require_mapping(error, "error").get("message"), "error.message")
    return data


def validate_metric_record(record: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_require_mapping(record, "metric"))
    _check_no_secrets(data)
    if data.get("schema_version") != SCHEMA_VERSION:
        _fail(f"metric schema_version must be {SCHEMA_VERSION}")
    _require_string(data.get("run_id"), "metric.run_id")
    if not isinstance(data.get("sequence"), int) or data["sequence"] < 0:
        _fail("metric.sequence must be a non-negative integer")
    _require_utc_timestamp(data.get("window_start_utc"), "metric.window_start_utc")
    if not isinstance(data.get("window_seconds"), (int, float)) or data["window_seconds"] <= 0:
        _fail("metric.window_seconds must be positive")
    validate_provenance(data.get("provenance"))
    metrics = _require_mapping(data.get("metrics"), "metric.metrics")
    for name, metric in metrics.items():
        if name not in KNOWN_METRICS:
            _fail(f"unknown metric: {name}")
        metric_data = _require_mapping(metric, f"metric.metrics.{name}")
        unit = _require_string(metric_data.get("unit"), f"metric.metrics.{name}.unit")
        expected_unit = KNOWN_METRICS[name]
        if unit != expected_unit:
            _fail(f"metric.metrics.{name}.unit must be {expected_unit}")
        _require_string(metric_data.get("source"), f"metric.metrics.{name}.source")
        value = metric_data.get("value")
        if value is None:
            if metric_data.get("status") != "unavailable":
                _fail(f"unavailable metric {name} must have status unavailable")
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            _fail(f"metric.metrics.{name}.value must be numeric or null")
        elif name.endswith("_pct") and not 0 <= value <= 100:
            _fail(f"metric.metrics.{name}.value must be between 0 and 100")
        elif name in {"latency_ms", "p95_latency_ms", "throughput_mbps", "throughput_kbps", "queue_mbit", "energy", "resource_cost", "sla_violations"} and value < 0:
            _fail(f"metric.metrics.{name}.value cannot be negative")
    action = data.get("action")
    if action is not None:
        action_data = _require_mapping(action, "metric.action")
        _require_string(action_data.get("name"), "metric.action.name")
        if not isinstance(action_data.get("installed"), bool):
            _fail("metric.action.installed must be boolean")
    return data


def validate_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_require_mapping(summary, "summary"))
    _check_no_secrets(data)
    if data.get("schema_version") != SCHEMA_VERSION:
        _fail(f"summary schema_version must be {SCHEMA_VERSION}")
    _require_string(data.get("run_id"), "summary.run_id")
    validate_provenance(data.get("provenance"))
    _require_mapping(data.get("metrics"), "summary.metrics")
    return data


def validate_trace_record(record: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_require_mapping(record, "trace"))
    _check_no_secrets(data)
    if data.get("schema_version") != SCHEMA_VERSION:
        _fail(f"trace schema_version must be {SCHEMA_VERSION}")
    _require_string(data.get("run_id"), "trace.run_id")
    if not isinstance(data.get("sequence"), int) or data["sequence"] < 0:
        _fail("trace.sequence must be a non-negative integer")
    _require_utc_timestamp(data.get("timestamp_utc"), "trace.timestamp_utc")
    _require_string(data.get("event"), "trace.event")
    validate_provenance(data.get("provenance"))
    return data