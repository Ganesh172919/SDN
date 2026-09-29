"""Specialist roles and the orchestrator that merges them into one policy."""

from __future__ import annotations

import json

from agentic.config import ACTIONS, ROLES, V_MAX_STEP, WEIGHT_KEYS, WEIGHT_MAX_STEP
from agentic.schemas import Policy, SpecialistOpinion, TelemetryWindow, clip_policy_step


def parse_opinion(raw: str) -> SpecialistOpinion:
    payload = json.loads(raw)
    role = str(payload["role"])
    if role not in ROLES:
        raise ValueError(f"unknown role {role}")
    deltas = payload.get("weight_deltas") or {}
    if not isinstance(deltas, dict):
        raise ValueError("weight_deltas must be an object")
    clean = {str(key): float(value) for key, value in deltas.items() if key in WEIGHT_KEYS}
    enable = tuple(str(item) for item in payload.get("enable") or [])
    disable = tuple(str(item) for item in payload.get("disable") or [])
    for action in enable + disable:
        if action not in ACTIONS:
            raise ValueError(f"illegal action {action}")
    return SpecialistOpinion(
        role=role,
        d_v=float(payload.get("dV", 0.0)),
        weight_deltas=clean,
        enable=enable,
        disable=disable,
        note=str(payload.get("note", "")),
    )


def parse_policy_text(raw: str) -> Policy:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("policy JSON must be an object")
    return Policy.from_dict(payload)


def merge_opinions(policy: Policy, opinions: list[SpecialistOpinion]) -> Policy:
    """Turn partial specialist opinions into one clipped policy proposal."""

    d_v = sum(opinion.d_v for opinion in opinions)
    d_v = max(-V_MAX_STEP, min(V_MAX_STEP, d_v))

    deltas = {key: 0.0 for key in WEIGHT_KEYS}
    for opinion in opinions:
        for key, value in opinion.weight_deltas.items():
            deltas[key] += value
    mean = sum(deltas.values()) / len(WEIGHT_KEYS)
    deltas = {key: value - mean for key, value in deltas.items()}
    peak = max((abs(value) for value in deltas.values()), default=0.0)
    if peak > WEIGHT_MAX_STEP:
        scale = WEIGHT_MAX_STEP / peak
        deltas = {key: value * scale for key, value in deltas.items()}

    target_weights = {key: policy.weight(key) + deltas[key] for key in WEIGHT_KEYS}
    mask = set(policy.action_mask)
    for opinion in opinions:
        mask.update(opinion.enable)
        for action in opinion.disable:
            mask.discard(action)
    if not mask:
        mask.add("admit")

    target = Policy(
        V=policy.V + d_v,
        latency=target_weights["latency"],
        throughput=target_weights["throughput"],
        loss=target_weights["loss"],
        energy=target_weights["energy"],
        resource=target_weights["resource"],
        action_mask=tuple(sorted(mask)),
    )
    return clip_policy_step(policy, target)


def congested(telemetry: TelemetryWindow) -> bool:
    return (
        telemetry.latency_ms >= 12.0
        or telemetry.loss_pct >= 2.0
        or telemetry.queue_mbit >= 0.15
        or telemetry.p95_latency_ms >= 40.0
    )


def alternate_idle(telemetry: TelemetryWindow) -> bool:
    return telemetry.util_alt_pct < 50.0


def healthy(telemetry: TelemetryWindow) -> bool:
    from agentic.config import HEALTHY_LATENCY_MS, HEALTHY_LOSS_PCT, HEALTHY_QUEUE_MBIT

    return (
        telemetry.loss_pct < HEALTHY_LOSS_PCT
        and telemetry.queue_mbit < HEALTHY_QUEUE_MBIT
        and telemetry.latency_ms < HEALTHY_LATENCY_MS
    )


def specialist_opinion(role: str, telemetry: TelemetryWindow, policy: Policy) -> SpecialistOpinion:
    """Deterministic specialist used by the mock model.

    The rules are the stand-in for a local model: same inputs, JSON out,
    no packet decisions.
    """

    if role not in ROLES:
        raise ValueError(role)
    hot = congested(telemetry)
    idle_alt = alternate_idle(telemetry)
    calm = healthy(telemetry)

    if role == "flow_sizing":
        if hot:
            return SpecialistOpinion(
                role=role,
                d_v=4.0,
                weight_deltas={"loss": 0.06, "throughput": -0.03},
                enable=("rate_limit", "admit"),
                disable=(),
                note="Offered load is above the primary path; keep rate_limit available.",
            )
    elif role == "routing":
        if hot and idle_alt:
            return SpecialistOpinion(
                role=role,
                d_v=8.0,
                weight_deltas={"latency": 0.14, "energy": -0.10, "throughput": -0.02},
                enable=("reroute", "admit"),
                disable=(),
                note="Queue, latency, and loss are up and the alternate path is idle.",
            )
    elif role == "anomaly":
        if telemetry.latency_trend > 5.0 or telemetry.loss_trend > 2.0 or telemetry.p95_latency_ms >= 40.0:
            return SpecialistOpinion(
                role=role,
                d_v=7.0,
                weight_deltas={"latency": 0.05, "loss": 0.04},
                enable=(),
                disable=(),
                note="Latency or loss is trending up; raise V.",
            )
    elif role == "security":
        if calm:
            return SpecialistOpinion(
                role=role,
                d_v=0.0,
                weight_deltas={},
                enable=(),
                disable=("drop",),
                note="Network is inside the healthy band; do not arm drop.",
            )
    elif role == "slicing":
        if hot and idle_alt:
            return SpecialistOpinion(
                role=role,
                d_v=0.0,
                weight_deltas={"resource": -0.04, "latency": 0.03},
                enable=("reroute",),
                disable=(),
                note="Shift resource weight toward the congested slice's latency.",
            )

    return SpecialistOpinion(role, 0.0, {}, (), (), "No change from this role.")
