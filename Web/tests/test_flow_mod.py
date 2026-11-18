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


class FlowModAndPhaseSpaceTests(unittest.TestCase):
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

    def test_flow_mod_table_listing(self):
        status, _, body = self._get("/api/studio/flow-mod/table")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("s1", body["switches"])
        self.assertIn("s1", body["flow_tables"])
        self.assertGreaterEqual(body["total_rules"], 4)

    def test_flow_mod_validation_allowed(self):
        payload = {
            "dpid": "s1",
            "priority": 32768,
            "match": {"in_port": 1, "eth_type": "0x0800", "ipv4_dst": "10.0.0.2/32"},
            "action": "OUTPUT:4",
            "meter_rate": 6.0
        }
        status, _, body = self._post("/api/studio/flow-mod/validate", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["verdict"], "ALLOWED")
        self.assertEqual(body["safety_score"], 100)
        self.assertIn("openflow_binary_preview", body)
        self.assertIn("hex_dump", body["openflow_binary_preview"])

    def test_flow_mod_validation_loop_veto(self):
        payload = {
            "dpid": "s2",
            "priority": 32768,
            "match": {"in_port": 1, "eth_type": "0x0800", "ipv4_dst": "10.0.0.2/32"},
            "action": "OUTPUT:3",
            "meter_rate": 0.0
        }
        status, _, body = self._post("/api/studio/flow-mod/validate", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["verdict"], "VETOED")
        self.assertIsNotNone(body["veto_reason"])
        self.assertTrue(any(c["status"] == "VETO" for c in body["checks"]))

    def test_flow_mod_validation_meter_rate_veto(self):
        payload = {
            "dpid": "s1",
            "priority": 32768,
            "match": {"in_port": 1, "eth_type": "0x0800", "ipv4_dst": "10.0.0.2/32"},
            "action": "OUTPUT:3",
            "meter_rate": 25.0
        }
        status, _, body = self._post("/api/studio/flow-mod/validate", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["verdict"], "VETOED")

    def test_flow_mod_inject_requires_auth(self):
        payload = {
            "dpid": "s1",
            "priority": 32768,
            "match": {"eth_type": "0x0800", "ipv4_dst": "10.0.0.5/32"},
            "action": "OUTPUT:4"
        }
        status, _, body = self._post("/api/studio/flow-mod/inject", payload)
        self.assertEqual(status, 403)
        self.assertIn("error", body)

    def test_flow_mod_inject_authorized_operator(self):
        headers = {"Authorization": "Bearer demo_token_operator_2026"}
        payload = {
            "dpid": "s1",
            "priority": 32768,
            "match": {"eth_type": "0x0800", "ipv4_dst": "10.0.0.5/32"},
            "action": "OUTPUT:4",
            "meter_rate": 5.0
        }
        status, _, body = self._post("/api/studio/flow-mod/inject", payload, headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIn("installed_rule_id", body)
        self.assertEqual(body["dpid"], "s1")

    def test_phase_space_coordinates(self):
        status, _, body = self._get("/api/studio/phase-space")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        coords = body["current_coordinates"]
        self.assertIn("Q_backlog_mbit", coords)
        self.assertIn("drift_rate_mbit2_s", coords)
        self.assertIn("stability_verdict", coords)
        self.assertIn("trajectory_history", body)
        self.assertGreaterEqual(len(body["trajectory_history"]), 1)


if __name__ == "__main__":
    unittest.main()
