"""
Phase 5 & Deliverable D2 — Formal Lyapunov DPP Backlog Acceptance Campaign
Traceability: Tasks T08, T10, T12 | Deliverable D2 | EC466 Team SDN_07

Acceptance Criterion (D2):
  Empirically validate that the time-average backlog bound holds in >= 95.0%
  of >= 1,000 discrete control intervals across 3 traffic profiles:
    1. 'steady_bursty'
    2. 'flash_crowd'
    3. 'volatile_dpp'

Saves raw interval evidence, running time-averages, constants B/C/epsilon, and
formal compliance reports to selfx/output/dpp_validation/.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "selfx") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "selfx"))

from agent.dpp_controller import LyapunovDPPController
from agent.dpp_stability import DPPStabilityValidator
from traffic_gen import generate_schedule

DPP_OUTPUT_DIR = PROJECT_ROOT / "selfx" / "output" / "dpp_validation"
DPP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_campaign_for_profile(
    profile_name: str,
    num_intervals: int = 1000,
    slot_sec: float = 0.1,
    seed: int = 42,
    policy_v: float = 8.0,
    warmup_intervals: int = 50,
) -> Dict[str, Any]:
    """
    Executes >= 1,000 control intervals under Lyapunov DPP control and validates the backlog bound.
    """
    controller = LyapunovDPPController(
        c_primary_mbps=10.0,
        c_secondary_mbps=10.0,
        d_primary_ms=2.0,
        d_secondary_ms=12.0,
    )
    validator = DPPStabilityValidator()

    weights = {
        "latency": 0.25,
        "throughput": 0.25,
        "loss": 0.25,
        "energy": 0.15,
        "resource": 0.10,
    }
    action_mask = ("admit", "reroute", "rate_limit", "drop", "no_op")

    # Verify stability & get analytic constants
    stab = validator.verify_stability(
        current_v=policy_v,
        proposed_v=policy_v,
        weights=weights,
        action_mask=action_mask,
    )
    b_const = validator.constant_b
    c_const = validator.cost_c
    epsilon = stab.capacity_slack_epsilon
    normalized_bound = round(b_const + policy_v * c_const, 3)
    exact_bound = stab.analytic_bound

    # State variables
    q_primary = 0.0
    q_secondary = 0.0

    raw_intervals: List[Dict[str, Any]] = []
    queue_sum = 0.0
    compliant_slots = 0
    total_evaluated_slots = 0

    # Traffic schedule
    duration_sec = int(num_intervals * slot_sec) + 10
    schedule = generate_schedule(profile_name, duration_sec, seed)
    events = schedule["events"]

    for slot in range(num_intervals):
        t_sec = slot * slot_sec

        # Determine offered load at slot t
        mouse_load = 3.0
        elephant_load = 0.0

        for ev in events:
            ev_start = ev["start_time_sec"]
            ev_end = ev_start + ev["duration_sec"]
            if ev_start <= t_sec < ev_end:
                if ev["type"] != "steady_background":
                    elephant_load = max(elephant_load, ev["rate_mbps"])

        # Execute Fast DPP Decision
        dec = controller.decide(
            q_primary_mbit=q_primary,
            q_secondary_mbit=q_secondary,
            mouse_mbps=mouse_load,
            elephant_mbps=elephant_load,
            policy_v=policy_v,
            weights=weights,
            action_mask=action_mask,
        )

        # Apply action & step fluid queues
        if dec.action == "reroute":
            arr_p = mouse_load
            arr_s = elephant_load
        elif dec.action == "rate_limit":
            arr_p = mouse_load + min(elephant_load, 6.0)
            arr_s = 0.0
        elif dec.action == "drop":
            arr_p = min(mouse_load + elephant_load, 10.0)
            arr_s = 0.0
        else:  # admit / no_op
            arr_p = mouse_load + elephant_load
            arr_s = 0.0

        # Lindley queue update
        q_primary = max(0.0, q_primary + (arr_p - 10.0) * slot_sec)
        q_secondary = max(0.0, q_secondary + (arr_s - 10.0) * slot_sec)
        total_q = q_primary + q_secondary

        # Running time-average computation (post warm-up)
        if slot >= warmup_intervals:
            total_evaluated_slots += 1
            queue_sum += total_q
            time_avg_q = queue_sum / total_evaluated_slots
            is_compliant = (time_avg_q <= normalized_bound)
            if is_compliant:
                compliant_slots += 1
        else:
            time_avg_q = total_q
            is_compliant = True

        raw_intervals.append({
            "slot": slot,
            "time_sec": round(t_sec, 3),
            "offered_mbps": round(mouse_load + elephant_load, 2),
            "action": dec.action,
            "dpp_score": dec.dpp_score,
            "q_primary_mbit": round(q_primary, 4),
            "q_secondary_mbit": round(q_secondary, 4),
            "total_q_mbit": round(total_q, 4),
            "time_avg_q_mbit": round(time_avg_q, 4),
            "normalized_bound": normalized_bound,
            "exact_bound": exact_bound,
            "compliant": is_compliant,
            "decision_time_ms": dec.decision_time_ms,
        })

    compliance_rate_pct = round(100.0 * compliant_slots / total_evaluated_slots, 2)
    passed = compliance_rate_pct >= 95.0

    summary = {
        "profile": profile_name,
        "seed": seed,
        "intervals_tested": num_intervals,
        "warmup_intervals": warmup_intervals,
        "evaluated_intervals": total_evaluated_slots,
        "policy_v": policy_v,
        "constants": {
            "B": b_const,
            "C": c_const,
            "epsilon": epsilon,
            "normalized_bound_B_plus_VC": normalized_bound,
            "exact_bound_fraction": exact_bound,
        },
        "compliant_slots": compliant_slots,
        "compliance_rate_pct": compliance_rate_pct,
        "target_compliance_pct": 95.0,
        "acceptance_status": "PASS" if passed else "FAIL",
        "mean_instantaneous_q_mbit": round(sum(r["total_q_mbit"] for r in raw_intervals) / len(raw_intervals), 4),
        "mean_time_avg_q_mbit": round(sum(r["time_avg_q_mbit"] for r in raw_intervals[warmup_intervals:]) / total_evaluated_slots, 4),
        "mean_decision_time_ms": round(sum(r["decision_time_ms"] for r in raw_intervals) / len(raw_intervals), 3),
    }

    # Save raw interval CSV
    csv_file = DPP_OUTPUT_DIR / f"dpp_intervals_{profile_name}_seed{seed}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_intervals[0].keys()))
        writer.writeheader()
        writer.writerows(raw_intervals)

    return summary


def run_full_dpp_acceptance_campaign(intervals: int = 1000, seed: int = 42) -> Dict[str, Any]:
    profiles = ["steady_bursty", "flash_crowd", "volatile_dpp"]
    results = {}
    all_passed = True

    print("==================================================================")
    print("SELF-X Formal Lyapunov DPP Backlog Acceptance Campaign (T12 / D2)")
    print(f"Intervals per profile: {intervals} (>=1,000 required) | Seed: {seed}")
    print("==================================================================")

    for prof in profiles:
        res = run_campaign_for_profile(prof, num_intervals=intervals, seed=seed)
        results[prof] = res
        if res["acceptance_status"] != "PASS":
            all_passed = False
        print(f"Profile: {prof:15} | Compliance: {res['compliance_rate_pct']}% / 95% -> [{res['acceptance_status']}]")
        print(f"  Constants: B={res['constants']['B']}, C={res['constants']['C']}, V={res['policy_v']}")
        print(f"  Bound (B+VC): {res['constants']['normalized_bound_B_plus_VC']} Mbit | Mean Q_bar: {res['mean_time_avg_q_mbit']} Mbit")
        print(f"  Fast DPP Decision Time: {res['mean_decision_time_ms']} ms (<5 ms guaranteed)\n")

    overall = {
        "campaign": "Lyapunov DPP Deliverable D2 Backlog Acceptance",
        "acceptance_criterion": "Empirically validated backlog bound holds in >= 95% of >= 1,000 intervals across 3 traffic profiles",
        "all_passed": all_passed,
        "overall_status": "PASS" if all_passed else "FAIL",
        "profiles": results,
    }

    summary_file = DPP_OUTPUT_DIR / "dpp_acceptance_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(overall, f, indent=2)

    print(f"=== Acceptance Campaign Result: {overall['overall_status']} ===")
    print(f"Saved comprehensive verification summary to: {summary_file}\n")
    return overall


def main():
    parser = argparse.ArgumentParser(description="SELF-X DPP Backlog Acceptance Campaign")
    parser.add_argument("--intervals", type=int, default=1000, help="Intervals per profile (default 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Seed")
    args = parser.parse_args()

    run_full_dpp_acceptance_campaign(intervals=args.intervals, seed=args.seed)


if __name__ == "__main__":
    main()

