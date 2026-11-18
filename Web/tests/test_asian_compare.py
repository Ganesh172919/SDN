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


class AsianModelsCompareTests(unittest.TestCase):
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

    def test_compare_elephant_surge(self):
        payload = {"scenario": "elephant_surge"}
        status, _, body = self._post("/api/asian-models/compare", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["scenario"], "elephant_surge")
        models = body["models_comparison"]
        self.assertEqual(len(models), 5)

        r1 = next(m for m in models if m["id"] == "deepseek/deepseek-r1")
        self.assertIn("reasoning_trace", r1)
        self.assertIn("Delta L", r1["reasoning_trace"])
        self.assertEqual(r1["kv_cache_mb"], 172)

        v3 = next(m for m in models if m["id"] == "deepseek/deepseek-chat")
        self.assertGreaterEqual(v3["tok_per_sec"], 100.0)

        smol = next(m for m in models if m["id"] == "local/smollm2-135m")
        self.assertLess(smol["latency_ms"], 1.0)

    def test_compare_link_flap(self):
        payload = {"scenario": "link_flap"}
        status, _, body = self._post("/api/asian-models/compare", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["scenario"], "link_flap")
        self.assertIn("s1-s2", body["scenario_description"])

    def test_compare_microburst(self):
        payload = {"scenario": "microburst"}
        status, _, body = self._post("/api/asian-models/compare", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["scenario"], "microburst")

    def test_compare_empty_defaults(self):
        status, _, body = self._post("/api/asian-models/compare", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["scenario"], "elephant_surge")
        self.assertIn("mla_efficiency_advantage", body)
        self.assertIn("93.3%", body["mla_efficiency_advantage"]["compression_ratio"])


if __name__ == "__main__":
    unittest.main()
