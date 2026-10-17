"""Portable, append-only result writer for SELF-X experiments."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .result_schema import (
    ResultValidationError,
    SCHEMA_VERSION,
    validate_metric_record,
    validate_run_metadata,
    validate_summary,
    validate_trace_record,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: Mapping[str, Any], exclusive: bool = False) -> None:
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


class ResultWriter:
    """Create a unique run directory and finalize it exactly once."""

    def __init__(self, results_root: str | os.PathLike[str], metadata: Mapping[str, Any]):
        self.results_root = Path(results_root).resolve()
        self.metadata = validate_run_metadata(metadata)
        self.run_dir = (self.results_root / self.metadata["run_id"]).resolve()
        if self.run_dir.parent != self.results_root:
            raise ResultValidationError("run directory escapes results root")
        if self.run_dir.exists():
            raise FileExistsError(f"result run already exists: {self.metadata['run_id']}")
        self.run_dir.mkdir(parents=True)
        self._finalized = False
        self._metric_path = self.run_dir / "metrics.jsonl"
        self._write_metadata()
        self._metric_path.touch(exist_ok=False)

    @property
    def run_id(self) -> str:
        return self.metadata["run_id"]

    def _write_metadata(self) -> None:
        _write_json(self.run_dir / "run.json", self.metadata, exclusive=True)

    def _ensure_open(self) -> None:
        if self._finalized:
            raise RuntimeError("result run is already finalized")

    def append_metric(self, record: Mapping[str, Any]) -> None:
        self._ensure_open()
        metric = validate_metric_record(record)
        if metric["run_id"] != self.run_id:
            raise ResultValidationError("metric run_id does not match writer run_id")
        if metric["provenance"] != self.metadata["provenance"]:
            raise ResultValidationError("metric provenance does not match run provenance")
        with self._metric_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metric, sort_keys=True, allow_nan=False) + "\n")

    def append_trace(self, record: Mapping[str, Any]) -> None:
        self._ensure_open()
        trace = validate_trace_record(record)
        if trace["run_id"] != self.run_id or trace["provenance"] != self.metadata["provenance"]:
            raise ResultValidationError("trace does not match writer run metadata")
        with (self.run_dir / "trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, sort_keys=True, allow_nan=False) + "\n")

    def append_log(self, message: str) -> None:
        self._ensure_open()
        if not isinstance(message, str):
            raise ResultValidationError("log message must be a string")
        with (self.run_dir / "run.log").open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip("\n") + "\n")

    def finalize(self, status: str, summary: Mapping[str, Any] | None = None, error: Mapping[str, Any] | None = None) -> Path:
        self._ensure_open()
        if status not in {"completed", "failed"}:
            raise ResultValidationError("final status must be completed or failed")
        if status == "completed" and summary is None:
            raise ResultValidationError("completed runs require a summary")
        if status == "failed" and error is None:
            raise ResultValidationError("failed runs require an error")
        if summary is not None:
            summary_data = validate_summary(summary)
            if summary_data["run_id"] != self.run_id:
                raise ResultValidationError("summary run_id does not match writer run_id")
            if summary_data["provenance"] != self.metadata["provenance"]:
                raise ResultValidationError("summary provenance does not match run provenance")
            _write_json(self.run_dir / "summary.json", summary_data, exclusive=True)
        updated = dict(self.metadata)
        updated["status"] = status
        updated["artifacts"] = dict(updated["artifacts"])
        updated["artifacts"]["run"] = "run.json"
        updated["artifacts"]["metrics"] = "metrics.jsonl"
        if summary is not None:
            updated["artifacts"]["summary"] = "summary.json"
        if (self.run_dir / "trace.jsonl").exists():
            updated["artifacts"]["trace"] = "trace.jsonl"
        if (self.run_dir / "run.log").exists():
            updated["artifacts"]["log"] = "run.log"
        if error is not None:
            updated["error"] = dict(error)
        updated = validate_run_metadata(updated)
        metadata_path = self.run_dir / "run.json"
        temporary_path = self.run_dir / ".run.json.tmp"
        _write_json(temporary_path, updated, exclusive=True)
        os.replace(temporary_path, metadata_path)
        self.metadata = updated
        self._finalized = True
        return self.run_dir


def read_run(run_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Read and validate a finalized or running result directory."""

    path = Path(run_dir).resolve()
    metadata_path = path / "run.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    with metadata_path.open(encoding="utf-8") as handle:
        metadata = validate_run_metadata(json.load(handle))
    result: dict[str, Any] = {"run": metadata, "metrics": []}
    metrics_path = path / metadata["artifacts"].get("metrics", "metrics.jsonl")
    if metrics_path.is_file():
        with metrics_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    try:
                        result["metrics"].append(validate_metric_record(json.loads(line)))
                    except (json.JSONDecodeError, ResultValidationError) as exc:
                        raise ResultValidationError(f"invalid metrics line {line_number}: {exc}") from exc
    summary_path = path / metadata["artifacts"].get("summary", "summary.json")
    if summary_path.is_file():
        with summary_path.open(encoding="utf-8") as handle:
            result["summary"] = validate_summary(json.load(handle))
    return result