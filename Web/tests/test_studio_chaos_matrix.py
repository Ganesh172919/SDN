"""
test_studio_chaos_matrix.py - Regression & End-to-End Tests for Testing Studio Export & Chaos Matrix
"""

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


class StudioChaosMatrixTests(unittest.TestCase):
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

    def test_studio_export_report(self):
        """Verify that GET /api/studio/export-report returns an audited signed report JSON."""
        url = f"{self.base_url}/api/studio/export-report"
        req = urllib.request.Request(url, method="GET")
        
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content_type = resp.headers.get("Content-Type", "")
            self.assertIn("application/json", content_type)
            
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["platform"], "SELF-X Autonomous Closed-Loop Traffic Engineering Platform")
            self.assertEqual(body["course"], "EC466 Software Defined Networks")
            self.assertEqual(body["team"], "Team SDN_07")
            self.assertIn("sha256_fingerprint", body)
            self.assertEqual(len(body["sha256_fingerprint"]), 64)
            self.assertEqual(len(body["authors"]), 6)
            self.assertEqual(body["datapath_architecture"]["bit_conserving_fluid_engine"], "ACTIVE")

    def test_studio_chaos_matrix_forbidden_unauthenticated(self):
        """Verify that POST /api/studio/chaos-matrix returns HTTP 403 when unauthenticated."""
        url = f"{self.base_url}/api/studio/chaos-matrix"
        req = urllib.request.Request(
            url,
            data=json.dumps({"suite": "full"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

    def test_studio_chaos_matrix_authorized_admin(self):
        """Verify that POST /api/studio/chaos-matrix returns 4 phases and recovery latencies for admin."""
        url = f"{self.base_url}/api/studio/chaos-matrix"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer demo_token_admin_2026"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps({"suite": "full"}).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(body["success"])
            self.assertEqual(len(body["phases"]), 4)
            self.assertGreater(body["total_recovery_ms"], 0)
            self.assertEqual(body["safety_invariants_preserved"], 4)
            self.assertEqual(body["operator"], "admin")

    def test_asian_models_cost_calculator(self):
        """Verify that GET /api/asian-models/cost-calculator computes correct monthly OPEX."""
        url = f"{self.base_url}/api/asian-models/cost-calculator"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(body["success"])
            self.assertEqual(body["decisions_per_month"], 86400)
            self.assertGreaterEqual(body["max_savings_percentage"], 90.0)
            
            projections = body["projections"]
            self.assertGreaterEqual(len(projections), 6)
            model_names = [p["model_name"] for p in projections]
            self.assertIn("DeepSeek-R1", model_names)
            self.assertIn("DeepSeek-V3", model_names)
            self.assertIn("Qwen 2.5 72B", model_names)


if __name__ == "__main__":
    unittest.main()
