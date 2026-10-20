import json
import tempfile
import unittest
from pathlib import Path

from eval.result_integration import (
    ExperimentResultRecorder,
    build_metric_record,
    build_run_metadata,
)
from eval.result_schema import ResultValidationError, validate_metric_record, validate_run_metadata
from eval.result_writer import read_run


def row(cycle=0, action="no_op"):
    return {
        "cycle": cycle,
        "latency_ms": 5.0 + cycle,
        "throughput_kbps": 800.0,
        "loss_pct": 0.0,
        "reward": "" if action == "no_op" else 0.25,
        "installed_action": action,
        "requested_action": action,
    }


class ResultIntegrationTests(unittest.TestCase):
    def test_each_mvp_condition_writes_valid_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            for condition in ("A0", "A1", "A2"):
                recorder = ExperimentResultRecorder(condition, 5, directory)
                recorder.record(row(), {"condition": condition})
                recorder.complete()
                result = read_run(recorder.run_dir)
                self.assertEqual(result["run"]["experiment"]["stage"], condition)
                self.assertEqual(result["run"]["provenance"], "live")
                self.assertEqual(result["metrics"][0]["sequence"], 0)

    def test_metadata_and_metric_contracts_are_validated(self):
        metadata = build_run_metadata("A1", 5, "a1-fixture")
        validate_run_metadata(metadata)
        metric = build_metric_record("a1-fixture", 0, row())
        validate_metric_record(metric)
        self.assertEqual(metric["metrics"]["queue_mbit"]["status"], "unavailable")

    def test_summary_matches_written_records(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = ExperimentResultRecorder("A2", 10, directory)
            recorder.record(row(0, "reroute"), {"condition": "A2"})
            recorder.record(row(1, "no_op"), {"condition": "A2"})
            recorder.complete()
            result = read_run(recorder.run_dir)
            self.assertEqual(result["summary"]["window_count"], len(result["metrics"]))
            self.assertEqual(result["summary"]["metrics"]["latency_ms"]["value"], 5.5)

    def test_failure_is_recorded_and_finalized_writer_cannot_change(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = ExperimentResultRecorder("A0", 5, directory)
            recorder.record(row(), {"condition": "A0"})
            recorder.fail(RuntimeError("secret-looking local failure"))
            result = read_run(recorder.run_dir)
            self.assertEqual(result["run"]["status"], "failed")
            self.assertNotIn("secret-looking", json.dumps(result["run"]))
            with self.assertRaises(RuntimeError):
                recorder.writer.append_metric(build_metric_record(recorder.run_id, 1, row(1)))

    def test_provenance_is_not_filename_derived(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = ExperimentResultRecorder("A1", 5, directory)
            recorder.record(row(), {"condition": "A1"})
            recorder.complete()
            result = read_run(recorder.run_dir)
            self.assertEqual(result["run"]["provenance"], "live")
            self.assertNotEqual(result["run"]["provenance"], "simulation")


if __name__ == "__main__":
    unittest.main()