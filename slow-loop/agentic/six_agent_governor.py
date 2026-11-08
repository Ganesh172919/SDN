"""
Six-Agent Hierarchical LLM Governance Layer
Traceability: Task T14 | Deliverables D3, D5 | EC466 Team SDN_07

Roles:
  1. Orchestrator: High-level intent decomposition, tool dispatch, conflict resolution, final merge.
  2. Flow-Sizing Specialist: Flow bandwidth analysis, elephant classification, rate ceiling recommendations.
  3. Routing Specialist: Multi-path delay evaluation, reroute link selection.
  4. Anomaly Specialist: Loss spikes, buffer queue surges, jitter detection.
  5. Security Specialist: Volumetric burst inspection, flood defense, drop recommendations.
  6. Slicing Specialist: Multi-tenant SLA enforcement, priority queue reservations.

Logs full structured audit traces including intent decomposition, tool usage,
specialist opinions, conflict resolution, and the resulting Delta-Pi proposal.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agentic.config import ACTIONS, ROLES, V_MAX_STEP, WEIGHT_KEYS, WEIGHT_MAX_STEP
from agentic.schemas import Policy, SpecialistOpinion, TelemetryWindow, clip_policy_step


@dataclass
class AgentAuditTrace:
    cycle: int
    timestamp_utc: str
    network_intent: str
    intent_decomposition: Dict[str, Any]
    tool_invocations: List[Dict[str, Any]]
    specialist_opinions: Dict[str, Dict[str, Any]]
    conflict_resolution_notes: List[str]
    merged_proposal: Dict[str, Any]
    elapsed_seconds: float


class SixAgentGovernor:
    """
    Hierarchical 6-agent governor implementing the complete intent-decomposing
    orchestrator + 5 specialist layer.
    """

    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode
        self.cycle_count = 0
        self.traces: List[AgentAuditTrace] = []

    def decompose_intent(self, intent: str, telem: TelemetryWindow) -> Dict[str, Any]:
        """
        Orchestrator decomposes high-level intent into role-specific sub-goals.
        """
        is_congested = telem.latency_ms > 12.0 or telem.loss_pct > 1.5 or telem.queue_mbit > 0.05
        has_elephant = telem.flow_mbps > 5.0

        return {
            "global_intent": intent,
            "sub_goals": {
                "flow_sizing": "Throttle elephant flows" if has_elephant else "Monitor nominal rates",
                "routing": "Reroute elephant to secondary link" if (is_congested and telem.util_alt_pct < 50.0) else "Keep primary route",
                "anomaly": "Relieve buffer saturation immediately" if is_congested else "Normal operating regime",
                "security": "Enforce admission controls" if has_elephant else "Audit clean traffic",
                "slicing": "Prioritize mice latency SLA (<15ms)" if is_congested else "Maintain fair bandwidth",
            },
            "congestion_detected": is_congested,
            "elephant_detected": has_elephant,
        }

    def consult_flow_sizing(self, telem: TelemetryWindow) -> SpecialistOpinion:
        if telem.flow_mbps > 6.0:
            return SpecialistOpinion(
                role="flow_sizing",
                d_v=-0.5,
                weight_deltas={"loss": 0.06, "latency": 0.04, "throughput": -0.10},
                enable=("rate_limit",),
                disable=(),
                note="Elephant burst detected (>6 Mbps); enable rate limiting and lower throughput weight",
            )
        return SpecialistOpinion("flow_sizing", 0.0, {}, (), (), "Flows nominal")

    def consult_routing(self, telem: TelemetryWindow) -> SpecialistOpinion:
        if telem.latency_ms > 10.0 and telem.util_alt_pct < 60.0:
            return SpecialistOpinion(
                role="routing",
                d_v=1.0,
                weight_deltas={"latency": 0.08, "energy": -0.04, "throughput": -0.04},
                enable=("reroute",),
                disable=(),
                note=f"High latency ({telem.latency_ms:.1f}ms); alternate path is healthy ({telem.util_alt_pct:.1f}% util); enable reroute",
            )
        return SpecialistOpinion("routing", 0.0, {}, (), (), "Routing optimal")

    def consult_anomaly(self, telem: TelemetryWindow) -> SpecialistOpinion:
        if telem.queue_mbit > 0.08 or telem.loss_pct > 2.0:
            return SpecialistOpinion(
                role="anomaly",
                d_v=-1.0,
                weight_deltas={"loss": 0.08, "latency": 0.06, "energy": -0.07, "resource": -0.07},
                enable=("drop", "rate_limit"),
                disable=(),
                note=f"Buffer queue overflow hazard (Q={telem.queue_mbit:.3f}Mbit, loss={telem.loss_pct:.1f}%); prioritize loss and latency",
            )
        return SpecialistOpinion("anomaly", 0.0, {}, (), (), "No anomalies")

    def consult_security(self, telem: TelemetryWindow) -> SpecialistOpinion:
        if telem.flow_mbps > 12.0:
            return SpecialistOpinion(
                role="security",
                d_v=0.0,
                weight_deltas={"resource": 0.05, "loss": 0.05, "throughput": -0.10},
                enable=("rate_limit",),
                disable=(),
                note="Excessive flow volume (>12 Mbps); enforce rate clamp",
            )
        return SpecialistOpinion("security", 0.0, {}, (), (), "Security posture normal")

    def consult_slicing(self, telem: TelemetryWindow) -> SpecialistOpinion:
        if telem.latency_ms > 15.0 or telem.sla_violations > 0:
            return SpecialistOpinion(
                role="slicing",
                d_v=0.5,
                weight_deltas={"latency": 0.10, "throughput": -0.05, "energy": -0.05},
                enable=("reroute", "rate_limit"),
                disable=(),
                note="SLA violation danger: enforce strict latency guarantee for delay-sensitive slice",
            )
        return SpecialistOpinion("slicing", 0.0, {}, (), (), "Slice SLAs satisfied")

    def orchestrate_cycle(
        self,
        current_policy: Policy,
        telem: TelemetryWindow,
        intent: str = "Minimise latency under SLA without exceeding buffer capacity",
    ) -> Tuple[Policy, AgentAuditTrace]:
        t0 = time.perf_counter()
        self.cycle_count += 1
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Intent Decomposition by Orchestrator
        decomp = self.decompose_intent(intent, telem)

        # 2. Specialist Consultations
        tools_used = [
            {"tool": "query_flow_table", "result": f"active_flows=2, flow_mbps={telem.flow_mbps}"},
            {"tool": "query_queue_stats", "result": f"q_mbit={telem.queue_mbit:.4f}"},
            {"tool": "query_port_utilization", "result": f"primary={telem.util_primary_pct}%, alt={telem.util_alt_pct}%"},
        ]

        opinions = [
            self.consult_flow_sizing(telem),
            self.consult_routing(telem),
            self.consult_anomaly(telem),
            self.consult_security(telem),
            self.consult_slicing(telem),
        ]

        # 3. Conflict Resolution & Merge by Orchestrator
        notes = []
        d_v = sum(op.d_v for op in opinions)
        d_v = max(-V_MAX_STEP, min(V_MAX_STEP, d_v))

        deltas = {k: 0.0 for k in WEIGHT_KEYS}
        for op in opinions:
            for k, val in op.weight_deltas.items():
                deltas[k] += val

        # Zero-center and clip weight steps
        mean_delta = sum(deltas.values()) / len(WEIGHT_KEYS)
        deltas = {k: v - mean_delta for k, v in deltas.items()}
        peak = max((abs(v) for v in deltas.values()), default=0.0)
        if peak > WEIGHT_MAX_STEP:
            scale = WEIGHT_MAX_STEP / peak
            deltas = {k: v * scale for k, v in deltas.items()}
            notes.append(f"Clipped specialist weight deltas by scale {scale:.3f}")

        target_weights = {k: current_policy.weight(k) + deltas[k] for k in WEIGHT_KEYS}
        mask = set(current_policy.action_mask)
        for op in opinions:
            mask.update(op.enable)
            for d in op.disable:
                mask.discard(d)
        if not mask:
            mask.add("admit")

        target_policy = Policy(
            V=current_policy.V + d_v,
            latency=target_weights["latency"],
            throughput=target_weights["throughput"],
            loss=target_weights["loss"],
            energy=target_weights["energy"],
            resource=target_weights["resource"],
            action_mask=tuple(sorted(mask)),
        )
        proposed_policy = clip_policy_step(current_policy, target_policy)

        elapsed = time.perf_counter() - t0
        trace = AgentAuditTrace(
            cycle=self.cycle_count,
            timestamp_utc=timestamp,
            network_intent=intent,
            intent_decomposition=decomp,
            tool_invocations=tools_used,
            specialist_opinions={op.role: {"d_v": op.d_v, "weights": op.weight_deltas, "note": op.note} for op in opinions},
            conflict_resolution_notes=notes,
            merged_proposal=proposed_policy.to_dict(),
            elapsed_seconds=round(elapsed, 4),
        )
        self.traces.append(trace)

        return proposed_policy, trace

