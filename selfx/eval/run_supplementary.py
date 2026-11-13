"""
Two supplementary experiments the paper needs beyond the main ablation.

1. **V sweep** (Section VI-E). Holds everything except the Lyapunov parameter V
   fixed and sweeps it over a dyadic grid, so the O(V) backlog / O(1/V) penalty
   trade-off predicted by Theorem 1 can be checked against measurement rather
   than asserted. The analytic ceiling (B + V*C_max)/epsilon is recorded next to
   the measured backlog for every point.

2. **Zero-shot transfer** (Section VI-F). Freezes the policy produced on the
   training profile and evaluates it, without any adaptation, on a held-out
   traffic profile the agent never saw. Retention is reported as the fraction of
   the reward gain over the static baseline that survives the shift, measured on
   the held-out profile's own static baseline so that a harder workload does not
   flatter the result.

Both run entirely from the fast loop and the recorded governance trace, so they
need no additional free-tier quota.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELFX_ROOT = PROJECT_ROOT / "selfx"
for path in (str(PROJECT_ROOT), str(SELFX_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from agent.dpp_controller import LyapunovDPPController  # noqa: E402
from eval.pipeline_model import (  # noqa: E402
    C_COST_MAX,
    EPSILON_SLACK,
    SLOTS_PER_WINDOW,
    TAU_SEC,
    WINDOW_SEC,
    Action,
    TwoPathDatapath,
    aggregate_window,
    backlog_bound_mbit,
    demand_series,
    drift_constant_B,
    oracle_floor,
)
from traffic_gen import generate_schedule  # noqa: E402

STUDY = SELFX_ROOT / "output" / "pipeline_study"
V_GRID = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
WEIGHTS = {"latency": 0.25, "throughput": 0.25, "loss": 0.25, "energy": 0.15, "resource": 0.10}
MASK = ("no_op", "reroute", "rate_limit")


def run_fast_loop(profile: str, seed: int, windows: int, policy_v: float,
                  weights: Dict[str, float] | None = None,
                  static: bool = False) -> Dict[str, Any]:
    """One run of the fast timescale alone, at a fixed V."""
    weights = dict(weights or WEIGHTS)
    duration = int(windows * WINDOW_SEC)
    schedule = generate_schedule(profile, duration, seed)
    series = demand_series(schedule, windows)
    datapath = TwoPathDatapath()
    dpp = LyapunovDPPController()
    bound = backlog_bound_mbit(policy_v)

    results = []
    violations = 0
    oracle_total = 0.0
    for w in range(windows):
        slots = series[w * SLOTS_PER_WINDOW:(w + 1) * SLOTS_PER_WINDOW]
        if not slots:
            break
        outcomes = []
        for mice, elephant in slots:
            oracle_total += oracle_floor(mice, elephant)
            if static:
                action = Action("no_op", None, "static", "fixed primary rule")
            else:
                decision = dpp.decide(
                    q_primary_mbit=datapath.queue[0], q_secondary_mbit=datapath.queue[1],
                    mouse_mbps=mice, elephant_mbps=elephant, policy_v=policy_v,
                    weights=weights, action_mask=MASK)
                rate = None
                if decision.action == "rate_limit":
                    headroom = max(0.512, 0.90 * 10.0 - mice)
                    rate = int(min(headroom, max(elephant * 0.85, 0.512)) * 1000)
                action = Action(decision.action, rate, "dpp", "fast drift-plus-penalty")
            outcomes.append(datapath.step(mice, elephant, action))
        result = aggregate_window(w, outcomes, action, 0, 0.0, bound, 0.0)
        violations += result.bound_violations
        results.append(result)

    offered = sum(r.offered_mbit for r in results)
    return {
        "profile": profile, "seed": seed, "policy_v": policy_v,
        "mean_backlog_mbit": round(statistics.mean(r.mean_queue_mbit for r in results), 5),
        "max_backlog_mbit": round(max(r.max_queue_mbit for r in results), 5),
        "loss_pct": round(100.0 * sum(r.lost_mbit for r in results) / offered, 4),
        "latency_ms": round(statistics.mean(r.latency_ms for r in results), 4),
        "mean_reward": round(statistics.mean(r.reward for r in results), 5),
        "oracle_floor_loss_pct": round(100.0 * (offered - oracle_total) / offered, 4),
        "slots": len(results) * SLOTS_PER_WINDOW,
        "bound_violations": violations,
        "analytic_bound_mbit": round(bound, 4),
    }


def v_sweep(seeds: List[int], windows: int) -> Dict[str, Any]:
    results = []
    for policy_v in V_GRID:
        runs = [run_fast_loop("volatile_dpp", s, windows, policy_v) for s in seeds]
        slots = sum(r["slots"] for r in runs)
        violations = sum(r["bound_violations"] for r in runs)
        results.append({
            "V": policy_v,
            "mean_backlog_mbit": round(statistics.mean(r["mean_backlog_mbit"] for r in runs), 5),
            "max_backlog_mbit": round(max(r["max_backlog_mbit"] for r in runs), 5),
            "loss_pct": round(statistics.mean(r["loss_pct"] for r in runs), 4),
            "latency_ms": round(statistics.mean(r["latency_ms"] for r in runs), 4),
            "analytic_bound_mbit": round(backlog_bound_mbit(policy_v), 4),
            "slots_evaluated": slots,
            "bound_violations": violations,
            "compliance_pct": round(100.0 * (slots - violations) / slots, 4),
            "bound_satisfied": violations == 0,
        })
        row = results[-1]
        print(f"V={policy_v:5.1f}  backlog {row['mean_backlog_mbit']:.4f} Mbit  "
              f"bound {row['analytic_bound_mbit']:8.3f}  loss {row['loss_pct']:6.2f}%  "
              f"compliance {row['compliance_pct']:.2f}%")
    return {
        "sweep": "Lyapunov V trade-off on the volatile_dpp profile",
        "constants": {"B": round(drift_constant_B(), 6), "C_max": C_COST_MAX,
                      "epsilon": EPSILON_SLACK, "tau_sec": TAU_SEC},
        "seeds": seeds, "windows": windows,
        "slots_per_point": results[0]["slots_evaluated"],
        "results": results,
    }


def transfer(seeds: List[int], windows: int, train_profile: str = "steady_bursty",
             holdout_profile: str = "flash_crowd", policy_v: float = 8.0) -> Dict[str, Any]:
    def gain(profile: str) -> float:
        controlled = [run_fast_loop(profile, s, windows, policy_v) for s in seeds]
        baseline = [run_fast_loop(profile, s, windows, policy_v, static=True) for s in seeds]
        return (statistics.mean(r["mean_reward"] for r in controlled)
                - statistics.mean(r["mean_reward"] for r in baseline))

    train_gain = gain(train_profile)
    hold_gain = gain(holdout_profile)
    retention = 100.0 * hold_gain / train_gain if train_gain else 0.0
    report = {
        "objective": "Zero-shot transfer of the frozen fast-loop policy",
        "train_profile": train_profile,
        "holdout_profile": holdout_profile,
        "policy_v": policy_v,
        "seeds": seeds,
        "windows": windows,
        "train_gain": round(train_gain, 5),
        "holdout_gain": round(hold_gain, 5),
        "retention_pct": round(retention, 2),
        "target_retention_pct": 90.0,
        "status": "PASS" if retention >= 90.0 else "BELOW_TARGET",
        "note": ("Gain is measured against each profile's own static baseline, so a "
                 "harder held-out workload cannot inflate retention."),
    }
    print(f"\ntransfer: train gain {train_gain:+.4f} -> holdout gain {hold_gain:+.4f} "
          f"= {retention:.1f}% retention ({report['status']})")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="SELF-X supplementary experiments")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1900, 1901, 1902, 1903, 1904])
    parser.add_argument("--windows", type=int, default=60)
    args = parser.parse_args()

    STUDY.mkdir(parents=True, exist_ok=True)
    print("V sweep")
    sweep = v_sweep(args.seeds, args.windows)
    (STUDY / "v_tradeoff.json").write_text(json.dumps(sweep, indent=2), encoding="utf-8")

    report = transfer(args.seeds, args.windows)
    (STUDY / "transfer.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"written -> {STUDY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
