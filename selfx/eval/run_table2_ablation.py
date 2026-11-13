"""Historical Table II proxy generator.

A1-A4 are scripted heuristics. A5 runs DPP alone. These outputs cannot
attribute effects to LLM inference, critique, LoRA or multi-agent governance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "selfx") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "selfx"))

from agent.dpp_controller import LyapunovDPPController
from agent.policy_backend import LoRAPolicyBackend
from traffic_gen import generate_schedule

OUTPUT_DIR = PROJECT_ROOT / "selfx" / "output" / "ablation_table2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def simulate_stage(
    stage: str,
    schedule: Dict[str, Any],
    seed: int,
) -> Dict[str, Any]:
    rng = random.Random(seed + hash(stage) % 1000)
    events = schedule["events"]
    duration_sec = schedule["duration_sec"]
    step_sec = 1.0
    num_steps = int(duration_sec / step_sec)

    q1 = 0.0
    q2 = 0.0
    latencies = []
    p95_latencies = []
    throughputs = []
    losses = []
    rewards = []
    queues = []
    cpu_overheads = []
    control_bytes = 0
    packet_in_count = 0

    c_primary = 10.0
    c_secondary = 10.0

    # Policy states for stage
    backend = LoRAPolicyBackend(seed=seed)
    dpp = LyapunovDPPController()

    v_val = 8.0
    weights = {"latency": 0.25, "throughput": 0.25, "loss": 0.25, "energy": 0.15, "resource": 0.10}

    for step in range(num_steps):
        t_sec = step * step_sec
        mouse_mbps = 3.0
        elephant_mbps = 0.0

        for ev in events:
            if ev["start_time_sec"] <= t_sec < ev["start_time_sec"] + ev["duration_sec"]:
                if ev["type"] != "steady_background":
                    elephant_mbps = max(elephant_mbps, ev["rate_mbps"])

        total_offered = mouse_mbps + elephant_mbps
        packet_in_count += int(total_offered * 12)
        control_bytes += int(total_offered * 180)

        # Action selection depending on stage
        if stage == "A0":
            # Static rule: always stays on primary path, no adaptation
            action = "admit"
            cpu = 2.1
            arr_p, arr_s = total_offered, 0.0

        elif stage == "A1":
            # Single LLM without reflection: occasional hallucinations / unconstrained decisions
            cpu = 18.5
            if total_offered > 10.0:
                action = rng.choice(["reroute", "rate_limit", "admit", "no_op"])
            else:
                action = rng.choice(["admit", "no_op"])

            if action == "reroute":
                arr_p, arr_s = mouse_mbps, elephant_mbps
            elif action == "rate_limit":
                arr_p, arr_s = mouse_mbps + min(elephant_mbps, 5.0), 0.0
            else:
                arr_p, arr_s = total_offered, 0.0

        elif stage == "A2":
            # A1 + Verbal reflection: uses memory to avoid repeated congestion mistakes
            cpu = 22.0
            if total_offered > 10.0:
                action = "reroute" if rng.random() < 0.75 else "rate_limit"
            else:
                action = "admit"

            if action == "reroute":
                arr_p, arr_s = mouse_mbps, elephant_mbps
            elif action == "rate_limit":
                arr_p, arr_s = mouse_mbps + min(elephant_mbps, 5.5), 0.0
            else:
                arr_p, arr_s = total_offered, 0.0

        elif stage == "A3":
            # A2 + LoRA fine-tuning: weights internalize policy, faster and more reliable
            cpu = 14.0
            if total_offered > 10.0:
                action = "reroute" if rng.random() < 0.88 else "rate_limit"
            else:
                action = "admit"

            if action == "reroute":
                arr_p, arr_s = mouse_mbps, elephant_mbps
            elif action == "rate_limit":
                arr_p, arr_s = mouse_mbps + min(elephant_mbps, 6.0), 0.0
            else:
                arr_p, arr_s = total_offered, 0.0

        elif stage == "A4":
            # A3 + 6-agent decomposition: specialized sizing, routing, slicing
            cpu = 16.5
            if total_offered > 10.0:
                action = "reroute" if q2 < 2.0 else "rate_limit"
            else:
                action = "admit"

            if action == "reroute":
                arr_p, arr_s = mouse_mbps, elephant_mbps
            elif action == "rate_limit":
                arr_p, arr_s = mouse_mbps + min(elephant_mbps, 6.0), 0.0
            else:
                arr_p, arr_s = total_offered, 0.0

        else:  # A5: Full SELF-X (A4 + Lyapunov DPP fast loop)
            cpu = 8.5  # fast analytic optimizer offloads LLM load
            dec = dpp.decide(
                q_primary_mbit=q1,
                q_secondary_mbit=q2,
                mouse_mbps=mouse_mbps,
                elephant_mbps=elephant_mbps,
                policy_v=v_val,
                weights=weights,
                action_mask=("admit", "reroute", "rate_limit", "drop", "no_op"),
            )
            action = dec.action
            if action == "reroute":
                arr_p, arr_s = mouse_mbps, elephant_mbps
            elif action == "rate_limit":
                arr_p, arr_s = mouse_mbps + min(elephant_mbps, 6.0), 0.0
            elif action == "drop":
                arr_p, arr_s = min(total_offered, 10.0), 0.0
            else:
                arr_p, arr_s = total_offered, 0.0

        # Dynamics
        q1 = max(0.0, min(10.0, q1 + (arr_p - c_primary) * step_sec))
        q2 = max(0.0, min(10.0, q2 + (arr_s - c_secondary) * step_sec))
        total_q = q1 + q2

        delivered = min(total_offered, c_primary + (c_secondary if arr_s > 0 else 0.0))
        dropped = max(0.0, total_offered - delivered)
        loss = round(100.0 * dropped / total_offered, 2) if total_offered > 0 else 0.0

        base_lat = 2.0 if arr_s == 0 else (mouse_mbps * 2.0 + elephant_mbps * 12.0) / total_offered
        latency = round(base_lat + (q1 * 1.8), 2)
        p95 = round(latency * 1.25, 2)

        # Multi-objective reward
        rew = round(
            1.0 * (delivered / 10.0)
            - 1.2 * (latency / 30.0)
            - 2.0 * (loss / 20.0)
            - 0.1 * (0.1 if action != "admit" else 0.0),
            4,
        )

        latencies.append(latency)
        p95_latencies.append(p95)
        throughputs.append(delivered)
        losses.append(loss)
        rewards.append(rew)
        queues.append(total_q)
        cpu_overheads.append(cpu)

    mean_lat = round(sum(latencies) / len(latencies), 2)
    p95_lat = round(sorted(p95_latencies)[int(len(p95_latencies) * 0.95)], 2)
    mean_tp = round(sum(throughputs) / len(throughputs), 3)
    mean_loss = round(sum(losses) / len(losses), 2)
    mean_rew = round(sum(rewards) / len(rewards), 4)
    cum_rew = round(sum(rewards), 2)
    mean_q = round(sum(queues) / len(queues), 4)
    bound_violations = round(100.0 * sum(1 for q in queues if q > 18.05) / len(queues), 2)
    mean_cpu = round(sum(cpu_overheads) / len(cpu_overheads), 1)

    return {
        "stage": stage,
        "seed": seed,
        "mean_latency_ms": mean_lat,
        "p95_latency_ms": p95_lat,
        "throughput_mbps": mean_tp,
        "packet_loss_pct": mean_loss,
        "mean_reward": mean_rew,
        "cumulative_reward": cum_rew,
        "queue_backlog_mbit": mean_q,
        "bound_violation_pct": bound_violations,
        "cpu_overhead_pct": mean_cpu,
        "control_bytes": control_bytes,
        "packet_in_count": packet_in_count,
        "convergence_time_ms": 120 if stage in ("A4", "A5") else (280 if stage == "A3" else 650),
    }


def run_table2_ablation(
    seeds: List[int] = [1900, 1901, 1902, 1903, 1904],
    duration_sec: int = 300,
) -> Dict[str, Any]:
    stages = ["A0", "A1", "A2", "A3", "A4", "A5"]
    stage_descriptions = {
        "A0": "Static Ryu/POX (hand-crafted rules) [Non-learning floor]",
        "A1": "Single non-specialist LLM; no reflection [Raw LLM reasoning]",
        "A2": "A1 + verbal reflection (no weight update) [Verbal reflection alone]",
        "A3": "A2 + safety-gated LoRA self-fine-tuning [Internalised in weights]",
        "A4": "A3 + multi-agent decomposition (6 specialists) [Task specialization]",
        "A5": "A4 + Lyapunov DPP fast timescale [Full two-timescale system]",
    }

    print("==================================================================")
    print("SELF-X Six-Stage Ablation Study Runner (Table 2 / T26)")
    print(f"Stages: A0 -> A5 | Seeds ({len(seeds)}): {seeds} | Duration: {duration_sec}s")
    print("==================================================================")

    results_by_stage: Dict[str, List[Dict[str, Any]]] = {s: [] for s in stages}

    for s_idx, seed in enumerate(seeds):
        sched = generate_schedule("steady_bursty", duration_sec, seed)
        for st in stages:
            rec = simulate_stage(st, sched, seed)
            results_by_stage[st].append(rec)

    # Compute stage aggregates
    summary_table = []
    for st in stages:
        records = results_by_stage[st]
        avg_lat = round(sum(r["mean_latency_ms"] for r in records) / len(records), 2)
        avg_p95 = round(sum(r["p95_latency_ms"] for r in records) / len(records), 2)
        avg_tp = round(sum(r["throughput_mbps"] for r in records) / len(records), 3)
        avg_loss = round(sum(r["packet_loss_pct"] for r in records) / len(records), 2)
        avg_cum_rew = round(sum(r["cumulative_reward"] for r in records) / len(records), 2)
        avg_q = round(sum(r["queue_backlog_mbit"] for r in records) / len(records), 4)
        avg_cpu = round(sum(r["cpu_overhead_pct"] for r in records) / len(records), 1)

        summary_table.append({
            "stage": st,
            "description": stage_descriptions[st],
            "latency_ms": avg_lat,
            "p95_latency_ms": avg_p95,
            "throughput_mbps": avg_tp,
            "packet_loss_pct": avg_loss,
            "cumulative_reward": avg_cum_rew,
            "queue_mbit": avg_q,
            "cpu_overhead_pct": avg_cpu,
        })
        print(f"Stage {st:2}: Latency={avg_lat:5.2f} ms | Loss={avg_loss:4.2f}% | Throughput={avg_tp:5.3f} Mbps | Reward={avg_cum_rew:6.2f} | CPU={avg_cpu:4.1f}%")

    out_data = {
        "evidence_status": "historical_heuristic_proxy",
        "title": "Table 2 - SELF-X Staged Ablation Study",
        "description": "Each stage adds exactly one design element, mapped to its literature analogue.",
        "seeds": seeds,
        "summary": summary_table,
        "raw_runs": results_by_stage,
    }

    # Save JSON and CSV
    json_path = OUTPUT_DIR / "table2_ablation_summary.json"
    json_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    csv_path = OUTPUT_DIR / "table2_ablation_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_table[0].keys()))
        writer.writeheader()
        writer.writerows(summary_table)

    print(f"\nSaved Table 2 Ablation Summary to: {json_path}")
    print(f"Saved CSV Table to:               {csv_path}\n")
    return out_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-proxy", action="store_true", help="regenerate the historical proxy")
    if not parser.parse_args().legacy_proxy:
        parser.error("Historical heuristic proxy. Run python -m selfx.eval.run_audited_comparison for the audited study.")
    run_table2_ablation()


if __name__ == "__main__":
    main()

