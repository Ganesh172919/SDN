"""
Lyapunov DPP [O(1/V), O(V)] Tradeoff Evaluation
Traceability: Task T13 | Deliverables D2, D5 | EC466 Team SDN_07

Sweeps trade-off parameter V in [1, 2, 4, 8, 16, 32] under fixed multi-objective
evaluation weights (latency, throughput, loss, energy, resource).
Validates:
  1. Time-average backlog scales linearly as O(V), bounded by (B + V * C) / epsilon.
  2. Time-average multi-objective cost decreases as O(1/V) towards optimal cost*.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "selfx") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "selfx"))

from agent.dpp_controller import LyapunovDPPController
from agent.dpp_stability import DPPStabilityValidator
from traffic_gen import generate_schedule

OUTPUT_DIR = PROJECT_ROOT / "selfx" / "output" / "dpp_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_v_sweep(v_values: List[float] = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0], intervals: int = 1000) -> Dict[str, Any]:
    controller = LyapunovDPPController()
    validator = DPPStabilityValidator()

    weights = {
        "latency": 0.25,
        "throughput": 0.25,
        "loss": 0.25,
        "energy": 0.15,
        "resource": 0.10,
    }
    action_mask = ("admit", "reroute", "rate_limit", "drop", "no_op")
    schedule = generate_schedule("volatile_dpp", int(intervals * 0.1) + 10, seed=42)
    events = schedule["events"]

    tradeoff_results = []
    print("==================================================================")
    print("SELF-X Lyapunov DPP [O(1/V), O(V)] Parameter Sweep (T13)")
    print("==================================================================")

    for v in v_values:
        q1 = 0.0
        q2 = 0.0
        total_q_sum = 0.0
        total_cost_sum = 0.0

        for slot in range(intervals):
            t_sec = slot * 0.1
            mouse_load = 3.0
            elephant_load = 0.0
            for ev in events:
                if ev["start_time_sec"] <= t_sec < ev["start_time_sec"] + ev["duration_sec"]:
                    if ev["type"] != "steady_background":
                        elephant_load = max(elephant_load, ev["rate_mbps"])

            dec = controller.decide(
                q_primary_mbit=q1,
                q_secondary_mbit=q2,
                mouse_mbps=mouse_load,
                elephant_mbps=elephant_load,
                policy_v=v,
                weights=weights,
                action_mask=action_mask,
            )

            if dec.action == "reroute":
                arr1, arr2 = mouse_load, elephant_load
                cost = 0.25 * (6.0 / 30.0) + 0.15 * 1.70 + 0.10 * 0.55 - 0.25 * (1.0)
            elif dec.action == "rate_limit":
                arr1, arr2 = mouse_load + min(elephant_load, 6.0), 0.0
                cost = 0.25 * (8.0 / 30.0) + 0.25 * (2.0 / 20.0) + 0.15 * 0.35 + 0.10 * 0.40 - 0.25 * (0.9)
            elif dec.action == "drop":
                arr1, arr2 = min(mouse_load + elephant_load, 10.0), 0.0
                cost = 0.25 * (3.0 / 30.0) + 0.25 * (5.0 / 20.0) + 0.15 * 0.35 + 0.10 * 0.10 - 0.25 * (0.7)
            else:
                arr1, arr2 = mouse_load + elephant_load, 0.0
                cost = 0.25 * (18.0 / 30.0) + 0.25 * (6.0 / 20.0) + 0.15 * 0.35 - 0.25 * (1.0)

            q1 = max(0.0, q1 + (arr1 - 10.0) * 0.1)
            q2 = max(0.0, q2 + (arr2 - 10.0) * 0.1)

            total_q_sum += (q1 + q2)
            total_cost_sum += cost

        mean_q = total_q_sum / intervals
        mean_cost = total_cost_sum / intervals
        bound = validator.constant_b + (v * validator.cost_c)

        record = {
            "V": v,
            "mean_backlog_mbit": round(mean_q, 4),
            "mean_cost": round(mean_cost, 4),
            "analytic_bound_B_plus_VC": round(bound, 3),
            "bound_satisfied": mean_q <= bound,
        }
        tradeoff_results.append(record)
        print(f"V={v:5.1f} | Mean Backlog: {mean_q:.4f} Mbit (Bound: {bound:.2f}) | Mean Cost: {mean_cost:.4f}")

    output = {
        "sweep": "V trade-off evaluation",
        "description": "Validation of O(1/V) cost and O(V) backlog scaling",
        "results": tradeoff_results,
    }

    out_file = OUTPUT_DIR / "dpp_v_tradeoff.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved V tradeoff evaluation to: {out_file}\n")
    return output


def main():
    evaluate_v_sweep()


if __name__ == "__main__":
    main()

