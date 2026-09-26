"""
Phase 5 — plotting.

Reads eval/logs/A0.csv, A1.csv, A2.csv (as written by run_ablation.py)
and produces:

  eval/plots/latency_comparison.png     — A0 vs A1 vs A2
  eval/plots/throughput_comparison.png  — A0 vs A1 vs A2
  eval/plots/loss_comparison.png        — A0 vs A1 vs A2
  eval/plots/reward_trend.png           — A1 vs A2 reward per cycle, plus a
                                           rolling mean, so the "A2 improves,
                                           A1 doesn't" acceptance criterion is
                                           visible at a glance.

Run after run_ablation.py has produced all three CSVs:
    python3 -m eval.plot_results
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config


def _read_csv(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def _series(rows, field):
    out = []
    for r in rows:
        v = r.get(field, "")
        out.append(float(v) if v not in ("", None) else None)
    return out


def _rolling_mean(values, window=10):
    out = []
    for i in range(len(values)):
        window_vals = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        out.append(sum(window_vals) / len(window_vals) if window_vals else None)
    return out


def _plot_metric_comparison(data_by_condition, field, ylabel, title, out_path):
    plt.figure(figsize=(9, 5))
    for condition, rows in data_by_condition.items():
        cycles = [int(r["cycle"]) for r in rows]
        values = _series(rows, field)
        plt.plot(cycles, values, label=condition, marker=".", markersize=3, linewidth=1.3)
    plt.xlabel("Control-loop cycle")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def _plot_reward_trend(data_by_condition, out_path):
    plt.figure(figsize=(9, 5))
    for condition in ("A1", "A2"):
        rows = data_by_condition.get(condition)
        if not rows:
            continue
        cycles = [int(r["cycle"]) for r in rows]
        rewards = _series(rows, "reward")
        rolling = _rolling_mean(rewards, window=10)
        plt.plot(cycles, rewards, alpha=0.25, label=f"{condition} reward (raw)")
        plt.plot(cycles, rolling, linewidth=2.2, label=f"{condition} reward (rolling mean)")
    plt.axhline(0, color="black", linewidth=0.8, alpha=0.5)
    plt.xlabel("Control-loop cycle")
    plt.ylabel("Reward")
    plt.title("Reward trend: A2 (full reflection + memory) vs A1 (memory disabled)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", default=config.EVAL_LOG_DIR)
    parser.add_argument("--out-dir", default=config.EVAL_PLOT_DIR)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    data_by_condition = {}
    for condition in config.CONDITIONS:
        path = os.path.join(args.log_dir, f"{condition}.csv")
        if os.path.exists(path):
            data_by_condition[condition] = _read_csv(path)
        else:
            print(f"warning: missing {path}, skipping {condition} in comparison plots")

    _plot_metric_comparison(
        data_by_condition, "latency_ms", "Latency (ms)",
        "Latency: A0 (static) vs A1 (agent, no memory) vs A2 (agent + memory)",
        os.path.join(args.out_dir, "latency_comparison.png"),
    )
    _plot_metric_comparison(
        data_by_condition, "throughput_kbps", "Throughput (kbps)",
        "Throughput: A0 (static) vs A1 (agent, no memory) vs A2 (agent + memory)",
        os.path.join(args.out_dir, "throughput_comparison.png"),
    )
    _plot_metric_comparison(
        data_by_condition, "loss_pct", "Loss (%)",
        "Loss: A0 (static) vs A1 (agent, no memory) vs A2 (agent + memory)",
        os.path.join(args.out_dir, "loss_comparison.png"),
    )
    _plot_reward_trend(data_by_condition, os.path.join(args.out_dir, "reward_trend.png"))

    print(f"Plots written to {args.out_dir}/")


if __name__ == "__main__":
    main()
