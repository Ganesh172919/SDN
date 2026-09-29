"""Fail-closed checks on policy updates."""

from __future__ import annotations

import unittest

from agentic.safety import check
from agentic.schemas import Policy, initial_policy, initial_telemetry


class SafetyTests(unittest.TestCase):
    def test_rejects_large_v_step(self) -> None:
        current = initial_policy()
        proposed = Policy(
            V=current.V + 50,
            action_mask=current.action_mask,
            **current.weights(),
        )
        decision = check(current, proposed, initial_telemetry(current))
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.policy, current)

    def test_rejects_weights_that_do_not_sum_to_one(self) -> None:
        current = initial_policy()
        proposed = Policy(
            V=current.V,
            latency=0.4,
            throughput=0.4,
            loss=0.4,
            energy=0.4,
            resource=0.4,
            action_mask=current.action_mask,
        )
        decision = check(current, proposed, initial_telemetry(current))
        self.assertFalse(decision.accepted)

    def test_rejects_empty_mask(self) -> None:
        current = initial_policy()
        proposed = Policy(V=current.V, action_mask=(), **current.weights())
        decision = check(current, proposed, initial_telemetry(current))
        self.assertFalse(decision.accepted)
        self.assertIn("empty", decision.reason)

    def test_rejects_new_drop_while_healthy(self) -> None:
        current = Policy(
            V=8.0,
            latency=0.10,
            throughput=0.25,
            loss=0.15,
            energy=0.35,
            resource=0.15,
            action_mask=("admit", "rate_limit", "reroute"),
        )
        proposed = Policy(
            V=8.0,
            action_mask=("admit", "drop", "rate_limit", "reroute"),
            **current.weights(),
        )
        decision = check(current, proposed, initial_telemetry(current))
        self.assertFalse(decision.accepted)
        self.assertIn("drop", decision.reason)

    def test_rejects_estimated_latency_regression(self) -> None:
        current = initial_policy()
        proposed = Policy(
            V=10.0,
            latency=0.12,
            throughput=0.23,
            loss=0.15,
            energy=0.35,
            resource=0.15,
            action_mask=current.action_mask,
        )
        decision = check(current, proposed, initial_telemetry(current), latency_delta_est=30.0)
        self.assertFalse(decision.accepted)
        self.assertIn("latency", decision.reason)

    def test_accepts_a_small_legal_step(self) -> None:
        current = initial_policy()
        proposed = Policy(
            V=12.0,
            latency=0.16,
            throughput=0.22,
            loss=0.16,
            energy=0.31,
            resource=0.15,
            action_mask=current.action_mask,
        )
        decision = check(current, proposed, initial_telemetry(current))
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.policy, proposed)


if __name__ == "__main__":
    unittest.main()
