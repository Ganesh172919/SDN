"""Fail-closed gate for a proposed policy.

A rejection leaves the previous policy installed. The gate does not
install flow-mods; it only accepts or rejects ΔΠ.
"""

from __future__ import annotations

from agentic.config import (
    ACTIONS,
    HEALTHY_LATENCY_MS,
    HEALTHY_LOSS_PCT,
    HEALTHY_QUEUE_MBIT,
    LATENCY_REGRESSION_MS,
    SLA_LOSS_PCT,
    V_MAX,
    V_MAX_STEP,
    V_MIN,
    WEIGHT_KEYS,
    WEIGHT_MAX_STEP,
    WEIGHT_SUM_TOL,
)
from agentic.schemas import GateDecision, Policy, TelemetryWindow


def _healthy(telemetry: TelemetryWindow) -> bool:
    return (
        telemetry.loss_pct < HEALTHY_LOSS_PCT
        and telemetry.queue_mbit < HEALTHY_QUEUE_MBIT
        and telemetry.latency_ms < HEALTHY_LATENCY_MS
    )


def check(
    current: Policy,
    proposed: Policy | None,
    telemetry: TelemetryWindow,
    latency_delta_est: float | None = None,
) -> GateDecision:
    if proposed is None:
        return GateDecision(False, "proposal was not valid JSON", current)

    if not V_MIN <= proposed.V <= V_MAX:
        return GateDecision(False, f"V {proposed.V:.2f} is outside [{V_MIN:.0f}, {V_MAX:.0f}]", current)
    if abs(proposed.V - current.V) > V_MAX_STEP + 1e-6:
        return GateDecision(
            False,
            f"V step {proposed.V - current.V:.2f} exceeds ±{V_MAX_STEP:.0f}",
            current,
        )

    weights = proposed.weights()
    if any(value < -1e-6 or value > 1.0 + 1e-6 for value in weights.values()):
        return GateDecision(False, "a weight is outside [0, 1]", current)
    if abs(sum(weights.values()) - 1.0) > WEIGHT_SUM_TOL:
        return GateDecision(False, "weights do not sum to 1", current)
    for key in WEIGHT_KEYS:
        step = abs(proposed.weight(key) - current.weight(key))
        if step > WEIGHT_MAX_STEP + 1e-4:
            return GateDecision(False, f"{key} weight step {step:.3f} exceeds {WEIGHT_MAX_STEP}", current)

    if not proposed.action_mask:
        return GateDecision(False, "action mask is empty", current)
    unknown = [action for action in proposed.action_mask if action not in ACTIONS]
    if unknown:
        return GateDecision(False, f"illegal actions {unknown}", current)

    enables_drop = "drop" in proposed.action_mask and "drop" not in current.action_mask
    if enables_drop and _healthy(telemetry):
        return GateDecision(
            False,
            "drop would be enabled while loss and queues are within the healthy band",
            current,
        )

    loss_not_the_problem = telemetry.loss_pct < SLA_LOSS_PCT and telemetry.loss_trend >= -0.5
    if (
        latency_delta_est is not None
        and latency_delta_est > LATENCY_REGRESSION_MS
        and loss_not_the_problem
    ):
        return GateDecision(
            False,
            f"similar outcomes raised latency by {latency_delta_est:.1f} ms while loss was not improving",
            current,
        )

    return GateDecision(True, "accepted", proposed)
