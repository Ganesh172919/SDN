import json
import tempfile
import unittest
from pathlib import Path

from selfx.eval.result_schema import ResultValidationError, SCHEMA_VERSION
from selfx.eval.result_writer import ResultWriter, read_run
from selfx.eval.tests.test_result_schema import valid_metric, valid_run


class ResultWriterTests(unittest.TestCase):
    def test_writes_and_reads_valid_simulation_result(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ResultWriter(directory, valid_run())
            writer.append_metric(valid_metric())
            writer.finalize(
                "completed",
                {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": writer.run_id,
                    "provenance": "simulation",
                    "metrics": {"latency_ms": {"value": 5.0, "unit": "ms", "source": "simulator"}},
                },
            )
            result = read_run(Path(directory) / writer.run_id)
            self.assertEqual(len(result["metrics"]), 1)
            self.assertEqual(result["run"]["status"], "completed")

    def test_does_not_overwrite_existing_run(self):
        with tempfile.TemporaryDirectory() as directory:
            ResultWriter(directory, valid_run())
            with self.assertRaises(FileExistsError):
                ResultWriter(directory, valid_run())

    def test_failed_run_requires_error_and_is_not_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ResultWriter(directory, valid_run())
            with self.assertRaises(ResultValidationError):
                writer.finalize("completed")
            writer.finalize("failed", error={"message": "dependency unavailable"})
            with (Path(directory) / writer.run_id / "run.json").open(encoding="utf-8") as handle:
                metadata = json.load(handle)
            self.assertEqual(metadata["status"], "failed")

    def test_cannot_write_after_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ResultWriter(directory, valid_run())
            writer.finalize("failed", error={"message": "stopped"})
            with self.assertRaises(RuntimeError):
                writer.append_log("late mutation")


if __name__ == "__main__":
    unittest.main()