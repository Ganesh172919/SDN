"""
Phase 4 — reward computation.

reward = weighted combination of (delta-latency, delta-throughput, delta-loss)
measured between the state right before an action and the state one
observation window later, per the architecture section of the spec.

All three deltas are normalized to roughly comparable scales before
weighting so that, e.g., a latency swing measured in milliseconds
doesn't dwarf a throughput swing measured in kbps. Signs are chosen so
that a HIGHER reward is always better:
  - throughput going up   -> positive contribution
  - latency going up      -> negative contribution
  - loss going up         -> negative contribution
"""

from dataclasses import dataclass

import config


@dataclass
class CycleMetrics:
    latency_ms: float
    throughput_kbps: float
    loss_pct: float


@dataclass
class RewardBreakdown:
    delta_latency_ms: float
    delta_throughput_kbps: float
    delta_loss_pct: float
    reward: float


def compute_reward(before: CycleMetrics, after: CycleMetrics) -> RewardBreakdown:
    delta_latency = after.latency_ms - before.latency_ms
    delta_throughput = after.throughput_kbps - before.throughput_kbps
    delta_loss = after.loss_pct - before.loss_pct

    # normalize: latency in ms (typically 0-100 range on an emulated
    # topology), throughput in kbps (typically 0-10000 range for a
    # 10 Mbps link), loss in percentage points (0-100). Divide each
    # delta by a characteristic scale so weights are comparable.
    norm_latency = delta_latency / 50.0
    norm_throughput = delta_throughput / 5000.0
    norm_loss = delta_loss / 20.0

    reward = (
        config.REWARD_WEIGHT_LATENCY * norm_latency
        + config.REWARD_WEIGHT_THROUGHPUT * norm_throughput
        + config.REWARD_WEIGHT_LOSS * norm_loss
    )

    return RewardBreakdown(
        delta_latency_ms=delta_latency,
        delta_throughput_kbps=delta_throughput,
        delta_loss_pct=delta_loss,
        reward=reward,
    )
