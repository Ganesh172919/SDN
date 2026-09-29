"""Slow-loop contextual bandit over policy parameters.

The fast tick does not train. This module only nudges V and the objective
weights toward accepted policies that earned positive reward in similar
network states.
"""

from __future__ import annotations

from agentic.replay import ReplayBuffer
from agentic.schemas import Policy, TelemetryWindow, clip_policy_step, interpolate_policy


def estimate_latency_delta(
    buffer: ReplayBuffer,
    telemetry: TelemetryWindow,
    min_samples: int = 3,
) -> float | None:
    """Mean observed latency change in similar past states, or None if sparse."""

    neighbors = buffer.similar(telemetry, k=12, min_kernel=0.15)
    if len(neighbors) < min_samples:
        return None
    weight_sum = sum(weight for _, weight in neighbors)
    if weight_sum <= 1e-9:
        return None
    change = sum(
        weight * (record.next_state.latency_ms - record.state.latency_ms)
        for record, weight in neighbors
    )
    return change / weight_sum


def _average_policy(items: list[tuple[Policy, float]]) -> Policy:
    total = sum(weight for _, weight in items)
    v = sum(policy.V * weight for policy, weight in items) / total
    weights = {
        key: sum(policy.weight(key) * weight for policy, weight in items) / total
        for key in ("latency", "throughput", "loss", "energy", "resource")
    }
    best_policy = max(items, key=lambda item: item[1])[0]
    return Policy(
        V=v,
        latency=weights["latency"],
        throughput=weights["throughput"],
        loss=weights["loss"],
        energy=weights["energy"],
        resource=weights["resource"],
        action_mask=best_policy.action_mask,
    )


def propose_baseline(current: Policy, telemetry: TelemetryWindow, buffer: ReplayBuffer) -> Policy:
    """Small clipped step toward high-reward policies in similar states."""

    scored = [
        (record.policy, weight * record.reward)
        for record, weight in buffer.similar(telemetry)
        if record.reward > 0.0
    ]
    if not scored or sum(weight for _, weight in scored) <= 1e-9:
        return current
    target = _average_policy(scored)
    mixed = interpolate_policy(current, target, 0.5)
    return clip_policy_step(current, mixed)


def blend(
    current: Policy,
    proposed: Policy,
    telemetry: TelemetryWindow,
    buffer: ReplayBuffer,
) -> Policy:
    """Pull an accepted proposal slightly toward the reward-weighted baseline."""

    if len(buffer) == 0:
        return clip_policy_step(current, proposed)
    baseline = propose_baseline(current, telemetry, buffer)
    mixed = interpolate_policy(proposed, baseline, 0.30)
    mixed = Policy(
        V=mixed.V,
        latency=mixed.latency,
        throughput=mixed.throughput,
        loss=mixed.loss,
        energy=mixed.energy,
        resource=mixed.resource,
        action_mask=proposed.action_mask,
    )
    return clip_policy_step(current, mixed)
