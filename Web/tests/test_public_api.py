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

sys.path.insert(0, str(Path(__file__).parents[1]))
import server


class PublicApiTests(unittest.TestCase):
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

    def create_result(self, condition="A1", failed=False):
        recorder = ExperimentResultRecorder(condition, 5, self.results_root)
        recorder.record({
            "cycle": 0,
            "latency_ms": 5.0,
            "throughput_kbps": 800.0,
            "loss_pct": 0.0,
            "reward": 0.25,
            "installed_action": "no_op",
            "requested_action": "no_op",
        }, {"condition": condition})
        if failed:
            recorder.fail(RuntimeError("test failure"))
        else:
            recorder.complete()
        return recorder.run_id

    def test_dashboard_and_status_are_public(self):
        status, headers, _ = self.request("/")
        self.assertEqual(status, 200)
        self.assertIsNone(headers.get("Location"))
        status, _, body = self.request("/api/status")
        self.assertEqual(status, 200)
        self.assertNotIn(b"ryu_base_url", body)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("testbed_mode", data)
        self.assertIn("testbed_message", data)
        self.assertIn("benchmarks_available", data)
        self.assertIn(data["testbed_mode"], ("live", "offline"))

    def test_login_is_retired(self):
        status, headers, _ = self.request("/login")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/")

    def test_result_index_summary_metrics_and_trace(self):
        run_id = self.create_result("A1")
        status, _, body = self.request("/api/results")
        self.assertEqual(status, 200)
        self.assertIn(run_id.encode(), body)

        status, _, body = self.request(f"/api/results/{run_id}/summary")
        self.assertEqual(status, 200)
        self.assertIn(b"summary", body)
        self.assertIn(b"live", body)

        status, _, body = self.request(f"/api/results/{run_id}/metrics")
        self.assertEqual(status, 200)
        self.assertIn(b"latency_ms", body)

        status, _, body = self.request(f"/api/results/{run_id}/trace")
        self.assertEqual(status, 200)
        self.assertIn(b"control_cycle", body)

        second_run_id = self.create_result("A2")
        status, _, body = self.request(f"/api/results/compare?run_ids={run_id},{second_run_id}")
        self.assertEqual(status, 200)
        self.assertIn(run_id.encode(), body)
        self.assertIn(second_run_id.encode(), body)

    def test_missing_malformed_and_failed_runs_are_explicit(self):
        status, _, _ = self.request("/api/results/missing/summary")
        self.assertEqual(status, 404)

        malformed = self.results_root / "malformed"
        malformed.mkdir()
        (malformed / "run.json").write_text("{}", encoding="utf-8")
        status, _, body = self.request("/api/results/malformed/summary")
        self.assertEqual(status, 422)
        self.assertNotIn(str(self.results_root).encode(), body)

        run_id = self.create_result("A2", failed=True)
        status, _, body = self.request(f"/api/results/{run_id}/summary")
        self.assertEqual(status, 409)
        self.assertIn(b"failed", body)

    def test_path_traversal_and_secrets_are_not_exposed(self):
        status, _, _ = self.request("/api/results/%2e%2e/summary")
        self.assertEqual(status, 404)

        secret_dir = self.results_root / "secret-run"
        secret_dir.mkdir()
        (secret_dir / "run.json").write_text(json.dumps({"api_key": "DO-NOT-RETURN"}), encoding="utf-8")
        status, _, body = self.request("/api/results/secret-run/summary")
        self.assertEqual(status, 422)
        self.assertNotIn(b"DO-NOT-RETURN", body)

    def test_network_changing_routes_remain_disabled(self):
        status, _, body = self.request("/api/action/reroute", method="POST", data=b"{}")
        self.assertEqual(status, 409)
        self.assertIn(b"disabled", body)
        status, _, _ = self.request("/api/ryu/stats/flowentry/add", method="POST", data=b"{}")
        self.assertEqual(status, 409)

    def test_benchmarks_summary(self):
        status, headers, body = self.request("/api/benchmarks/summary")
        self.assertEqual(status, 200)
        self.assertIn(b"window_count", body)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("window_count"), 86400)
        self.assertIn("A4", data.get("controllers", {}))
        self.assertIn("mixed", data.get("groups", {}))

        # Test safe missing file handling
        orig = server.BENCHMARKS_V4_SUMMARY
        try:
            server.BENCHMARKS_V4_SUMMARY = Path("D:/SDN/non_existent_summary.json")
            m_status, _, m_body = self.request("/api/benchmarks/summary")
            self.assertEqual(m_status, 404)

            # Test malformed JSON
            temp_malformed = self.results_root / "bad_summary.json"
            temp_malformed.write_text("{not valid json", encoding="utf-8")
            server.BENCHMARKS_V4_SUMMARY = temp_malformed
            bad_status, _, _ = self.request("/api/benchmarks/summary")
            self.assertEqual(bad_status, 502)

            # Test incomplete payload schema
            temp_malformed.write_text(json.dumps({"some_key": 123}), encoding="utf-8")
            inc_status, _, _ = self.request("/api/benchmarks/summary")
            self.assertEqual(inc_status, 502)
        finally:
            server.BENCHMARKS_V4_SUMMARY = orig

    def test_benchmarks_llm_diagnostics(self):
        status, headers, body = self.request("/api/benchmarks/llm-diagnostics")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("provenance"), "LLM API Diagnostic Check")
        self.assertTrue("gemini_v4" in data.get("runs", {}) or "openrouter_v4" in data.get("runs", {}))


if __name__ == "__main__":
    unittest.main()