#!/usr/bin/env python3
"""Build project diagrams and a reproducible slow-loop simulation plot set."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent
WEB_ASSET_DIR = PROJECT_ROOT / "Web" / "assets" / "visualizations"
sys.path.insert(0, str(PROJECT_ROOT / "slow-loop"))

from agentic.benchmark import run_loop  # noqa: E402
from agentic.config import WINDOW_SEC  # noqa: E402


BG = "#FAFAF7"
INK = "#19363C"
MUTED = "#62777A"
GRID = "#DEE6E2"
TEAL = "#187F73"
CORAL = "#D16F52"
GOLD = "#D29B3D"
SLATE = "#88999A"
PALE = "#EEF2EF"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": 500,
            "axes.labelsize": 9,
            "axes.labelcolor": MUTED,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.edgecolor": GRID,
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
        }
    )


def save_figure(fig: plt.Figure, filename: str) -> None:
    output_path = OUTPUT_DIR / filename
    fig.savefig(output_path, dpi=190, bbox_inches="tight", facecolor=BG)
    shutil.copyfile(output_path, WEB_ASSET_DIR / filename)
    plt.close(fig)


def run_simulation(episodes: int, seed: int) -> tuple[dict, dict]:
    learned = run_loop(
        episodes=episodes,
        seed=seed,
        profile="default",
        mode="multi",
        learn=True,
    )
    frozen = run_loop(
        episodes=episodes,
        seed=seed,
        profile="default",
        mode="multi",
        learn=False,
    )
    return learned, frozen


def write_simulation_data(learned: dict, frozen: dict, episodes: int, seed: int) -> dict:
    fields = (
        "latency_ms",
        "p95_latency_ms",
        "throughput_mbps",
        "loss_pct",
        "queue_mbit",
        "reward",
        "sla_violations",
    )
    csv_path = OUTPUT_DIR / "simulation-timeseries.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("policy", "episode", "minute", *fields))
        writer.writeheader()
        for policy_name, rows in (("governed_mock", learned["episodes"]), ("frozen_initial", frozen["episodes"])):
            for index, row in enumerate(rows, start=1):
                writer.writerow(
                    {
                        "policy": policy_name,
                        "episode": index,
                        "minute": round(index * WINDOW_SEC / 60.0, 3),
                        **{key: round(float(row[key]), 6) for key in fields},
                    }
                )

    tail_n = min(3, episodes)
    summary = {
        "provenance": "seeded slow-loop fluid simulator; deterministic mock governance model; not live Mininet/Ryu telemetry",
        "profile": "default",
        "mode": "multi",
        "seed": seed,
        "episodes": episodes,
        "window_seconds": WINDOW_SEC,
        "simulated_minutes": round(episodes * WINDOW_SEC / 60.0, 3),
        "summary_window": f"mean of final {tail_n} windows",
        "metrics": {},
    }
    for label, result in (("governed_mock", learned), ("frozen_initial", frozen)):
        summary["metrics"][label] = {
            key: round(mean(row[key] for row in result["episodes"][-tail_n:]), 6)
            for key in fields
        }
    with (OUTPUT_DIR / "simulation-summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return summary


def plot_simulation(learned: dict, frozen: dict, summary: dict) -> None:
    metrics = (
        ("latency_ms", "Mean latency", "ms"),
        ("p95_latency_ms", "95th percentile latency", "ms"),
        ("throughput_mbps", "Delivered throughput", "Mbps"),
        ("loss_pct", "Packet loss", "%"),
    )
    episode_count = len(learned["episodes"])
    x = list(range(1, episode_count + 1))
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.2))
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.09, top=0.82, wspace=0.2, hspace=0.34)
    fig.text(0.06, 0.97, "Seeded slow-loop simulation", fontsize=16, fontweight=500, ha="left", color=INK)
    fig.text(
        0.06,
        0.925,
        f"{episode_count} one-minute windows · default profile · seed {summary['seed']} · mock governance",
        color=MUTED,
        fontsize=9,
    )

    for ax, (field, title, unit) in zip(axes.flat, metrics):
        ax.plot(
            x,
            [row[field] for row in learned["episodes"]],
            color=TEAL,
            lw=2.0,
            marker="o",
            markersize=2.8,
            markevery=max(1, episode_count // 10),
            label="Governed (mock model)",
        )
        ax.plot(
            x,
            [row[field] for row in frozen["episodes"]],
            color=CORAL,
            lw=1.8,
            linestyle=(0, (4, 3)),
            marker="s",
            markersize=2.5,
            markevery=max(1, episode_count // 10),
            label="Frozen initial policy",
        )
        ax.set_title(title, loc="left", pad=9)
        ax.set_ylabel(unit)
        ax.set_xlabel("Simulated minute")
        ax.set_xlim(1, max(episode_count, 2))
        ax.set_xticks(sorted(set([1, *range(5, episode_count + 1, 5), episode_count])))
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(GRID)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.98, 0.93), frameon=False, ncol=2)
    save_figure(fig, "simulation-performance.png")


def _node(ax, x: float, y: float, width: float, height: float, label: str, *, fill: str, fontsize: float = 8) -> None:
    shape = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        facecolor=fill,
        edgecolor=INK,
        linewidth=0.9,
    )
    ax.add_patch(shape)
    ax.text(x, y, label, ha="center", va="center", color=INK, fontsize=fontsize, fontweight=500)


def _flow_box(ax, x: float, y: float, width: float, height: float, label: str, *, fill: str, fontsize: float = 7.8) -> None:
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.05,rounding_size=0.09",
        facecolor=fill,
        edgecolor=INK,
        linewidth=0.9,
    )
    ax.add_patch(patch)
    ax.text(x, y, label, ha="center", va="center", color=INK, fontsize=fontsize, fontweight=500, linespacing=1.2)


def _arrow(ax, start: tuple[float, float], end: tuple[float, float], *, color: str = SLATE, dashed: bool = False) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1.15,
            color=color,
            linestyle=(0, (3, 2)) if dashed else "solid",
            shrinkA=2,
            shrinkB=2,
        )
    )


def plot_system_overview() -> None:
    fig, ax = plt.subplots(figsize=(14, 8.4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9.5)
    ax.axis("off")
    fig.subplots_adjust(left=0.025, right=0.975, bottom=0.04, top=0.91)
    fig.text(0.04, 0.965, "SELF-X system overview", fontsize=17, fontweight=500, ha="left", color=INK)
    fig.text(
        0.04,
        0.927,
        "Current live-testbed MVP, separate simulator prototype, and authenticated dashboard",
        fontsize=9.2,
        ha="left",
        color=MUTED,
    )

    # Current MVP: its safety-gated flow loop talks to the real Ryu/Mininet testbed.
    ax.add_patch(
        FancyBboxPatch((0.25, 5.1), 13.5, 3.45, boxstyle="round,pad=0.05,rounding_size=0.12",
                       facecolor="#F4F7F5", edgecolor=GRID, linewidth=1.0)
    )
    ax.text(0.55, 8.2, "CURRENT MVP · LIVE TESTBED PATH", color=TEAL, fontsize=9.4, fontweight=600)
    ax.text(0.55, 7.82, "Mininet (4 switches / 8 hosts)  ↔  Ryu ofctl_rest", color=INK, fontsize=9.2, fontweight=500)

    loop_labels = [
        "OBSERVE\nRyu stats + ping",
        "DECIDE\nstructured action",
        "SAFETY GATE\nfail closed",
        "ACT\nflow / meter",
        "WAIT +\nobserve after",
        "COMPUTE\nreward",
        "REFLECT\noutcome",
        "MEMORIZE\nTop-30 JSON",
    ]
    loop_x = [1.25 + i * 1.64 for i in range(8)]
    for i, (x, label) in enumerate(zip(loop_x, loop_labels)):
        fill = "#E2EFEC" if i in (0, 3, 7) else "#FFFFFF"
        _flow_box(ax, x, 6.75, 1.39, 0.82, label, fill=fill, fontsize=7.5)
        if i < len(loop_x) - 1:
            _arrow(ax, (x + 0.72, 6.75), (loop_x[i + 1] - 0.72, 6.75))

    # Memory context is retrieved on later cycles; this is an agent loop, not a one-way pipeline.
    ax.plot([loop_x[-1], loop_x[-1]], [6.32, 5.65], color=SLATE, lw=1.0, linestyle=(0, (3, 2)))
    _arrow(ax, (loop_x[-1] - 0.06, 5.65), (loop_x[0] + 0.08, 5.65), dashed=True)
    ax.plot([loop_x[0], loop_x[0]], [5.65, 6.32], color=SLATE, lw=1.0, linestyle=(0, (3, 2)))
    ax.text(7.0, 5.38, "Memory is available as few-shot context on the next cycle", ha="center", color=MUTED, fontsize=7.8)

    # Separate simulator/governance prototype; deliberately no arrow to Ryu or the MVP lane.
    ax.add_patch(
        FancyBboxPatch((0.25, 1.35), 7.75, 3.35, boxstyle="round,pad=0.05,rounding_size=0.12",
                       facecolor="#F7F4EC", edgecolor="#E8DAB7", linewidth=1.0)
    )
    ax.text(0.55, 4.36, "SLOW-LOOP PROTOTYPE · SIMULATOR ONLY", color="#A87820", fontsize=9.0, fontweight=600)
    proto_x = [1.18, 3.02, 4.86, 6.72]
    proto_labels = ["simulator\ntelemetry", "specialists +\ngovernor", "validate policy\nupdate (V, weights, mask)", "fluid\nsimulator"]
    for i, (x, label) in enumerate(zip(proto_x, proto_labels)):
        fill = "#FFFDF7" if i != 2 else "#F5E8C9"
        _flow_box(ax, x, 3.08, 1.55, 0.92, label, fill=fill, fontsize=7.6)
        if i < len(proto_x) - 1:
            _arrow(ax, (x + 0.8, 3.08), (proto_x[i + 1] - 0.8, 3.08), color=GOLD)
    _arrow(ax, (6.72, 2.56), (1.18, 2.56), color=GOLD, dashed=True)
    ax.text(4.0, 2.27, "closed-loop simulation · not connected to selfx/ or Ryu", ha="center", color=MUTED, fontsize=7.7)
    ax.text(0.55, 1.66, "Heuristic drift + penalty prototype; it does not establish the planned live DPP guarantee.",
            color=MUTED, fontsize=7.6)

    # Dashboard paths remain distinct: local browser simulation and read-only live status.
    ax.add_patch(
        FancyBboxPatch((8.25, 1.35), 5.5, 3.35, boxstyle="round,pad=0.05,rounding_size=0.12",
                       facecolor="#F1F5F8", edgecolor="#CCDCE5", linewidth=1.0)
    )
    ax.text(8.55, 4.36, "AUTHENTICATED WEB DASHBOARD", color="#38728C", fontsize=9.0, fontweight=600)
    _flow_box(ax, 11.0, 3.72, 2.6, 0.62, "Browser UI + session-protected server", fill="#E5EFF4", fontsize=8.0)
    _flow_box(ax, 9.72, 2.65, 2.05, 0.92, "SIMULATION MODE\nbrowser-local generated values", fill="#FFFFFF", fontsize=7.4)
    _flow_box(ax, 12.25, 2.65, 2.28, 0.92, "LIVE MODE\nstatus / read-only GET\nmetrics unavailable; writes disabled", fill="#FFFFFF", fontsize=7.1)
    _arrow(ax, (10.55, 3.38), (9.84, 3.14), color=SLATE)
    _arrow(ax, (11.45, 3.38), (12.05, 3.14), color=SLATE)
    ax.text(11.0, 1.86, "Project figures shown in the dashboard are generated assets, not live network charts.",
            ha="center", color=MUTED, fontsize=7.3)

    save_figure(fig, "system-overview.png")


def plot_topology_models() -> None:
    fig, ax = plt.subplots(figsize=(14, 5.3), constrained_layout=True)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 5.1)
    ax.axis("off")
    fig.suptitle("Two network views in the repository", fontsize=16, fontweight=500, x=0.04, ha="left", y=1.05)
    ax.text(0.15, 4.65, "SELF-X MVP testbed", fontsize=12, fontweight=500, color=INK)
    ax.text(7.0, 4.65, "Slow-loop simulator abstraction", fontsize=12, fontweight=500, color=INK)

    switch_x = [0.65, 2.15, 3.65, 5.15]
    switch_y = 2.25
    controller_x = 2.9
    _node(ax, controller_x, 3.8, 2.0, 0.5, "Ryu controller", fill="#E7EFEC", fontsize=8.5)
    ax.plot([controller_x, controller_x], [3.55, 3.25], color=SLATE, linestyle=(0, (3, 3)), lw=1.2)
    ax.plot([switch_x[0], switch_x[-1]], [3.25, 3.25], color=SLATE, linestyle=(0, (3, 3)), lw=1.2)
    for sx in switch_x:
        ax.plot([sx, sx], [3.25, 2.55], color=SLATE, linestyle=(0, (3, 3)), lw=1.1)
        _node(ax, sx, switch_y, 0.78, 0.54, f"s{switch_x.index(sx) + 1}", fill="#E2EFEC", fontsize=9)

    for i in range(3):
        left, right = switch_x[i], switch_x[i + 1]
        ax.plot([left + 0.4, right - 0.4], [switch_y, switch_y], color=INK, lw=2)
        ax.text((left + right) / 2, 2.58, "10 Mbps · 2 ms", ha="center", color=MUTED, fontsize=7.4)

    host_num = 1
    for sx in switch_x:
        for offset in (-0.24, 0.24):
            hx, hy = sx + offset, 0.85
            ax.plot([sx, hx], [1.98, 1.08], color=SLATE, lw=1.0)
            _node(ax, hx, hy, 0.48, 0.36, f"h{host_num}", fill="#F1F3F0", fontsize=7.6)
            host_num += 1

    ax.plot([6.35, 6.35], [0.45, 4.3], color=GRID, lw=1.2)
    ax.text(7.0, 3.95, "s2", ha="center", va="center", fontsize=9, fontweight=500, color=INK,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "#E2EFEC", "edgecolor": INK, "linewidth": 0.9})
    ax.text(11.8, 3.95, "s3", ha="center", va="center", fontsize=9, fontweight=500, color=INK,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "#E2EFEC", "edgecolor": INK, "linewidth": 0.9})

    upper_path = MplPath([(7.38, 3.95), (9.4, 4.9), (11.42, 3.95)], [MplPath.MOVETO, MplPath.CURVE3, MplPath.CURVE3])
    lower_path = MplPath([(7.38, 3.95), (9.4, 2.65), (11.42, 3.95)], [MplPath.MOVETO, MplPath.CURVE3, MplPath.CURVE3])
    ax.add_patch(PathPatch(upper_path, facecolor="none", edgecolor=TEAL, lw=2.5))
    ax.add_patch(PathPatch(lower_path, facecolor="none", edgecolor=GOLD, lw=2.5))
    ax.text(9.4, 4.55, "Path A · 10 Mbps · 5 ms", ha="center", va="center", color=TEAL, fontsize=8.4, fontweight=500)
    ax.text(9.4, 3.0, "Path B · 10 Mbps · 12 ms", ha="center", va="center", color=INK, fontsize=8.4, fontweight=500)
    ax.text(9.4, 1.9, "Simplified two-path fluid model; not a second drawing of the MVP wiring.",
            ha="center", va="center", color=MUTED, fontsize=8.0, wrap=True)
    ax.text(0.15, 0.25, "4 switches · 8 hosts · linear chain", color=MUTED, fontsize=8.5)
    save_figure(fig, "topology-models.png")


def plot_implementation_status() -> None:
    phases = [
        ("1  Dashboard foundation", "Complete"),
        ("2  Integration foundation", "Planned"),
        ("3  Fast-timescale DPP", "Planned"),
        ("4  Slow-timescale governance", "Partial"),
        ("5  Safety-gated adaptation", "Planned"),
        ("6  Experience and improvement", "Partial"),
        ("7  Evaluation and evidence", "Partial"),
    ]
    category_x = {"Planned": 0, "Partial": 1, "Complete": 2}
    category_color = {"Planned": SLATE, "Partial": GOLD, "Complete": TEAL}
    counts = {status: sum(s == status for _, s in phases) for status in category_x}
    fig, ax = plt.subplots(figsize=(10.5, 5.4), constrained_layout=True)
    y = list(range(len(phases)))
    for idx, ((_, status), ypos) in enumerate(zip(phases, y)):
        ax.scatter(category_x[status], ypos, s=100, color=category_color[status], zorder=3, edgecolor=BG, linewidth=1.2)
    ax.set_yticks(y, [name for name, _ in phases])
    ax.invert_yaxis()
    ax.set_xlim(-0.4, 2.4)
    ax.set_xticks(
        [0, 1, 2],
        [f"Planned\n{counts['Planned']}", f"Partial\n{counts['Partial']}", f"Complete\n{counts['Complete']}"],
    )
    ax.tick_params(axis="y", length=0, pad=10)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.grid(axis="y", color=GRID, linewidth=0.75)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("Roadmap phase status", loc="left", fontsize=16, pad=22)
    ax.text(
        0.0,
        1.015,
        "Status labels follow the repository README; partial phases include prototype or MVP scope.",
        transform=ax.transAxes,
        color=MUTED,
        fontsize=9,
    )
    save_figure(fig, "implementation-status.png")


def plot_safety_guardrails() -> None:
    rules = [
        ("Maximum flow traffic drop", "Allowed up to", 100.0, 20.0, "%", "≤ 20%"),
        ("Maximum projected link utilization", "Allowed up to", 110.0, 90.0, "%", "≤ 90%"),
        ("Minimum rate-limit setting", "Must be at least", 1024.0, 512.0, "kbps", "≥ 512 kbps"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(9.8, 5.7))
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.1, top=0.79, hspace=0.9)
    fig.text(0.07, 0.97, "MVP safety guardrails", fontsize=16, fontweight=500, ha="left", color=INK)
    fig.text(0.07, 0.925, "Configured bounds in selfx/config.py and enforced by selfx/safety.py", color=MUTED, fontsize=9)
    for ax, (label, qualifier, max_value, boundary, unit, callout) in zip(axes, rules):
        ax.axvspan(0, max_value, color=PALE, zorder=0)
        if "Minimum" in label:
            ax.axvspan(boundary, max_value, color=TEAL, alpha=0.2, zorder=1)
        else:
            ax.axvspan(0, boundary, color=TEAL, alpha=0.2, zorder=1)
        ax.axvline(boundary, color=CORAL, lw=1.8, linestyle=(0, (3, 2)), zorder=2)
        ax.text(0.0, 1.12, label, transform=ax.transAxes, ha="left", va="bottom", color=INK, fontsize=9.4, fontweight=500)
        ax.text(1.0, 1.12, f"{qualifier} {callout}", transform=ax.transAxes, ha="right", va="bottom", color=INK, fontsize=9.0)
        ax.set_xlim(0, max_value)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        ax.set_xlabel(unit, labelpad=3)
        ax.grid(axis="x", color=BG, linewidth=0.8)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
    save_figure(fig, "safety-guardrails.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=30, help="simulated 60-second windows (default: 30)")
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()
    learned, frozen = run_simulation(args.episodes, args.seed)
    summary = write_simulation_data(learned, frozen, args.episodes, args.seed)
    plot_simulation(learned, frozen, summary)
    plot_system_overview()
    plot_topology_models()
    plot_implementation_status()
    plot_safety_guardrails()
    print(f"Created visualizations in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
