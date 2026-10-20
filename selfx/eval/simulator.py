"""Seeded finite-buffer fluid network. Units: Mbit, Mbps, seconds, ms.

Two parallel logical paths (s1-s2-s4 and s1-s3-s4), each with a 10 Mbps
bottleneck and a 0.5 Mbit buffer. These are model assumptions, not Mininet.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass

from agent.schemas import DecisionOutput
from agent.reward import CycleMetrics
import safety

CAPACITY = 10.0
BUFFER = 0.5
INTERVAL = 5.0
FLOW_MATCH = {"in_port": 1, "eth_type": 2048, "ipv4_dst": "10.0.0.8"}


def traffic_trace(seed: int, cycles: int) -> list[dict]:
    if cycles <= 0:
        raise ValueError("cycles must be positive")
    rng = random.Random(seed)
    trace = []
    for cycle in range(cycles):
        # Repeated light / burst / alternate-heavy / dual-congestion episodes.
        phase = (cycle // 3) % 4
        primary = rng.uniform(3.0, 5.5) if phase != 3 else rng.uniform(6.0, 8.0)
        alternate = rng.uniform(1.0, 3.0) if phase in (0, 1) else rng.uniform(5.0, 8.0)
        elephant = rng.uniform(1.0, 3.0) if phase == 0 else rng.uniform(5.0, 9.5)
        trace.append({"cycle": cycle, "primary_background_mbps": round(primary, 4),
                      "alternate_background_mbps": round(alternate, 4), "elephant_mbps": round(elephant, 4),
                      "phase": ("light", "primary_burst", "alternate_busy", "both_busy")[phase]})
    return trace


@dataclass
class Outcome:
    latency_ms: float
    throughput_kbps: float
    loss_pct: float
    queue_mbit: list[float]
    offered_mbit: float
    delivered_mbit: float
    dropped_mbit: float
    meter_dropped_mbit: float

    def metrics(self):
        return CycleMetrics(self.latency_ms, self.throughput_kbps, self.loss_pct)


class FluidNetwork:
    def __init__(self):
        self.queue = [0.0, 0.0]

    def summary(self, demand: dict) -> dict:
        p, a, e = (demand[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps"))
        before = self.evaluate(demand, DecisionOutput(action="no_op", rationale="observation"))
        return {"latency_ms": before.latency_ms, "throughput_kbps": before.throughput_kbps,
                "loss_pct": before.loss_pct, "num_switches": 4,
                "top_flows": [{"dpid": "1", "match": FLOW_MATCH, "rate_kbps": e * 1000}],
                "hot_ports": [{"dpid": "1", "port_no": 2, "tx_kbps": (p + e) * 1000,
                               "util_pct": (p + e) * 10},
                              {"dpid": "1", "port_no": 3, "tx_kbps": a * 1000, "util_pct": a * 10}],
                "simulation": {"capacity_mbps": CAPACITY, "buffer_mbit": BUFFER,
                               "primary_background_mbps": p, "alternate_background_mbps": a,
                               "elephant_mbps": e, "queues_mbit": list(self.queue),
                               "valid_reroute_out_port": 3, "current_output_port": 2,
                               "action_lifetime": "one 5-second window; next flow starts on primary"},
                "embedding_features": [p / CAPACITY, a / CAPACITY, e / CAPACITY,
                                       self.queue[0] / BUFFER, self.queue[1] / BUFFER, (p + e) / CAPACITY]}

    def validate(self, demand: dict, decision: DecisionOutput) -> safety.SafetyResult:
        if not decision.is_well_formed():
            return safety.SafetyResult(False, "malformed decision", "no_op")
        if decision.action != "no_op" and (decision.target_dpid != 1 or decision.target_flow_match != FLOW_MATCH):
            return safety.SafetyResult(False, "unknown switch or flow", "no_op")
        if decision.action == "reroute" and decision.reroute_out_port != 3:
            return safety.SafetyResult(False, "output port has no alternate path", "no_op")
        return safety.check(safety.SafetyContext(
            action=decision.action, target_flow_rate_kbps=demand["elephant_mbps"] * 1000,
            proposed_rate_limit_kbps=decision.rate_limit_kbps, target_link_capacity_kbps=CAPACITY * 1000,
            target_link_current_kbps=demand["alternate_background_mbps"] * 1000))

    def evaluate(self, demand: dict, decision: DecisionOutput, commit: bool = False) -> Outcome:
        p, a, e = (demand[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps"))
        admitted_e = min(e, decision.rate_limit_kbps / 1000) if decision.action == "rate_limit" else e
        rates = [p, a]
        rates[1 if decision.action == "reroute" else 0] += admitted_e
        meter_drop = (e - admitted_e) * INTERVAL
        delivered_total, overflow_total, delays, new_queues = 0.0, 0.0, [], []
        for idx, rate in enumerate(rates):
            initial = self.queue[idx]
            net = rate - CAPACITY
            final = min(BUFFER, max(0.0, initial + net * INTERVAL))
            overflow = max(0.0, initial + net * INTERVAL - BUFFER)
            delivered = initial + rate * INTERVAL - final - overflow
            # Exact average fluid queue for a constant-rate window with saturation.
            if abs(net) < 1e-12:
                avg_queue = initial
            elif net > 0:
                hit = min(INTERVAL, (BUFFER - initial) / net)
                avg_queue = ((initial + min(BUFFER, initial + net * hit)) * hit / 2 + BUFFER * (INTERVAL - hit)) / INTERVAL
            else:
                hit = min(INTERVAL, initial / -net)
                avg_queue = (initial + max(0.0, initial + net * hit)) * hit / 2 / INTERVAL
            delay = 8.0 + avg_queue / CAPACITY * 1000
            delays.append((delay, delivered))
            delivered_total += delivered
            overflow_total += overflow
            new_queues.append(final)
        offered = (p + a + e) * INTERVAL
        dropped = overflow_total + meter_drop
        latency = sum(d * w for d, w in delays) / delivered_total if delivered_total else 8.0
        if commit:
            self.queue = new_queues
        return Outcome(round(latency, 6), round(delivered_total / INTERVAL * 1000, 6),
                       round(100 * dropped / offered, 6) if offered else 0,
                       new_queues, offered, delivered_total, dropped, meter_drop)


def decision_for(action: str, demand: dict, rationale: str) -> DecisionOutput:
    return DecisionOutput(action=action, target_dpid=1 if action != "no_op" else None,
                          target_flow_match=FLOW_MATCH if action != "no_op" else None,
                          reroute_out_port=3 if action == "reroute" else None,
                          rate_limit_kbps=math.ceil(demand["elephant_mbps"] * 800) if action == "rate_limit" else None,
                          rationale=rationale)


def reactive_policy(summary: dict, examples: list[dict], use_memory: bool) -> DecisionOutput:
    s = summary["simulation"]
    demand = {"elephant_mbps": s["elephant_mbps"]}
    if s["primary_background_mbps"] + s["elephant_mbps"] <= 8.5:
        action = "no_op"
    elif s["alternate_background_mbps"] + s["elephant_mbps"] <= 9:
        action = "reroute"
    else:
        action = "rate_limit"
    reason = "Offline threshold controller: 85% primary trigger and 90% alternate ceiling."
    if use_memory and examples:
        from agent.embedding import cosine, embed_state
        candidates = [r for r in examples if r["reward"] > 0.005 and
                      cosine(embed_state(summary), embed_state(r["state_summary"])) > .97]
        if candidates:
            best = max(candidates, key=lambda r: r["reward"])
            action = best["action"]
            reason = f"Offline case retrieval: reuse action from similar episode {best['cycle']}; rebuild parameters for current flow."
    return decision_for(action, demand, reason)


def least_loaded(summary: dict) -> DecisionOutput:
    s = summary["simulation"]
    action = "reroute" if s["alternate_background_mbps"] < s["primary_background_mbps"] and s["alternate_background_mbps"] + s["elephant_mbps"] <= 9 else "no_op"
    return decision_for(action, s, "Greedy least-loaded feasible path; no memory or LLM.")
