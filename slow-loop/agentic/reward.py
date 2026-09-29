"""Multi-objective reward for one slow-loop window.

Higher is better. Latency, loss, energy, and resource increases are
penalized. Throughput increases are rewarded. The weights are the fixed
evaluation weights, not the controller's own objective.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic.config import EVAL_WEIGHTS
from agentic.schemas import TelemetryWindow


@dataclass(frozen=True)
class RewardBreakdown:
    delta_latency_ms: float
    delta_throughput_mbps: float
    delta_loss_pct: float
    delta_energy: float
    delta_resource: float
    delta_sla: float
    reward: float


def compute_reward(before: TelemetryWindow, after: TelemetryWindow) -> RewardBreakdown:
    delta_latency = after.latency_ms - before.latency_ms
    delta_throughput = after.throughput_mbps - before.throughput_mbps
    delta_loss = after.loss_pct - before.loss_pct
    delta_energy = after.energy - before.energy
    delta_resource = after.resource_cost - before.resource_cost
    delta_sla = after.sla_violations - before.sla_violations

    reward = (
        EVAL_WEIGHTS["latency"] * (-delta_latency / 30.0)
        + EVAL_WEIGHTS["throughput"] * (delta_throughput / 8.0)
        + EVAL_WEIGHTS["loss"] * (-delta_loss / 20.0)
        + EVAL_WEIGHTS["energy"] * (-delta_energy / 1.0)
        + EVAL_WEIGHTS["resource"] * (-delta_resource / 1.0)
        - 0.15 * max(0.0, delta_sla)
    )
    return RewardBreakdown(
        delta_latency_ms=delta_latency,
        delta_throughput_mbps=delta_throughput,
        delta_loss_pct=delta_loss,
        delta_energy=delta_energy,
        delta_resource=delta_resource,
        delta_sla=delta_sla,
        reward=reward,
    )


def reflect(before: TelemetryWindow, after: TelemetryWindow, reward: float) -> str:
    """One sentence stored with the experience. No extra model call."""

    movement = "improved" if reward > 0.02 else "hurt" if reward < -0.02 else "held"
    return (
        f"The window {movement} the network: latency {before.latency_ms:.1f} ms to "
        f"{after.latency_ms:.1f} ms, loss {before.loss_pct:.1f}% to {after.loss_pct:.1f}%, "
        f"throughput {before.throughput_mbps:.2f} to {after.throughput_mbps:.2f} Mbps, "
        f"reward {reward:.3f}."
    )
