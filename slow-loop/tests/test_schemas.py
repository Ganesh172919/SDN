"""Schema round-trip and policy-step clipping."""

from __future__ import annotations

import unittest

from agentic.config import V_MAX_STEP, WEIGHT_KEYS, WEIGHT_MAX_STEP
from agentic.schemas import Policy, clip_policy_step, initial_policy


class SchemaTests(unittest.TestCase):
    def test_policy_json_roundtrip(self) -> None:
        policy = initial_policy()
        restored = Policy.from_dict(policy.to_dict())
        self.assertEqual(restored, policy)
        self.assertAlmostEqual(sum(restored.weights().values()), 1.0, places=6)

    def test_clip_limits_v_and_weights(self) -> None:
        current = initial_policy()
        target = Policy(
            V=100.0,
            latency=0.70,
            throughput=0.10,
            loss=0.10,
            energy=0.05,
            resource=0.05,
            action_mask=("admit", "reroute"),
        )
        stepped = clip_policy_step(current, target)
        self.assertLessEqual(stepped.V - current.V, V_MAX_STEP + 1e-6)
        self.assertGreaterEqual(stepped.V, 1.0)
        self.assertLessEqual(stepped.V, 100.0)
        for key in WEIGHT_KEYS:
            self.assertLessEqual(abs(stepped.weight(key) - current.weight(key)), WEIGHT_MAX_STEP + 1e-4)
        self.assertAlmostEqual(sum(stepped.weights().values()), 1.0, places=5)
        self.assertIn("reroute", stepped.action_mask)
        self.assertNotIn("drop", stepped.action_mask)


if __name__ == "__main__":
    unittest.main()
