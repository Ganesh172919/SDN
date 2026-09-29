"""Role prompts for the slow policy governor.

One model serves every role. The prompts differ; the process does not
load a separate checkpoint per specialist.
"""

from __future__ import annotations

import json

from agentic.config import ROLES
from agentic.schemas import Policy, TelemetryWindow

_SHARED = """You govern a Lyapunov drift-plus-penalty controller for an SDN \
bottleneck. You do not install OpenFlow rules and you do not edit the \
drift math. You only propose parameters: V, objective weights \
(latency, throughput, loss, energy, resource, summing to 1), and an \
action mask drawn from reroute, rate_limit, admit, and drop.

Path A is 10 Mbps with 5 ms delay. Path B is 10 Mbps with 12 ms delay. \
Reroute is how overflow leaves a congested primary path. Drop and \
aggressive rate limits cost loss. V is in [1, 100]. Change V by at most \
20 and any weight by at most 0.20 in one cycle. Return JSON only."""

ROLE_PROMPTS = {
    "flow_sizing": _SHARED
    + " You are the flow-sizing specialist. Focus on offered load, loss, "
    "and whether rate_limit or admit should stay available.",
    "routing": _SHARED
    + " You are the routing and traffic-engineering specialist. If the "
    "primary queue, latency, and loss are up while the alternate path is "
    "idle, raise the latency weight and keep reroute enabled.",
    "anomaly": _SHARED
    + " You are the anomaly specialist. React to rising latency and loss "
    "trends by increasing V so the fast loop spends more effort on the penalty.",
    "security": _SHARED
    + " You are the security specialist. Do not enable drop while loss, "
    "queue, and latency are already healthy.",
    "slicing": _SHARED
    + " You are the slicing specialist. Balance resource cost against "
    "using the alternate path when a slice is congested.",
    "single": _SHARED
    + " You are the sole governor. Combine flow sizing, routing, anomaly "
    "detection, security, and slicing into one policy update.",
}

_OPINION_SCHEMA = {
    "role": "routing",
    "dV": 0.0,
    "weight_deltas": {"latency": 0.0},
    "enable": ["reroute"],
    "disable": [],
    "note": "one sentence",
}

_POLICY_SCHEMA = {
    "V": 8.0,
    "weights": {
        "latency": 0.10,
        "throughput": 0.25,
        "loss": 0.15,
        "energy": 0.35,
        "resource": 0.15,
    },
    "action_mask": ["admit", "drop", "rate_limit", "reroute"],
}


def _payload(role: str, telemetry: TelemetryWindow, policy: Policy) -> str:
    body = {
        "role": role,
        "telemetry": telemetry.to_dict(),
        "policy": policy.to_dict(),
        "response_schema": _POLICY_SCHEMA if role == "single" else _OPINION_SCHEMA,
    }
    return json.dumps(body)


def build_role_messages(role: str, telemetry: TelemetryWindow, policy: Policy) -> list[dict[str, str]]:
    if role not in ROLES and role != "single":
        raise ValueError(f"unknown role {role}")
    return [
        {"role": "system", "content": ROLE_PROMPTS[role]},
        {"role": "user", "content": _payload(role, telemetry, policy)},
    ]
