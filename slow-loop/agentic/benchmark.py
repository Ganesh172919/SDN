"""Validity, scripted reasoning, closed-loop, and holdout checks.

The fast controller inside the simulator does not learn. Learning is the
governor plus the reward-weighted update between windows.
"""

from __future__ import annotations

import math
from typing import Any

from agentic.config import WINDOW_SEC
from agentic.governor import Governor
from agentic.model_client import MockModel, ModelClient
from agentic.replay import ReplayBuffer
from agentic.reward import compute_reward, reflect
from agentic.schemas import Experience, Policy, TelemetryWindow, initial_policy, initial_telemetry
from agentic.simulator import Simulator


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    low = int(math.floor(index))
    high = min(low + 1, len(ordered) - 1)
    weight = index - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def scripted_telemetry(policy: Policy | None = None) -> TelemetryWindow:
    """Queue, latency, and loss are up. The alternate path is idle."""

    active = policy or initial_policy()
    return TelemetryWindow(
        queue_mbit=0.42,
        queue_trend=0.30,
        util_primary_pct=98.0,
        util_alt_pct=4.0,
        flow_mbps=16.0,
        latency_ms=48.0,
        latency_trend=22.0,
        loss_pct=14.0,
        loss_trend=9.0,
        throughput_mbps=9.2,
        energy=0.35,
        resource_cost=0.2,
        sla_violations=0.45,
        p95_latency_ms=53.0,
        policy=active,
    )


