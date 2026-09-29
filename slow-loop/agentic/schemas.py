"""Policy, telemetry, and experience records for the slow loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agentic.config import (
    ACTIONS,
    V_MAX,
    V_MAX_STEP,
    V_MIN,
    WEIGHT_KEYS,
    WEIGHT_MAX_STEP,
)


def _round_weights(weights: dict[str, float]) -> dict[str, float]:
    ordered = [round(float(weights[key]), 6) for key in WEIGHT_KEYS]
    ordered[-1] = round(1.0 - sum(ordered[:-1]), 6)
    if ordered[-1] < -1e-6:
        raise ValueError("weights sum above 1 after rounding")
    ordered[-1] = max(0.0, ordered[-1])
    return {key: value for key, value in zip(WEIGHT_KEYS, ordered)}


@dataclass(frozen=True)
class Policy:
    """Parameters the fast drift-plus-penalty tick is allowed to use."""

    V: float
    latency: float
    throughput: float
    loss: float
    energy: float
    resource: float
    action_mask: tuple[str, ...]

    def weight(self, key: str) -> float:
        return float(getattr(self, key))

    def weights(self) -> dict[str, float]:
        return {key: self.weight(key) for key in WEIGHT_KEYS}

    def to_dict(self) -> dict[str, Any]:
        return {
            "V": self.V,
            "weights": self.weights(),
            "action_mask": list(self.action_mask),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> Policy:
        weights = payload["weights"]
        missing = [key for key in WEIGHT_KEYS if key not in weights]
        if missing:
            raise ValueError(f"missing weights: {missing}")
        mask = tuple(sorted(str(item) for item in payload["action_mask"]))
        return Policy(
            V=float(payload["V"]),
            latency=float(weights["latency"]),
            throughput=float(weights["throughput"]),
            loss=float(weights["loss"]),
            energy=float(weights["energy"]),
            resource=float(weights["resource"]),
            action_mask=mask,
        )


def initial_policy() -> Policy:
    """Throughput- and energy-heavy start. Reroute is allowed but costly."""

    return Policy(
        V=8.0,
        latency=0.10,
        throughput=0.25,
        loss=0.15,
        energy=0.35,
        resource=0.15,
        action_mask=tuple(sorted(ACTIONS)),
    )


def interpolate_policy(left: Policy, right: Policy, alpha: float) -> Policy:
    """Point on the segment from ``left`` to ``right``. Mask comes from ``right``."""

    def mix(a: float, b: float) -> float:
        return (1.0 - alpha) * a + alpha * b

    weights = {key: mix(left.weight(key), right.weight(key)) for key in WEIGHT_KEYS}
    canon = _round_weights(weights)
    mask = right.action_mask or left.action_mask
    return Policy(
        V=mix(left.V, right.V),
        action_mask=tuple(sorted(mask)),
        **canon,
    )


def clip_policy_step(current: Policy, target: Policy) -> Policy:
    """Largest step toward ``target`` that respects V and weight boxes."""

    d_v = min(V_MAX_STEP, max(-V_MAX_STEP, target.V - current.V))
    new_v = min(V_MAX, max(V_MIN, current.V + d_v))

    lo = {key: max(0.0, current.weight(key) - WEIGHT_MAX_STEP) for key in WEIGHT_KEYS}
    hi = {key: min(1.0, current.weight(key) + WEIGHT_MAX_STEP) for key in WEIGHT_KEYS}

    best = current.weights()
    low_alpha = 0.0
    high_alpha = 1.0
    for _ in range(32):
        alpha = (low_alpha + high_alpha) / 2.0
        cand = {
            key: current.weight(key) + alpha * (target.weight(key) - current.weight(key))
            for key in WEIGHT_KEYS
        }
        excess = sum(cand.values()) - 1.0
        cand = {key: cand[key] - excess / len(WEIGHT_KEYS) for key in WEIGHT_KEYS}
        feasible = all(lo[key] - 1e-9 <= cand[key] <= hi[key] + 1e-9 for key in WEIGHT_KEYS)
        if feasible:
            best = cand
            low_alpha = alpha
        else:
            high_alpha = alpha

    canon = _round_weights(best)
    mask = target.action_mask if target.action_mask else current.action_mask
    return Policy(V=new_v, action_mask=tuple(sorted(mask)), **canon)


@dataclass(frozen=True)
class TelemetryWindow:
    """One slow-loop observation. Rates are means over the window."""

    queue_mbit: float
    queue_trend: float
    util_primary_pct: float
    util_alt_pct: float
    flow_mbps: float
    latency_ms: float
    latency_trend: float
    loss_pct: float
    loss_trend: float
    throughput_mbps: float
    energy: float
    resource_cost: float
    sla_violations: float
    p95_latency_ms: float
    policy: Policy

    def features(self) -> tuple[float, ...]:
        return (
            self.queue_mbit / 0.5,
            self.util_primary_pct / 100.0,
            self.util_alt_pct / 100.0,
            self.latency_ms / 50.0,
            self.loss_pct / 20.0,
            self.latency_trend / 20.0,
            self.loss_trend / 10.0,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "queue_mbit": self.queue_mbit,
            "queue_trend": self.queue_trend,
            "util_primary_pct": self.util_primary_pct,
            "util_alt_pct": self.util_alt_pct,
            "flow_mbps": self.flow_mbps,
            "latency_ms": self.latency_ms,
            "latency_trend": self.latency_trend,
            "loss_pct": self.loss_pct,
            "loss_trend": self.loss_trend,
            "throughput_mbps": self.throughput_mbps,
            "energy": self.energy,
            "resource_cost": self.resource_cost,
            "sla_violations": self.sla_violations,
            "p95_latency_ms": self.p95_latency_ms,
            "policy": self.policy.to_dict(),
        }
        return payload

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> TelemetryWindow:
        return TelemetryWindow(
            queue_mbit=float(payload["queue_mbit"]),
            queue_trend=float(payload["queue_trend"]),
            util_primary_pct=float(payload["util_primary_pct"]),
            util_alt_pct=float(payload["util_alt_pct"]),
            flow_mbps=float(payload["flow_mbps"]),
            latency_ms=float(payload["latency_ms"]),
            latency_trend=float(payload["latency_trend"]),
            loss_pct=float(payload["loss_pct"]),
            loss_trend=float(payload["loss_trend"]),
            throughput_mbps=float(payload["throughput_mbps"]),
            energy=float(payload["energy"]),
            resource_cost=float(payload["resource_cost"]),
            sla_violations=float(payload["sla_violations"]),
            p95_latency_ms=float(payload["p95_latency_ms"]),
            policy=Policy.from_dict(payload["policy"]),
        )


def initial_telemetry(policy: Policy | None = None) -> TelemetryWindow:
    """Idle observation used before the first window."""

    active = policy or initial_policy()
    return TelemetryWindow(
        queue_mbit=0.0,
        queue_trend=0.0,
        util_primary_pct=30.0,
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
        p95_latency_ms=5.0,
        policy=active,
    )


@dataclass(frozen=True)
class SpecialistOpinion:
    role: str
    d_v: float
    weight_deltas: dict[str, float]
    enable: tuple[str, ...]
    disable: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "dV": self.d_v,
            "weight_deltas": self.weight_deltas,
            "enable": list(self.enable),
            "disable": list(self.disable),
            "note": self.note,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True)
class Experience:
    state: TelemetryWindow
    policy: Policy
    reward: float
    next_state: TelemetryWindow
    reflection: str


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    reason: str
    policy: Policy


@dataclass(frozen=True)
class CycleResult:
    accepted: bool
    reason: str
    policy_before: Policy
    policy_after: Policy
    proposal: Policy | None
    governor_seconds: float
    valid_json: bool
    mode: str
