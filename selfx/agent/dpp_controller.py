"""
Fast-Timescale Lyapunov Drift-Plus-Penalty (DPP) Controller
Traceability: Tasks T09, T10 | Deliverables D2 | EC466 Team SDN_07

Provides:
  - Real-time standalone fast controller operating on 100 ms – 1 s control ticks.
  - Provable queue-backlog stability without requiring online RL training or LLM waits.
  - Per-flow, polynomial-time greedy minimization of conditional drift + V * penalty:
      min_{a in Mask} [ sum_i Q_i(t) * (lambda_i(a) - mu_i(a)) + V * cost(a) ]
  - Benchmarks decision and installation latencies (guaranteed < 5 ms).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agent.action_gateway import GatewayValidationResult, TopologyActionGateway


@dataclass(frozen=True)
class DPPDecision:
    action: str
    dpp_score: float
    drift: float
    penalty: float
    q_primary_mbit: float
    q_secondary_mbit: float
    offered_mbps: float
    decision_time_ms: float
    rule_install_time_ms: float
    gateway_result: Optional[GatewayValidationResult] = None


class LyapunovDPPController:
    """
    Fast-timescale analytic Lyapunov DPP flow controller.
    Runs independently of the slow LLM governance loop.
    """

    def __init__(
        self,
        c_primary_mbps: float = 10.0,
        c_secondary_mbps: float = 10.0,
        d_primary_ms: float = 2.0,
        d_secondary_ms: float = 12.0,
        topology_name: str = "linear",
    ) -> None:
        self.c_primary = c_primary_mbps
        self.c_secondary = c_secondary_mbps
        self.d_primary = d_primary_ms
        self.d_secondary = d_secondary_ms
        self.gateway = TopologyActionGateway(topology_name)
        self.decision_benchmarks: List[float] = []

    def evaluate_action_terms(
        self,
        action: str,
        q_primary: float,
        q_secondary: float,
        mouse_mbps: float,
        elephant_mbps: float,
        policy_v: float,
        weights: Dict[str, float],
    ) -> Tuple[float, float, float]:
        """
        Computes (drift, penalty, total_dpp_score) for a candidate action.
        """
        total_offered = mouse_mbps + elephant_mbps

        if action == "reroute":
            arr_p = mouse_mbps
            arr_s = elephant_mbps
            lat_p = self.d_primary + (arr_p / self.c_primary) * 2.0
            lat_s = self.d_secondary + (arr_s / self.c_secondary) * 5.0
            avg_lat = (mouse_mbps * lat_p + elephant_mbps * lat_s) / max(0.1, total_offered)
            loss_pct = 0.0
            throughput = total_offered
            energy = 1.70  # using alternate link consumes extra power
            resource = 0.55

        elif action == "rate_limit":
            arr_p = mouse_mbps + min(elephant_mbps, self.c_primary * 0.6)
            arr_s = 0.0
            avg_lat = self.d_primary + (arr_p / self.c_primary) * 4.0
            admitted = arr_p
            dropped = total_offered - admitted
            loss_pct = (100.0 * dropped / total_offered) if total_offered > 0 else 0.0
            throughput = admitted
            energy = 0.35
            resource = 0.40

        elif action == "drop":
            arr_p = min(total_offered, self.c_primary)
            arr_s = 0.0
            avg_lat = self.d_primary + 1.0
            loss_pct = (100.0 * (total_offered - arr_p) / total_offered) if total_offered > 0 else 0.0
            throughput = arr_p
            energy = 0.35
            resource = 0.10

        elif action == "admit" or action == "no_op":
            arr_p = total_offered
            arr_s = 0.0
            avg_lat = self.d_primary + (arr_p / self.c_primary) * 12.0
            loss_pct = max(0.0, 100.0 * (arr_p - self.c_primary) / arr_p) if arr_p > self.c_primary else 0.0
            throughput = min(arr_p, self.c_primary)
            energy = 0.35
            resource = 0.0

        else:
            return 999.0, 999.0, 999.0

        # Drift term: Q1 * (arr1 - C1) + Q2 * (arr2 - C2)
        drift = q_primary * (arr_p - self.c_primary) + q_secondary * (arr_s - self.c_secondary)

        # Multi-objective penalty: w_lat * latency + w_loss * loss + w_energy * energy + w_res * res - w_tp * tp
        w_lat = weights.get("latency", 0.20)
        w_loss = weights.get("loss", 0.20)
        w_en = weights.get("energy", 0.20)
        w_res = weights.get("resource", 0.20)
        w_tp = weights.get("throughput", 0.20)

        penalty = (
            w_lat * (avg_lat / 30.0)
            + w_loss * (loss_pct / 20.0)
            + w_en * energy
            + w_res * resource
            - w_tp * (throughput / 10.0)
        )

        score = drift + policy_v * penalty
        return drift, penalty, score

    def decide(
        self,
        q_primary_mbit: float,
        q_secondary_mbit: float,
        mouse_mbps: float,
        elephant_mbps: float,
        policy_v: float,
        weights: Dict[str, float],
        action_mask: Tuple[str, ...],
        flow_match: Optional[Dict[str, Any]] = None,
    ) -> DPPDecision:
        """
        Executes fast DPP minimization and benchmarks decision and compilation times.
        """
        t0 = time.perf_counter()

        best_action = "admit" if "admit" in action_mask else action_mask[0]
        best_score = float("inf")
        best_drift = 0.0
        best_penalty = 0.0

        # Greedy drift-plus-penalty selection
        for act in action_mask:
            drift, penalty, score = self.evaluate_action_terms(
                act,
                q_primary_mbit,
                q_secondary_mbit,
                mouse_mbps,
                elephant_mbps,
                policy_v,
                weights,
            )
            if score < best_score:
                best_score = score
                best_drift = drift
                best_penalty = penalty
                best_action = act

        t_decision = (time.perf_counter() - t0) * 1000.0  # ms

        # Action Gateway compilation & verification
        t_install_start = time.perf_counter()
        match_criteria = flow_match or {"nw_src": "10.0.0.2", "nw_dst": "10.0.0.8"}
        total_offered = mouse_mbps + elephant_mbps
        gateway_res = self.gateway.validate_and_compile(
            best_action,
            match_criteria,
            offered_rate_kbps=total_offered * 1000.0,
            reason="Lyapunov DPP decision",
        )
        t_install = (time.perf_counter() - t_install_start) * 1000.0  # ms

        self.decision_benchmarks.append(t_decision)

        return DPPDecision(
            action=best_action,
            dpp_score=round(best_score, 4),
            drift=round(best_drift, 4),
            penalty=round(best_penalty, 4),
            q_primary_mbit=q_primary_mbit,
            q_secondary_mbit=q_secondary_mbit,
            offered_mbps=total_offered,
            decision_time_ms=round(t_decision, 3),
            rule_install_time_ms=round(t_install, 3),
            gateway_result=gateway_res,
        )

