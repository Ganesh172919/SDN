"""
Evaluation of Stated Latency Targets (>=20% vs Static, >=10% vs DQN)
Traceability: Task T31 | Deliverables D5, D6 | EC466 Team SDN_07

Formal Target Metrics:
  1. Target 1 (vs Static Control):
     Reduction = 100 * (Latency_{Static} - Latency_{Full}) / Latency_{Static} >= 20.0%
  2. Target 2 (vs DQN DRL Baseline):
     Reduction = 100 * (Latency_{DQN} - Latency_{Full}) / Latency_{DQN} >= 10.0%

Evaluated over matched paired seeds with standard uncertainty & confidence bounds.
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

from eval.run_table5_comparison import simulate_system
from traffic_gen import generate_schedule

OUTPUT_DIR = PROJECT_ROOT / "selfx" / "output" / "statistical_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_latency_targets(
    seeds: List[int] = [1900, 1901, 1902, 1903, 1904, 1905, 1906, 1907],
    duration_sec: int = 300,
) -> Dict[str, Any]:
    print("==================================================================")
    print("SELF-X Formal Latency Targets Evaluation (T31)")
    print("Target 1: >= 20% vs Static Ryu/POX | Target 2: >= 10% vs DQN")
    print(f"Seeds ({len(seeds)}): {seeds} | Matched Offered Workloads")
    print("==================================================================")

    static_latencies = []
    dqn_latencies = []
    full_latencies = []

    reductions_vs_static = []
    reductions_vs_dqn = []

    for seed in seeds:
        sched = generate_schedule("steady_bursty", duration_sec, seed)
        res_static = simulate_system(1, "Static Ryu/POX", sched, seed)
        res_dqn = simulate_system(2, "DQN", sched, seed)
        res_full = simulate_system(6, "Full SELF-X", sched, seed)

        l_static = res_static["mean_latency_ms"]
        l_dqn = res_dqn["mean_latency_ms"]
        l_full = res_full["mean_latency_ms"]

        red_static = 100.0 * (l_static - l_full) / l_static
        red_dqn = 100.0 * (l_dqn - l_full) / l_dqn

        static_latencies.append(l_static)
        dqn_latencies.append(l_dqn)
        full_latencies.append(l_full)

        reductions_vs_static.append(red_static)
        reductions_vs_dqn.append(red_dqn)

    n = len(seeds)
    mean_static = sum(static_latencies) / n
    mean_dqn = sum(dqn_latencies) / n
    mean_full = sum(full_latencies) / n

    mean_red_static = sum(reductions_vs_static) / n
    mean_red_dqn = sum(reductions_vs_dqn) / n

    std_red_static = math.sqrt(sum((r - mean_red_static) ** 2 for r in reductions_vs_static) / (n - 1))
    std_red_dqn = math.sqrt(sum((r - mean_red_dqn) ** 2 for r in reductions_vs_dqn) / (n - 1))

    se_static = std_red_static / math.sqrt(n)
    se_dqn = std_red_dqn / math.sqrt(n)

    pass_static = mean_red_static >= 20.0
    pass_dqn = mean_red_dqn >= 10.0
    all_passed = pass_static and pass_dqn

    report = {
        "evaluation": "Formal Latency Reduction Verification",
        "sample_size_N": n,
        "mean_latency_static_ms": round(mean_static, 2),
        "mean_latency_dqn_ms": round(mean_dqn, 2),
        "mean_latency_full_selfx_ms": round(mean_full, 2),
        "target_1_vs_static": {
            "target_reduction_pct": 20.0,
            "measured_reduction_pct": round(mean_red_static, 2),
            "std_error": round(se_static, 2),
            "confidence_interval_95": [round(mean_red_static - 2.36 * se_static, 2), round(mean_red_static + 2.36 * se_static, 2)],
            "status": "PASS" if pass_static else "FAIL",
        },
        "target_2_vs_dqn": {
            "target_reduction_pct": 10.0,
            "measured_reduction_pct": round(mean_red_dqn, 2),
            "std_error": round(se_dqn, 2),
            "confidence_interval_95": [round(mean_red_dqn - 2.36 * se_dqn, 2), round(mean_red_dqn + 2.36 * se_dqn, 2)],
            "status": "PASS" if pass_dqn else "FAIL",
        },
        "overall_status": "PASS" if all_passed else "FAIL",
    }

    out_file = OUTPUT_DIR / "latency_targets_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Mean Latencies: Static={mean_static:.2f} ms | DQN={mean_dqn:.2f} ms | Full SELF-X={mean_full:.2f} ms")
    print(f"Reduction vs Static: {mean_red_static:.2f}% (Target: >=20.0%) -> [{report['target_1_vs_static']['status']}]")
    print(f"Reduction vs DQN:    {mean_red_dqn:.2f}% (Target: >=10.0%) -> [{report['target_2_vs_dqn']['status']}]")
    print(f"Overall Result:      {report['overall_status']}")
    print(f"Saved Report to:     {out_file}\n")

    return report


def main():
    evaluate_latency_targets()


if __name__ == "__main__":
    main()

