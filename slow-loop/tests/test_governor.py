"""Governor cycle, scripted SDN case, and one closed loop against a frozen policy."""

from __future__ import annotations

import math
import unittest

from agentic.benchmark import run_benchmark, run_loop, scripted_telemetry
from agentic.governor import Governor
from agentic.model_client import MockModel
from agentic.replay import ReplayBuffer
from agentic.schemas import Experience, Policy, initial_policy, initial_telemetry


class _BadModel:
    def complete(self, messages: list[dict[str, str]]) -> str:
        return "not json at all"


class GovernorTests(unittest.TestCase):
    def test_scripted_case_raises_latency_weight_and_keeps_reroute(self) -> None:
        policy = initial_policy()
        result = Governor(MockModel(), ReplayBuffer()).step(scripted_telemetry(policy), policy, mode="multi")
        self.assertTrue(result.valid_json)
        self.assertTrue(result.accepted)
        self.assertGreater(result.policy_after.latency, policy.latency + 0.02)
        self.assertIn("reroute", result.policy_after.action_mask)

    def test_invalid_json_keeps_the_previous_policy(self) -> None:
        policy = initial_policy()
        result = Governor(_BadModel(), ReplayBuffer()).step(initial_telemetry(policy), policy, mode="single")
        self.assertFalse(result.valid_json)
        self.assertFalse(result.accepted)
        self.assertEqual(result.policy_after, policy)

    def test_invalid_json_can_fall_back_to_a_clipped_rl_step(self) -> None:
        policy = initial_policy()
        better = Policy(
            V=28.0,
            latency=0.30,
            throughput=0.18,
            loss=0.22,
            energy=0.20,
            resource=0.10,
            action_mask=policy.action_mask,
        )
        state = scripted_telemetry(policy)
        buffer = ReplayBuffer()
        for _ in range(3):
            buffer.add(Experience(state, better, 0.4, state, "latency fell after reroute"))
        result = Governor(_BadModel(), buffer).step(state, policy, mode="multi")
        self.assertFalse(result.valid_json)
        self.assertTrue(result.accepted)
        self.assertIn("rl baseline", result.reason)
        self.assertGreater(result.policy_after.V, policy.V)
        self.assertLessEqual(result.policy_after.V - policy.V, 20.0 + 1e-6)

    def test_closed_loop_beats_frozen_policy_and_holdout_runs(self) -> None:
        report = run_benchmark(episodes=6, mode="multi", client=MockModel(), seed=1729)
        self.assertEqual(report["validity_rate"], 1.0)
        self.assertTrue(report["scripted_reasoning_pass"])
        self.assertTrue(report["closed_loop_ok"])
        self.assertLess(report["learned"]["latency_ms"], report["frozen"]["latency_ms"])
        self.assertLess(report["learned"]["sla_violations"], report["frozen"]["sla_violations"])
        self.assertTrue(math.isfinite(report["holdout"]["latency_ms"]))
        self.assertGreaterEqual(report["governor_p95_ms"], report["governor_p50_ms"])

        single = run_loop(episodes=4, seed=1729, profile="holdout", mode="single", learn=True)
        self.assertEqual(single["validity_rate"], 1.0)
        self.assertTrue(math.isfinite(single["loss_pct"]))


if __name__ == "__main__":
    unittest.main()
