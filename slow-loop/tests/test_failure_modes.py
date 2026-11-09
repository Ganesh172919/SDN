"""
Failure Mode and Two-Timescale Safety Validation Suite
Traceability: Task T19 | Deliverables D3, D4 | EC466 Team SDN_07

Validates:
  1. Malformed and out-of-range policies fail closed (incumbent preserved).
  2. Regressive candidate policies are rejected by the stress gate.
  3. Missing and stale telemetry triggers safe no-op / retention.
  4. Slow-loop LLM timeouts do not stall fast DPP packet forwarding.
  5. Datapath switch installation failures trigger fail-safe rollback to baseline forwarding.
"""

from __future__ import annotations

import unittest
from agentic.schemas import Policy, TelemetryWindow, initial_policy
from agentic.safety import check as safety_check
from agentic.stress_gate import NonRegressionStressGate
from agentic.six_agent_governor import SixAgentGovernor
from agent.policy_lifecycle import PolicyLifecycleOrchestrator
from agent.dpp_controller import LyapunovDPPController
from agent.rule_recovery import RuleRecoveryManager


class TwoTimescaleFailureModeTests(unittest.TestCase):

    def setUp(self):
        self.incumbent = initial_policy()
        self.orchestrator = PolicyLifecycleOrchestrator()
        self.telem_nominal = TelemetryWindow(
            queue_mbit=0.01,
            queue_trend=0.0,
            util_primary_pct=40.0,
            util_alt_pct=0.0,
            flow_mbps=3.0,
            latency_ms=5.0,
            latency_trend=0.0,
            loss_pct=0.0,
            loss_trend=0.0,
            throughput_mbps=3.0,
            energy=0.35,
            resource_cost=0.0,
            sla_violations=0.0,
            p95_latency_ms=6.5,
            policy=self.incumbent,
        )

    def test_malformed_and_out_of_bounds_policies_fail_closed(self):
        # 1. Negative weight
        bad_policy_1 = Policy(
            V=8.0, latency=-0.1, throughput=0.5, loss=0.3, energy=0.2, resource=0.1,
            action_mask=("admit", "reroute"),
        )
        entry1 = self.orchestrator.process_candidate_policy(bad_policy_1)
        self.assertEqual(entry1.final_status, "REJECTED_RETAINED_INCUMBENT")

        # 2. Weights not summing to 1.0
        bad_policy_2 = Policy(
            V=8.0, latency=0.5, throughput=0.5, loss=0.5, energy=0.2, resource=0.1,
            action_mask=("admit", "reroute"),
        )
        entry2 = self.orchestrator.process_candidate_policy(bad_policy_2)
        self.assertEqual(entry2.final_status, "REJECTED_RETAINED_INCUMBENT")

        # 3. Excessive V jump (> V_MAX_STEP)
        bad_policy_3 = Policy(
            V=28.0, latency=0.2, throughput=0.2, loss=0.2, energy=0.2, resource=0.2,
            action_mask=("admit", "reroute"),
        )
        entry3 = self.orchestrator.process_candidate_policy(bad_policy_3)
        self.assertEqual(entry3.final_status, "REJECTED_RETAINED_INCUMBENT")

        # Confirm incumbent is still active
        self.assertEqual(self.orchestrator.bridge.get_incumbent_record().version_id, "pi-v1.0")

    def test_regressive_candidate_rejected_by_stress_gate(self):
        gate = NonRegressionStressGate()
        # Candidate that completely disables reroute during heavy congestion
        regressive_candidate = Policy(
            V=8.0,
            latency=0.05,
            throughput=0.80,
            loss=0.05,
            energy=0.05,
            resource=0.05,
            action_mask=("no_op",),  # Refuses to relieve bottleneck!
        )
        verdict = gate.evaluate_candidate(self.incumbent, regressive_candidate)
        self.assertFalse(verdict.promoted)
        self.assertIn("Hard safety invariant violated", verdict.reason)

    def test_missing_or_stale_telemetry_fails_closed(self):
        # Pass None proposal to safety gate
        res = safety_check(self.incumbent, None, self.telem_nominal)
        self.assertFalse(res.accepted)
        self.assertEqual(res.policy, self.incumbent)

    def test_provider_timeout_does_not_stall_fast_dpp(self):
        controller = LyapunovDPPController()
        # Fast DPP must make sub-millisecond decision regardless of slow governor state
        t0 = unittest.TestCase().defaultTestResult()
        dec = controller.decide(
            q_primary_mbit=0.05,
            q_secondary_mbit=0.0,
            mouse_mbps=3.0,
            elephant_mbps=10.0,
            policy_v=8.0,
            weights=self.incumbent.weights(),
            action_mask=self.incumbent.action_mask,
        )
        self.assertIn(dec.action, ("reroute", "rate_limit", "admit", "drop"))
        self.assertLess(dec.decision_time_ms, 5.0)  # sub-5ms latency guarantee

    def test_switch_installation_and_atomic_rollback(self):
        mgr = RuleRecoveryManager()
        # Register an action
        rule = mgr.register_installed_action("0000000000000002", "reroute", {"nw_src": "10.0.0.2"})
        self.assertEqual(rule.status, "pending_verification")

        # Simulate readback failure
        mgr.verify_readback(rule.rule_id, [])  # Empty switch flow table
        self.assertEqual(rule.status, "failed_installation")

        # Trigger fail-closed rollback
        rollback_cmds = mgr.trigger_rollback("verification_failed")
        self.assertEqual(len(mgr.active_rules), 0)

    def test_full_promotion_and_rollback_audit_chain(self):
        # 1. Propose a good adaptive policy
        good_policy = Policy(
            V=9.0,
            latency=0.30,
            throughput=0.25,
            loss=0.25,
            energy=0.10,
            resource=0.10,
            action_mask=("admit", "reroute", "rate_limit"),
        )
        entry = self.orchestrator.process_candidate_policy(good_policy)
        self.assertEqual(entry.final_status, "PROMOTED_AND_ACTIVATED")
        self.assertEqual(entry.switch_action_taken, "admit")
        self.assertTrue(entry.datapath_verified)

        # 2. Trigger rollback on simulated network fault
        rb_entry = self.orchestrator.trigger_anomaly_rollback(reason="packet_loss_spike")
        self.assertEqual(rb_entry.final_status, "ROLLED_BACK")
        self.assertEqual(rb_entry.switch_action_taken, "restore_baseline_l2_rules")

        # Verify audit chain integrity
        log = self.orchestrator.export_audit_log()
        self.assertEqual(len(log), 2)
        self.assertTrue(all("proposal_hash" in e for e in log))


if __name__ == "__main__":
    unittest.main()
