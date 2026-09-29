"""Reward-weighted updates stay inside the slow-loop step limits."""

from __future__ import annotations

import unittest

from agentic.config import REPLAY_CAPACITY, V_MAX_STEP, WEIGHT_KEYS, WEIGHT_MAX_STEP
from agentic.replay import ReplayBuffer
from agentic.rl import propose_baseline
from agentic.schemas import Experience, Policy, initial_policy
from agentic.benchmark import scripted_telemetry


class RLTests(unittest.TestCase):
    def test_baseline_step_is_clipped(self) -> None:
        current = initial_policy()
        target = Policy(
            V=90.0,
            latency=0.50,
            throughput=0.20,
            loss=0.10,
            energy=0.10,
            resource=0.10,
            action_mask=current.action_mask,
        )
        state = scripted_telemetry(current)
        buffer = ReplayBuffer()
        for _ in range(4):
            buffer.add(Experience(state, target, 1.0, state, "reroute recovered latency"))
        stepped = propose_baseline(current, state, buffer)
        self.assertLessEqual(stepped.V - current.V, V_MAX_STEP + 1e-6)
        self.assertGreater(stepped.V, current.V)
        for key in WEIGHT_KEYS:
            self.assertLessEqual(
                abs(stepped.weight(key) - current.weight(key)),
                WEIGHT_MAX_STEP + 1e-4,
            )
        self.assertAlmostEqual(sum(stepped.weights().values()), 1.0, places=5)

    def test_replay_drops_oldest(self) -> None:
        buffer = ReplayBuffer(capacity=2)
        state = scripted_telemetry()
        policy = initial_policy()
        for reward in (0.1, 0.2, 0.3):
            buffer.add(Experience(state, policy, reward, state, "note"))
        self.assertEqual(len(buffer), 2)
        self.assertEqual([record.reward for record in buffer.all_records()], [0.2, 0.3])
        self.assertLessEqual(2, REPLAY_CAPACITY)


if __name__ == "__main__":
    unittest.main()
