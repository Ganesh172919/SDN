import json
import os
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import unittest
import socketserver
from pathlib import Path

import sys
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(WEB_DIR)
for p in (PROJECT_ROOT, WEB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import SDNRequestHandler


class NewFeaturesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), SDNRequestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        req = Request(f"http://127.0.0.1:{self.port}{path}")
        with urlopen(req, timeout=3.0) as resp:
            data = resp.read()
            return resp.status, resp.headers, json.loads(data.decode("utf-8"))

    def _get_raw(self, path):
        req = Request(f"http://127.0.0.1:{self.port}{path}")
        with urlopen(req, timeout=3.0) as resp:
            return resp.status, resp.headers, resp.read()

    def test_comparison_configs_endpoint(self):
        status, headers, body = self._get("/api/comparison/configs")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("count"), 14)
        configs = body.get("configs", [])
        self.assertEqual(len(configs), 14)
        config_ids = {c["id"] for c in configs}
        self.assertIn("S0", config_ids)
        self.assertIn("S5", config_ids)
        self.assertIn("dqn", config_ids)
        self.assertIn("marl", config_ids)
        self.assertIn("threshold", config_ids)
        for c in configs:
            self.assertIn("label", c)
            self.assertIn("family", c)
            self.assertIn("description", c)

    def test_comparison_effects_endpoint(self):
        status, headers, body = self._get("/api/comparison/effects")
        self.assertEqual(status, 200)
        self.assertIn("agentic", body)
        self.assertIn("comparisons", body)
        comparisons = body["comparisons"]
        self.assertIn("S0", comparisons)
        self.assertIn("changes", comparisons["S0"])
        self.assertIn("latency_ms", comparisons["S0"]["changes"])
        self.assertIn("ci95", comparisons["S0"]["changes"]["latency_ms"])

    def test_comparison_runs_summary(self):
        status, headers, body = self._get("/api/comparison/runs?summary_only=true")
        self.assertEqual(status, 200)
        self.assertIn("total_runs", body)
        self.assertIn("summary", body)
        summary = body["summary"]
        self.assertGreater(len(summary), 0)
        first = summary[0]
        self.assertIn("configuration", first)
        self.assertIn("mean_latency_ms", first)
        self.assertIn("mean_goodput_mbps", first)
        self.assertIn("mean_loss_pct", first)
        self.assertIn("mean_reward", first)

    def test_comparison_runs_filtered(self):
        status, headers, body = self._get("/api/comparison/runs?configs=S0,S5")
        self.assertEqual(status, 200)
        runs = body.get("runs", [])
        self.assertGreater(len(runs), 0)
        for r in runs:
            self.assertIn(r["configuration"], {"S0", "S5"})
            self.assertIn("windows", r)
            self.assertGreater(len(r["windows"]), 0)

    def test_topologies_list(self):
        status, headers, body = self._get("/api/topologies")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        topos = body.get("topologies", [])
        self.assertGreaterEqual(len(topos), 3)
        topo_ids = {t["id"] for t in topos}
        self.assertIn("leaf_spine", topo_ids)
        self.assertIn("linear", topo_ids)
        self.assertIn("unseen_mesh", topo_ids)
        for t in topos:
            self.assertGreater(t["switch_count"], 0)
            self.assertGreater(t["host_count"], 0)

    def test_topology_manifest_leaf_spine(self):
        status, headers, body = self._get("/api/topologies/leaf_spine")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), "leaf_spine")
        self.assertIn("spines", body)
        self.assertIn("leafs", body)
        self.assertIn("hosts", body)
        self.assertIn("links", body)
        self.assertEqual(len(body["spines"]), 2)
        self.assertEqual(len(body["leafs"]), 4)
        self.assertEqual(len(body["hosts"]), 8)

    def test_topology_manifest_linear(self):
        status, headers, body = self._get("/api/topologies/linear")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("id"), "linear")
        self.assertIn("switches", body)
        self.assertIn("hosts", body)

    def test_topology_manifest_invalid_and_traversal(self):
        # Invalid characters
        with self.assertRaises(HTTPError) as ctx:
            self._get("/api/topologies/..%2F..%2Fetc%2Fpasswd")
        self.assertEqual(ctx.exception.code, 400)

        # Nonexistent topology
        with self.assertRaises(HTTPError) as ctx:
            self._get("/api/topologies/nonexistent_topology")
        self.assertEqual(ctx.exception.code, 404)

    def test_traffic_schedules_list(self):
        status, headers, body = self._get("/api/traffic/schedules")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        schedules = body.get("schedules", [])
        self.assertGreaterEqual(len(schedules), 3)
        profiles = {s["profile"] for s in schedules}
        self.assertIn("flash_crowd", profiles)
        self.assertIn("steady_bursty", profiles)
        self.assertIn("volatile_dpp", profiles)

    def test_traffic_schedule_detail(self):
        status, headers, body = self._get("/api/traffic/schedules/flash_crowd")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("profile"), "flash_crowd")
        self.assertIn("events", body)
        self.assertGreater(len(body["events"]), 0)
        first_event = body["events"][0]
        self.assertIn("src", first_event)
        self.assertIn("dst", first_event)
        self.assertIn("rate_mbps", first_event)

    def test_traffic_schedule_invalid_profile(self):
        with self.assertRaises(HTTPError) as ctx:
            self._get("/api/traffic/schedules/bad*profile")
        self.assertEqual(ctx.exception.code, 400)

        with self.assertRaises(HTTPError) as ctx:
            self._get("/api/traffic/schedules/nonexistent_workload")
        self.assertEqual(ctx.exception.code, 404)

    def test_analytics_dpp(self):
        status, headers, body = self._get("/api/analytics/dpp")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertIn("acceptance", body)
        self.assertIn("v_tradeoff", body)
        acceptance = body["acceptance"]
        self.assertEqual(acceptance.get("overall_status"), "PASS")
        self.assertIn("profiles", acceptance)
        v_tradeoff = body["v_tradeoff"]
        self.assertIn("results", v_tradeoff)
        self.assertGreater(len(v_tradeoff["results"]), 0)

    def test_analytics_statistics(self):
        status, headers, body = self._get("/api/analytics/statistics")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertIn("paired_ttest", body)
        ttest = body["paired_ttest"]
        self.assertIn("t_statistic", ttest)
        self.assertIn("p_value", ttest)
        self.assertIn("cohens_d_effect_size", ttest)
        self.assertIn("seed_pairs", ttest)
        self.assertEqual(len(ttest["seed_pairs"]), 10)

    def test_analytics_lora(self):
        status, headers, body = self._get("/api/analytics/lora")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        self.assertIn("config", body)
        self.assertIn("steps", body)
        config = body["config"]
        self.assertEqual(config.get("hyperparameters", {}).get("rank"), 8)
        self.assertEqual(config.get("hyperparameters", {}).get("alpha"), 16)
        self.assertEqual(config.get("trainable_parameters"), 460800)
        steps = body["steps"]
        self.assertGreaterEqual(len(steps), 50)
        first_step = steps[0]
        self.assertIn("step", first_step)
        self.assertIn("loss", first_step)
        self.assertIn("gradient_norm", first_step)

    def test_status_reports_new_features(self):
        status, headers, body = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("comparison_available"))
        self.assertTrue(body.get("topologies_available"))
        self.assertTrue(body.get("traffic_schedules_available"))
        self.assertTrue(body.get("analytics_available"))


if __name__ == "__main__":
    unittest.main()
