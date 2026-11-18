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
from selfx.models.openrouter_asian import (
    ASIAN_MODEL_CATALOG,
    BENCHMARK_COMPARISONS,
    OpenRouterAsianClient,
    parse_policy_delta,
    query_asian_model
)


class AsianModelsApiTests(unittest.TestCase):
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

    def test_asian_models_catalog_endpoint(self):
        status, _, body = self._get("/api/asian-models/catalog")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("catalog", body)
        self.assertGreaterEqual(body["total_models"], 8)

        catalog = body["catalog"]
        self.assertIn("deepseek/deepseek-r1", catalog)
        self.assertIn("deepseek/deepseek-chat", catalog)
        self.assertIn("qwen/qwen-2.5-72b-instruct", catalog)
        self.assertIn("01-ai/yi-lightning", catalog)
        self.assertIn("zhipu/glm-4-9b-chat:free", catalog)

        # Verify MLA savings documented
        r1 = catalog["deepseek/deepseek-r1"]
        self.assertIn("MLA", r1["architecture"])
        self.assertIn("93.3%", r1["kv_cache_compression"])

    def test_asian_models_benchmark_endpoint(self):
        status, _, body = self._get("/api/asian-models/benchmark")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("benchmarks", body)
        self.assertGreaterEqual(len(body["benchmarks"]), 10)

        controllers = [b["controller"] for b in body["benchmarks"]]
        self.assertTrue(any("DeepSeek-R1" in c for c in controllers))
        self.assertTrue(any("Qwen 2.5 72B" in c for c in controllers))
        self.assertTrue(any("Pure Lyapunov DPP" in c for c in controllers))

    def test_asian_models_query_endpoint(self):
        payload = {
            "model_id": "deepseek/deepseek-r1:free",
            "state": {
                "background_mbps": 3.0,
                "bulk_mbps": 14.0,
                "q1_mbit": 1.75,
                "q2_mbit": 0.10,
                "current_v": 8.0
            }
        }
        status, _, body = self._post("/api/asian-models/query", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["model_id"], "deepseek/deepseek-r1:free")
        self.assertIn("policy_delta", body)
        delta = body["policy_delta"]
        self.assertIn("reasoning_trace", delta)
        self.assertIn("delta_V", delta)
        self.assertIn("delta_weights", delta)
        self.assertIn("meter_rate_mbps", delta)
        self.assertTrue(delta["safety_envelope_satisfied"])
        self.assertFalse(body["meter_check"]["allowed"])
        self.assertIn("57.1%", body["meter_check"]["reason"])

        payload["state"].update(bulk_mbps=5.0, q1_mbit=0.2)
        status, _, body = self._post("/api/asian-models/query", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["meter_check"]["allowed"])

    def test_asian_models_query_rejects_invalid_bulk_demand(self):
        for value in (-1, "5", None, float("inf"), True, 1e308):
            with self.subTest(value=value):
                status, _, body = self._post("/api/asian-models/query", {
                    "model_id": "deepseek/deepseek-r1:free",
                    "state": {"bulk_mbps": value},
                })
                self.assertEqual(status, 400)
                self.assertFalse(body["success"])

    def test_policy_delta_parser_safety_clamping(self):
        # Exaggerated delta_V clamped
        bad_json = '{"delta_V": 100.0, "delta_weights": [5.0, 5.0, 5.0, 5.0, 5.0], "meter_rate_mbps": 999.0}'
        parsed = parse_policy_delta(bad_json)
        self.assertLessEqual(parsed["delta_V"], 4.0)
        self.assertLessEqual(parsed["meter_rate_mbps"], 10.0)
        for w in parsed["delta_weights"]:
            self.assertLessEqual(w, 0.20)


if __name__ == "__main__":
    unittest.main()