def _mean(rows: list[dict[str, float]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(row[key] for row in rows) / len(rows)


def run_loop(
    *,
    episodes: int,
    seed: int,
    profile: str,
    mode: str,
    learn: bool,
    client: ModelClient | None = None,
) -> dict[str, Any]:
    simulator = Simulator(seed=seed, profile=profile, horizon_sec=episodes * WINDOW_SEC + 5.0)
    policy = initial_policy()
    state = initial_telemetry(policy)
    buffer = ReplayBuffer()
    governor = Governor(client or MockModel(), buffer)
    rows: list[dict[str, float]] = []
    governor_times: list[float] = []
    accepted = 0
    valid = 0
    decisions = 0

    for _ in range(episodes):
        if learn:
            result = governor.step(state, policy, mode=mode)
            policy = result.policy_after
            governor_times.append(result.governor_seconds)
            decisions += 1
            accepted += int(result.accepted)
            valid += int(result.valid_json)
        window = simulator.run_window(policy, state)
        breakdown = compute_reward(state, window)
        buffer.add(
            Experience(
                state=state,
                policy=policy,
                reward=breakdown.reward,
                next_state=window,
                reflection=reflect(state, window, breakdown.reward),
            )
        )
        rows.append(
            {
                "latency_ms": window.latency_ms,
                "p95_latency_ms": window.p95_latency_ms,
                "throughput_mbps": window.throughput_mbps,
                "loss_pct": window.loss_pct,
                "queue_mbit": window.queue_mbit,
                "reward": breakdown.reward,
                "sla_violations": window.sla_violations,
            }
        )
        state = window

    tail = rows[-3:] if len(rows) >= 3 else rows
    return {
        "latency_ms": _mean(tail, "latency_ms"),
        "p95_latency_ms": _mean(tail, "p95_latency_ms"),
        "throughput_mbps": _mean(tail, "throughput_mbps"),
        "loss_pct": _mean(tail, "loss_pct"),
        "queue_mbit": _mean(tail, "queue_mbit"),
        "reward": _mean(rows, "reward"),
        "sla_violations": _mean(tail, "sla_violations"),
        "accept_rate": (accepted / decisions) if decisions else 0.0,
        "validity_rate": (valid / decisions) if decisions else 1.0,
        "governor_times": governor_times,
        "episodes": rows,
    }


def _metrics(summary: dict[str, Any]) -> dict[str, float]:
    keys = (
        "latency_ms",
        "p95_latency_ms",
        "throughput_mbps",
        "loss_pct",
        "queue_mbit",
        "reward",
        "sla_violations",
    )
    return {key: float(summary[key]) for key in keys}


def run_benchmark(
    *,
    episodes: int = 10,
    mode: str = "multi",
    client: ModelClient | None = None,
    seed: int = 1729,
) -> dict[str, Any]:
    if mode not in {"single", "multi"}:
        raise ValueError("mode must be 'single' or 'multi'")
    model = client or MockModel()

    scripted_governor = Governor(model, ReplayBuffer())
    before = initial_policy()
    scripted = scripted_governor.step(scripted_telemetry(before), before, mode=mode)
    reasoning_pass = (
        scripted.accepted
        and scripted.valid_json
        and scripted.policy_after.latency > before.latency + 0.02
        and "reroute" in scripted.policy_after.action_mask
    )

    learned = run_loop(
        episodes=episodes,
        seed=seed,
        profile="default",
        mode=mode,
        learn=True,
        client=model,
    )
    frozen = run_loop(
        episodes=episodes,
        seed=seed,
        profile="default",
        mode=mode,
        learn=False,
        client=model,
    )
    holdout = run_loop(
        episodes=episodes,
        seed=seed + 997,
        profile="holdout",
        mode=mode,
        learn=True,
        client=model,
    )

    times_ms = [seconds * 1000.0 for seconds in learned["governor_times"]]
    learned_metrics = _metrics(learned)
    frozen_metrics = _metrics(frozen)
    closed_ok = (
        learned_metrics["latency_ms"] <= frozen_metrics["latency_ms"] + 0.5
        and learned_metrics["sla_violations"] <= frozen_metrics["sla_violations"] + 0.01
    )
    return {
        "mode": mode,
        "episodes": episodes,
        "seed": seed,
        "validity_rate": learned["validity_rate"],
        "accept_rate": learned["accept_rate"],
        "scripted_reasoning_pass": reasoning_pass,
        "scripted_reason": scripted.reason,
        "scripted_latency_weight": scripted.policy_after.latency,
        "learned": learned_metrics,
        "frozen": frozen_metrics,
        "holdout": _metrics(holdout),
        "governor_p50_ms": percentile(times_ms, 0.50),
        "governor_p95_ms": percentile(times_ms, 0.95),
        "closed_loop_ok": closed_ok,
    }


def format_report(report: dict[str, Any]) -> str:
    def block(title: str, metrics: dict[str, float]) -> str:
        return (
            f"{title}\n"
            f"  latency {metrics['latency_ms']:.2f} ms   "
            f"p95 {metrics['p95_latency_ms']:.2f} ms\n"
            f"  throughput {metrics['throughput_mbps']:.2f} Mbps   "
            f"loss {metrics['loss_pct']:.2f}%\n"
            f"  queue {metrics['queue_mbit']:.3f} Mbit   "
            f"sla {metrics['sla_violations']:.3f}   "
            f"reward {metrics['reward']:.3f}"
        )

    lines = [
        f"SELF-X slow loop  mode={report['mode']}  episodes={report['episodes']}  seed={report['seed']}",
        f"validity {report['validity_rate']:.2%}   accept {report['accept_rate']:.2%}",
        f"scripted reasoning {'pass' if report['scripted_reasoning_pass'] else 'fail'}"
        f"  latency weight {report['scripted_latency_weight']:.3f}"
        f"  ({report['scripted_reason']})",
        block("learned (last 3 windows)", report["learned"]),
        block("frozen initial policy", report["frozen"]),
        block("holdout seed, no reused buffer", report["holdout"]),
        f"governor p50 {report['governor_p50_ms']:.2f} ms   p95 {report['governor_p95_ms']:.2f} ms",
        f"closed loop {'ok' if report['closed_loop_ok'] else 'worse than frozen'}",
    ]
    return "\n".join(lines)
