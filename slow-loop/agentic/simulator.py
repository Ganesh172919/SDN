"""Fluid queue of the 4-switch topology's s2-s3 bottleneck.

Path A is 10 Mbps / 5 ms. Path B is 10 Mbps / 12 ms. Trunks are not the
bottleneck. Each 100 ms tick picks one masked action with drift-plus-penalty.
Nothing inside the tick is trained.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agentic.config import (
    ACTIONS,
    MAX_QUEUE_MBIT,
    PATH_A_DELAY_MS,
    PATH_A_MBPS,
    PATH_B_DELAY_MS,
    PATH_B_MBPS,
    SLA_LATENCY_MS,
    SLA_LOSS_PCT,
    TICK_SEC,
    TICKS_PER_WINDOW,
    WINDOW_SEC,
)
from agentic.schemas import Policy, TelemetryWindow

# Using the slow path costs extra energy, so a throughput-heavy policy
# stays on the primary until the governor raises the latency weight.
ENERGY_IDLE = 0.15
ENERGY_PRIMARY = 0.35
ENERGY_ALTERNATE = 1.35


@dataclass(frozen=True)
class ActionEffect:
    action: str
    arr_a: float
    arr_b: float
    explicit_drop_mbps: float
    q_a: float
    q_b: float
    overflow_mbit: float
    latency_ms: float
    throughput_mbps: float
    loss_pct: float
    energy: float
    resource: float
    drift: float
    penalty: float
    score: float


def _step_queue(queue: float, arrival_mbps: float, capacity_mbps: float) -> tuple[float, float]:
    nxt = queue + (arrival_mbps - capacity_mbps) * TICK_SEC
    if nxt > MAX_QUEUE_MBIT:
        return MAX_QUEUE_MBIT, nxt - MAX_QUEUE_MBIT
    if nxt < 0.0:
        return 0.0, 0.0
    return nxt, 0.0


def _split(action: str, offered_mbps: float, q_a: float) -> tuple[float, float, float]:
    """Return (arrival A, arrival B, explicit drop) in Mbps."""

    if action == "reroute":
        congested = offered_mbps > PATH_A_MBPS * 0.98 or q_a > 0.05
        if not congested:
            return offered_mbps, 0.0, 0.0
        keep = min(offered_mbps, PATH_A_MBPS * 0.8)
        return keep, offered_mbps - keep, 0.0
    if action == "rate_limit":
        cap = PATH_A_MBPS * 0.9
        admitted = min(offered_mbps, cap)
        return admitted, 0.0, offered_mbps - admitted
    if action == "drop":
        admitted = min(offered_mbps, PATH_A_MBPS)
        return admitted, 0.0, offered_mbps - admitted
    return offered_mbps, 0.0, 0.0


def predict_action(policy: Policy, action: str, q_a: float, q_b: float, offered_mbps: float) -> ActionEffect:
    arr_a, arr_b, explicit_drop = _split(action, offered_mbps, q_a)
    next_a, over_a = _step_queue(q_a, arr_a, PATH_A_MBPS)
    next_b, over_b = _step_queue(q_b, arr_b, PATH_B_MBPS)
    overflow = over_a + over_b
    drop_mbit = explicit_drop * TICK_SEC + overflow
    offered_mbit = max(offered_mbps * TICK_SEC, 1e-9)
    delivered_mbit = max(0.0, offered_mbit - drop_mbit)
    loss_pct = 100.0 * drop_mbit / offered_mbit
    throughput = delivered_mbit / TICK_SEC

    lat_a = PATH_A_DELAY_MS + 1000.0 * next_a / PATH_A_MBPS
    lat_b = PATH_B_DELAY_MS + 1000.0 * next_b / PATH_B_MBPS
    served_a = max(0.0, arr_a * TICK_SEC - over_a)
    served_b = max(0.0, arr_b * TICK_SEC - over_b)
    served = served_a + served_b
    if served <= 1e-9:
        latency = max(lat_a, lat_b)
    else:
        latency = (served_a * lat_a + served_b * lat_b) / served

    if arr_b > 0.5:
        energy = ENERGY_PRIMARY + ENERGY_ALTERNATE
    elif arr_a > 0.0:
        energy = ENERGY_PRIMARY
    else:
        energy = ENERGY_IDLE
    resource = 0.0 if action == "admit" or (action == "reroute" and arr_b <= 0.5) else 0.55

    weights = policy.weights()
    penalty = (
        weights["latency"] * (latency / 40.0)
        + weights["loss"] * (loss_pct / 25.0)
        + weights["energy"] * energy
        + weights["resource"] * resource
        - weights["throughput"] * (throughput / 10.0)
    )
    drift = q_a * (arr_a - PATH_A_MBPS) + q_b * (arr_b - PATH_B_MBPS)
    score = drift + policy.V * penalty
    return ActionEffect(
        action=action,
        arr_a=arr_a,
        arr_b=arr_b,
        explicit_drop_mbps=explicit_drop,
        q_a=next_a,
        q_b=next_b,
        overflow_mbit=overflow,
        latency_ms=latency,
        throughput_mbps=throughput,
        loss_pct=loss_pct,
        energy=energy,
        resource=resource,
        drift=drift,
        penalty=penalty,
        score=score,
    )


_TIE_ORDER = {"admit": 0, "reroute": 1, "rate_limit": 2, "drop": 3}


def choose_action(policy: Policy, q_a: float, q_b: float, offered_mbps: float) -> ActionEffect:
    mask = [action for action in policy.action_mask if action in ACTIONS]
    if not mask:
        mask = ["admit"]
    best: ActionEffect | None = None
    for action in mask:
        effect = predict_action(policy, action, q_a, q_b, offered_mbps)
        if best is None or effect.score < best.score - 1e-9:
            best = effect
        elif abs(effect.score - best.score) <= 1e-9 and _TIE_ORDER[action] < _TIE_ORDER[best.action]:
            best = effect
    assert best is not None
    return best


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    weight = index - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


@dataclass
class _Burst:
    start: float
    duration: float
    mbps: float


class Simulator:
    """Seeded mice plus elephant bursts, copied from the traffic generator ranges."""

    def __init__(
        self,
        seed: int = 1729,
        profile: str = "default",
        horizon_sec: float = 1200.0,
    ) -> None:
        if profile not in {"default", "holdout"}:
            raise ValueError(f"unknown profile {profile}")
        self.profile = profile
        self.seed = seed
        self.rng = random.Random(seed)
        self.steady_mbps = 3.0 if profile == "default" else 4.0
        self.t = 0.0
        self.q_a = 0.0
        self.q_b = 0.0
        self.bursts = self._schedule(horizon_sec)

    def _schedule(self, horizon_sec: float) -> list[_Burst]:
        bursts: list[_Burst] = []
        t = self.rng.uniform(5.0, 15.0)
        while t < horizon_sec:
            if self.profile == "default":
                duration = self.rng.uniform(4.0, 10.0)
                rate = self.rng.uniform(8.0, 15.0)
                gap = self.rng.uniform(20.0, 45.0)
            else:
                duration = self.rng.uniform(3.0, 8.0)
                rate = self.rng.uniform(10.0, 18.0)
                gap = self.rng.uniform(10.0, 25.0)
            bursts.append(_Burst(t, duration, rate))
            t += duration + gap
        return bursts

    def offered_mbps(self, t: float | None = None) -> float:
        now = self.t if t is None else t
        rate = self.steady_mbps
        for burst in self.bursts:
            if burst.start <= now < burst.start + burst.duration:
                rate += burst.mbps
        return rate

    def run_window(self, policy: Policy, previous: TelemetryWindow | None = None) -> TelemetryWindow:
        latencies: list[float] = []
        queues: list[float] = []
        util_a: list[float] = []
        util_b: list[float] = []
        offered_sum = 0.0
        delivered_sum = 0.0
        drop_sum = 0.0
        energy_sum = 0.0
        resource_sum = 0.0
        sla_ticks = 0

        for _ in range(TICKS_PER_WINDOW):
            offered = self.offered_mbps()
            effect = choose_action(policy, self.q_a, self.q_b, offered)
            self.q_a = effect.q_a
            self.q_b = effect.q_b
            self.t += TICK_SEC

            offered_mbit = offered * TICK_SEC
            drop_mbit = effect.explicit_drop_mbps * TICK_SEC + effect.overflow_mbit
            delivered_mbit = max(0.0, offered_mbit - drop_mbit)
            tick_loss = 100.0 * drop_mbit / offered_mbit if offered_mbit else 0.0

            latencies.append(effect.latency_ms)
            queues.append(self.q_a + self.q_b)
            util_a.append(100.0 * min(effect.arr_a, PATH_A_MBPS) / PATH_A_MBPS)
            util_b.append(100.0 * min(effect.arr_b, PATH_B_MBPS) / PATH_B_MBPS)
            offered_sum += offered_mbit
            delivered_sum += delivered_mbit
            drop_sum += drop_mbit
            energy_sum += effect.energy
            resource_sum += effect.resource
            if effect.latency_ms > SLA_LATENCY_MS or tick_loss > SLA_LOSS_PCT:
                sla_ticks += 1

        n = float(TICKS_PER_WINDOW)
        latency = sum(latencies) / n
        loss = 100.0 * drop_sum / offered_sum if offered_sum else 0.0
        queue = sum(queues) / n
        prev_latency = previous.latency_ms if previous else latency
        prev_loss = previous.loss_pct if previous else loss
        prev_queue = previous.queue_mbit if previous else queue
        return TelemetryWindow(
            queue_mbit=queue,
            queue_trend=queue - prev_queue,
            util_primary_pct=sum(util_a) / n,
            util_alt_pct=sum(util_b) / n,
            flow_mbps=offered_sum / WINDOW_SEC,
            latency_ms=latency,
            latency_trend=latency - prev_latency,
            loss_pct=loss,
            loss_trend=loss - prev_loss,
            throughput_mbps=delivered_sum / WINDOW_SEC,
            energy=energy_sum / n,
            resource_cost=resource_sum / n,
            sla_violations=sla_ticks / n,
            p95_latency_ms=_percentile(latencies, 0.95),
            policy=policy,
        )
