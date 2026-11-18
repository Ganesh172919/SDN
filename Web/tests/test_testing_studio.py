import json
import threading
import unittest
import urllib.request
import urllib.error
import socketserver
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(WEB_DIR)
for p in (PROJECT_ROOT, WEB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import SDNRequestHandler


class TestingStudioApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), SDNRequestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path, payload=None, headers=None):
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        data = json.dumps(payload).encode("utf-8") if payload is not None else b"{}"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status, resp.headers, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, err.headers, json.loads(err.read().decode("utf-8"))

    def _get(self, path, headers=None):
        req_headers = {}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(f"{self.base_url}{path}", headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status, resp.headers, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, err.headers, json.loads(err.read().decode("utf-8"))

    def test_studio_verification_pipeline(self):
        status, _, body = self._post("/api/studio/verify")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["overall_status"], "PASS")
        self.assertIn("stages", body)
        self.assertEqual(len(body["stages"]), 6)

        stage_ids = [s["id"] for s in body["stages"]]
        self.assertIn("port_connectivity", stage_ids)
        self.assertIn("openflow_telemetry", stage_ids)
        self.assertIn("dpp_lyapunov_engine", stage_ids)
        self.assertIn("lora_policy_head", stage_ids)
        self.assertIn("llm_governor", stage_ids)
        self.assertIn("safety_guardrail", stage_ids)

        for stage in body["stages"]:
            self.assertEqual(stage["status"], "PASS")
            self.assertIn("latency_us", stage)
            self.assertIn("details", stage)

    def test_studio_traffic_stress_injection(self):
        # 8 Mbps burst (fits on alternate path 10 Mbps with 90% threshold)
        payload = {"scenario": "elephant_burst", "rate_mbps": 8.0, "duration_s": 10.0}
        status, _, body = self._post("/api/studio/traffic-stress", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("unmanaged_impact", body)
        self.assertIn("selfx_controlled_response", body)
        self.assertEqual(body["selfx_controlled_response"]["status"], "CONVERGED_STABLE")
        self.assertIn("Alternate", body["selfx_controlled_response"]["applied_action"])

        # 12 Mbps burst (exceeds alternate threshold, requires ingress metering)
        payload2 = {"scenario": "elephant_burst", "rate_mbps": 12.0, "duration_s": 10.0}
        status2, _, body2 = self._post("/api/studio/traffic-stress", payload2)
        self.assertEqual(status2, 200)
        self.assertTrue(body2["success"])
        self.assertIn("Metered Ingress", body2["selfx_controlled_response"]["applied_action"])

    def test_studio_chaos_injection(self):
        actions = ["kill_link", "drop_port", "inject_jitter", "restore_all"]
        for act in actions:
            payload = {"action": act, "target": "s1-s2"}
            status, _, body = self._post("/api/studio/chaos", payload)
            self.assertEqual(status, 200)
            self.assertTrue(body["success"])
            self.assertEqual(body["action"], act)
            self.assertIn("failover_latency_ms", body)
            self.assertTrue(body["bit_conservation_verified"])

    def test_studio_lyapunov_parameter_tuning(self):
        payload = {
            "V": 16.0,
            "weights": [0.30, 0.30, 0.20, 0.10, 0.10],
            "meter_rate": 7.5
        }
        status, _, body = self._post("/api/studio/lyapunov-tune", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["V"], 16.0)
        self.assertEqual(body["meter_rate_mbps"], 7.5)
        self.assertIn("theoretical_bounds", body)
        self.assertIn("queue_backlog_bound", body["theoretical_bounds"])

    def test_studio_telemetry_stream(self):
        status, _, body = self._get("/api/studio/telemetry-stream")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("events", body)
        self.assertGreater(len(body["events"]), 0)


if __name__ == "__main__":
    unittest.main()
