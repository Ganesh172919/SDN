import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2]))
from selfx.eval.result_integration import ExperimentResultRecorder
from selfx.eval.result_schema import SCHEMA_VERSION

sys.path.insert(0, str(Path(__file__).parents[1]))
import server


class ResultsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_root = Path(tempfile.mkdtemp())
        server.RESULTS_ROOT = cls.results_root
        cls.httpd = server.socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0), server.SDNRequestHandler
        )
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, msg, headers, newurl):
            return None

    def request(self, path, method="GET", data=None):
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        opener = urllib.request.build_opener(self.NoRedirect())
        try:
            response = opener.open(request, timeout=3)
            return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def create_result(self, condition="A1", failed=False, incomplete=False):
        recorder = ExperimentResultRecorder(condition, 10, self.results_root)
        recorder.record({
            "cycle": 0,
            "latency_ms": 6.2,
            "throughput_kbps": 950.0,
            "loss_pct": 0.05,
            "reward": 0.35,
            "installed_action": "no_op",
            "requested_action": "no_op",
        }, {"condition": condition})

        if incomplete:
            # Leave open/running without finalizing summary
            return recorder.run_id

        if failed:
            recorder.fail(RuntimeError("evaluation crash simulation"))
        else:
            recorder.complete()
        return recorder.run_id

    def test_dashboard_loads_without_auth_and_serves_results_script(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIsNone(headers.get("Location"))
        # Verify script inclusion
        self.assertIn(b'src="js/results.js"', body)
        self.assertIn(b'id="resultsEmptyState"', body)
        self.assertIn(b'id="resultsPopulatedState"', body)
        self.assertIn(b'id="btnRefreshResults"', body)
        self.assertIn(b'No saved experiment results yet', body)

        # Verify static serving of results.js
        status, _, script_body = self.request("/js/results.js")
        self.assertEqual(status, 200)
        self.assertIn(b"ExperimentResultsManager", script_body)

    def test_empty_results_state_display(self):
        # With no runs in temp results root
        status, _, body = self.request("/api/results")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])

    def test_valid_a0_a1_a2_results_and_comparison_api(self):
        run_a0 = self.create_result("A0")
        run_a1 = self.create_result("A1")
        run_a2 = self.create_result("A2")

        status, _, body = self.request("/api/results")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        run_ids = [r["run_id"] for r in data["results"]]
        self.assertIn(run_a0, run_ids)
        self.assertIn(run_a1, run_ids)
        self.assertIn(run_a2, run_ids)

        # Test compare endpoint
        status, _, comp_body = self.request(f"/api/results/compare?run_ids={run_a0},{run_a1},{run_a2}")
        self.assertEqual(status, 200)
        comp_data = json.loads(comp_body.decode("utf-8"))
        self.assertEqual(len(comp_data["results"]), 3)
        stages = [item["run"]["experiment"]["stage"] for item in comp_data["results"]]
        self.assertIn("A0", stages)
        self.assertIn("A1", stages)
        self.assertIn("A2", stages)

    def test_provenance_is_visible_and_correct(self):
        run_id = self.create_result("A1")
        status, _, body = self.request(f"/api/results/{run_id}/summary")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["run"]["provenance"], "live")
        self.assertEqual(data["summary"]["provenance"], "live")

    def test_missing_metrics_are_not_rendered_as_zero(self):
        run_id = self.create_result("A2")
        status, _, body = self.request(f"/api/results/{run_id}/summary")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        metrics = data["summary"]["metrics"]

        # p95_latency_ms and queue_mbit are not collected by standard harness
        self.assertEqual(metrics["p95_latency_ms"]["status"], "unavailable")
        self.assertIsNone(metrics["p95_latency_ms"]["value"])
        self.assertNotEqual(metrics["p95_latency_ms"]["value"], 0)

        self.assertEqual(metrics["queue_mbit"]["status"], "unavailable")
        self.assertIsNone(metrics["queue_mbit"]["value"])
        self.assertNotEqual(metrics["queue_mbit"]["value"], 0)

    def test_failed_or_incomplete_runs_are_not_successful(self):
        failed_id = self.create_result("A2", failed=True)
        status, _, body = self.request(f"/api/results/{failed_id}/summary")
        self.assertEqual(status, 409)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["run"]["status"], "failed")
        self.assertIn("error", data)

        # Incomplete run cannot be compared
        incomplete_id = self.create_result("A1", incomplete=True)
        status, _, body = self.request(f"/api/results/{incomplete_id}/summary")
        self.assertEqual(status, 409)

        # Comparison with failed run must return 409
        valid_id = self.create_result("A0")
        status, _, comp_body = self.request(f"/api/results/compare?run_ids={valid_id},{failed_id}")
        self.assertEqual(status, 409)
        self.assertIn(b"all comparison runs must be completed with summaries", comp_body)

    def test_api_errors_and_safe_traversal_protection(self):
        # 404 for missing run
        status, _, body = self.request("/api/results/nonexistent-run/summary")
        self.assertEqual(status, 404)

        # Path traversal rejected
        status, _, _ = self.request("/api/results/..%2F..%2Fetc/summary")
        self.assertEqual(status, 404)

        # Network write routes remain disabled
        status, _, body = self.request("/api/action/reroute", method="POST", data=b"{}")
        self.assertEqual(status, 409)
        self.assertIn(b"disabled", body)

        status, _, _ = self.request("/api/ryu/stats/switches")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
