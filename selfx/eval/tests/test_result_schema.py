import math
import unittest

from selfx.eval.result_schema import (
    ResultValidationError,
    SCHEMA_VERSION,
    validate_artifact_path,
    validate_metric_record,
    validate_run_metadata,
)


def valid_run(**overrides):
    data = {
        "schema_version": SCHEMA_VERSION,
        "run_id": "test-run-001",
        "created_at_utc": "2026-10-17T12:00:00Z",
        "git_commit": "55226da",
        "experiment": {"stage": "A0", "controller_mode": "static"},
        "topology": {"id": "linear-4-switch-8-host"},
        "workload": {"profile": "default"},
        "seed": 1729,
        "duration_seconds": 60,
        "environment": {"python": "3.13.7"},
        "status": "running",
        "provenance": "simulation",
        "artifacts": {"run": "run.json", "metrics": "metrics.jsonl"},
    }
    data.update(overrides)
    return data


def valid_metric(**overrides):
    data = {
        "schema_version": SCHEMA_VERSION,
        "run_id": "test-run-001",
        "sequence": 0,
        "window_start_utc": "2026-10-17T12:00:00Z",
        "window_seconds": 60,
        "provenance": "simulation",
        "metrics": {
            "latency_ms": {"value": 5.0, "unit": "ms", "source": "simulator"},
            "loss_pct": {"value": None, "unit": "%", "source": "unavailable", "status": "unavailable"},
        },
        "action": {"name": "no_op", "installed": False},
    }
    data.update(overrides)
    return data


class ResultSchemaTests(unittest.TestCase):
    def test_valid_metadata_and_metric(self):
        self.assertEqual(validate_run_metadata(valid_run())["run_id"], "test-run-001")
        self.assertEqual(validate_metric_record(valid_metric())["sequence"], 0)

    def test_rejects_missing_or_invalid_provenance(self):
        with self.assertRaises(ResultValidationError):
            validate_run_metadata(valid_run(provenance=None))
        with self.assertRaises(ResultValidationError):
            validate_metric_record(valid_metric(provenance="live-ish"))

    def test_rejects_invalid_stage_and_malformed_metadata(self):
        with self.assertRaises(ResultValidationError):
            validate_run_metadata(valid_run(experiment={"stage": "A7", "controller_mode": "static"}))
        with self.assertRaises(ResultValidationError):
            validate_run_metadata(valid_run(topology="linear"))

    def test_rejects_nan_and_infinity(self):
        with self.assertRaises(ResultValidationError):
            validate_metric_record(valid_metric(metrics={"latency_ms": {"value": math.nan, "unit": "ms", "source": "x"}}))
        with self.assertRaises(ResultValidationError):
            validate_metric_record(valid_metric(metrics={"latency_ms": {"value": math.inf, "unit": "ms", "source": "x"}}))

    def test_rejects_unsafe_paths(self):
        for path in ("../outside.json", "C:/outside.json", "nested\\outside.json", "/absolute.json"):
            with self.subTest(path=path), self.assertRaises(ResultValidationError):
                validate_artifact_path(path)

    def test_rejects_secret_bearing_metadata(self):
        with self.assertRaises(ResultValidationError):
            validate_run_metadata(valid_run(environment={"api_key": "not-real"}))


if __name__ == "__main__":
    unittest.main()