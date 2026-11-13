"""
Regenerate every figure in the paper from ``output/pipeline_study``.

All figures are written as vector PDF (for LaTeX) plus PNG (for the slide deck)
into ``paper/figures``. Nothing here hard-codes a number: if the study is re-run,
the figures and the numbers in the paper move together.

Palette: the validated categorical slots blue / orange / aqua / yellow for
unrelated series, and a single-hue blue ramp for the ordered S0..S5 stages
(a progression is magnitude-like, not categorical). Every low-contrast fill
carries a direct value label, which is the relief rule for those slots.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELFX_ROOT = PROJECT_ROOT / "selfx"
STUDY_DIR = SELFX_ROOT / "output" / "pipeline_study"
FIG_DIR = PROJECT_ROOT / "paper" / "figures"

# --- validated palette ------------------------------------------------------ #
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
MAGENTA, VIOLET, RED = "#e87ba4", "#6250d6", "#e34948"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#9a9893"
GRID = "#e3e2de"
#: single-hue ramp, light -> dark, for the ordered pipeline stages
STAGE_RAMP = ["#c3dbf5", "#9cc3ee", "#6ea6e4", "#4189db", "#2a78d6", "#14528f"]

STAGE_SHORT = {
    "S0": "S0\nstatic",
    "S1": "S1\nLLM",
    "S2": "S2\n+critique",
    "S3": "S3\n+LoRA",
    "S4": "S4\n+governor",
    "S5": "S5\nfull",
}
BASELINE_SHORT = {
    "threshold": "Threshold\nheuristic",
    "least_loaded": "Least-loaded\n(ECMP-style)",
    "tabular_q": "Tabular Q\nlearning",
}


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.5,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.6,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.frameon": False,
        "legend.fontsize": 7.5,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
    })


def despine(ax, left: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if not left:
        ax.spines["left"].set_visible(False)
    ax.grid(axis="x", visible=False)


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.pdf")
    fig.savefig(FIG_DIR / f"{name}.png", dpi=220)
    plt.close(fig)
    print(f"  wrote {name}.pdf / .png")


def load() -> Dict[str, Any]:
    summary = json.loads((STUDY_DIR / "pipeline_summary.json").read_text(encoding="utf-8"))
    runs = json.loads((STUDY_DIR / "pipeline_runs.json").read_text(encoding="utf-8"))
    return {"summary": summary, "runs": runs}


def stages_of(summary: Dict[str, Any], keys: Sequence[str]) -> List[Dict[str, Any]]:
    index = {s["configuration"]: s for s in summary["stages"]}
    return [index[k] for k in keys if k in index]


def label_bars(ax, bars, values, fmt="{:.2f}", dy=0.0, color=INK) -> None:
    """Direct value labels. These are the relief for the low-contrast fills."""
    for bar, value in zip(bars, values):
        height = bar.get_height()
        offset = dy if dy else (0.02 * (ax.get_ylim()[1] - ax.get_ylim()[0]))
        ax.annotate(fmt.format(value),
                    (bar.get_x() + bar.get_width() / 2,
                     height + offset if height >= 0 else height - offset),
                    ha="center", va="bottom" if height >= 0 else "top",
                    fontsize=7.2, color=color)


# --------------------------------------------------------------------------- #
# Fig. 1 — architecture
# --------------------------------------------------------------------------- #

def fig_architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    def box(x, y, w, h, text, face, edge, text_color=INK, fontsize=8.0, weight="normal"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.4",
                                    linewidth=1.0, facecolor=face, edgecolor=edge))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, color=text_color, weight=weight, linespacing=1.35)

    def arrow(x1, y1, x2, y2, color=MUTED, style="-|>", ls="-"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                                     linewidth=1.0, linestyle=ls, mutation_scale=9,
                                     shrinkA=2, shrinkB=2))

    # slow loop
    ax.text(50, 49.5, "Slow timescale — governance epoch 30 s", ha="center",
            fontsize=8.2, color=BLUE, weight="bold")
    box(3, 37, 20, 8.5, "Orchestrator\n(intent decomposition)", "#eaf2fc", BLUE)
    box(27, 37, 30, 8.5,
        "5 specialists  ·  OpenRouter free model\nflow-sizing · routing · anomaly\nsecurity · slicing",
        "#eaf2fc", BLUE, fontsize=7.2)
    box(61, 37, 16, 8.5, "Self-critique\n+ replay buffer", "#eaf2fc", BLUE)
    box(81, 37, 16, 8.5, "LoRA adapter\nr=8, α=16", "#eaf2fc", BLUE)
    arrow(23, 41.2, 27, 41.2)
    arrow(57, 41.2, 61, 41.2)
    arrow(77, 41.2, 81, 41.2)

    # delta pi channel
    box(33, 26, 34, 6.5, "Δπ = (V, w, action mask)   —   safety-gated, versioned",
        "#fdf0e9", ORANGE, fontsize=7.8)
    arrow(50, 37, 50, 32.5, ORANGE)

    # fast loop
    ax.text(50, 21.5, "Fast timescale — control slot τ = 100 ms", ha="center",
            fontsize=8.2, color=AQUA, weight="bold")
    box(14, 11, 30, 8.0, "Lyapunov drift-plus-penalty\nargmin  Δ(L) + V·cost", "#e8f7f1", AQUA)
    box(50, 11, 30, 8.0, "Independent safety arbiter\n20% drop ceiling · 512 kbps floor",
        "#e8f7f1", AQUA, fontsize=7.6)
    arrow(50, 26, 29, 19.0, ORANGE, ls="--")
    arrow(44, 15, 50, 15, AQUA)

    # datapath
    box(27, 1.5, 40, 6.5, "OpenFlow 1.3 datapath  ·  two paths, 10 Mbps, 2 Mbit buffer",
        "#f4f4f1", MUTED, fontsize=7.8)
    arrow(65, 11, 65, 8.0, AQUA)
    arrow(20, 8.0, 20, 11, MUTED)
    ax.text(18.4, 9.6, "telemetry", ha="right", va="center", fontsize=6.8, color=MUTED)
    arrow(8, 8.0, 8, 37, MUTED, ls=":")
    ax.text(7.0, 23, "windowed\ntelemetry", ha="right", va="center", fontsize=6.8, color=MUTED)

    save(fig, "fig1_architecture")


# --------------------------------------------------------------------------- #
# Fig. 2 — offered traffic
# --------------------------------------------------------------------------- #

def fig_traffic() -> None:
    sys.path[:0] = [str(PROJECT_ROOT), str(SELFX_ROOT)]
    from eval.pipeline_model import (C_ALTERNATE_MBPS, C_PRIMARY_MBPS, TAU_SEC,
                                     demand_series)
    from traffic_gen import generate_schedule

    summary = load()["summary"]
    seed = summary["seeds"][0]
    windows = summary["windows_per_run"]
    schedule = generate_schedule("steady_bursty", int(windows * summary["window_sec"]), seed)
    series = demand_series(schedule, windows)
    t = [i * TAU_SEC for i in range(len(series))]
    mice = [m for m, _ in series]
    eleph = [e for _, e in series]
    total = [m + e for m, e in series]

    fig, ax = plt.subplots(figsize=(7.0, 2.5))
    ax.fill_between(t, 0, mice, color=AQUA, alpha=0.75, linewidth=0, label="Mice (latency-sensitive)")
    ax.fill_between(t, mice, total, color=ORANGE, alpha=0.70, linewidth=0, label="Elephant aggregate")
    ax.axhline(C_PRIMARY_MBPS, color=BLUE, linewidth=1.1, linestyle="--")
    ax.axhline(C_PRIMARY_MBPS + C_ALTERNATE_MBPS, color=INK, linewidth=1.1, linestyle=":")
    ax.annotate("primary capacity 10 Mbps", (t[-1], C_PRIMARY_MBPS), xytext=(-4, 3),
                textcoords="offset points", ha="right", fontsize=7, color=BLUE)
    ax.annotate("total capacity 20 Mbps — demand above this line is irreducible loss",
                (t[-1], C_PRIMARY_MBPS + C_ALTERNATE_MBPS), xytext=(-4, 3),
                textcoords="offset points", ha="right", fontsize=7, color=INK)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Offered load (Mbps)")
    ax.set_title(f"Offered traffic, seed {seed} — steady mice plus Poisson elephant bursts")
    ax.set_xlim(0, t[-1])
    ax.set_ylim(0, max(total) * 1.08)
    ax.legend(loc="upper left", ncol=2)
    despine(ax)
    save(fig, "fig2_traffic")


# --------------------------------------------------------------------------- #
# Fig. 3 — stage ablation
# --------------------------------------------------------------------------- #

def fig_ablation(summary: Dict[str, Any]) -> None:
    stages = stages_of(summary, ["S0", "S1", "S2", "S3", "S4", "S5"])
    # Stage codes only on the axis; the mechanism each one adds is spelled out in
    # the caption and in Table II. Two-line tick labels collided at column width.
    names = [s["configuration"] for s in stages]
    x = list(range(len(stages)))

    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.9), constrained_layout=True)
    panels = [
        ("mean_latency_ms", "sem_latency_ms", "Mean delay (ms) ↓", "{:.0f}"),
        ("loss_pct", "sem_loss_pct", "Packet loss (%) ↓", "{:.1f}"),
        ("mean_reward", "sem_reward", "Mean window reward ↑", "{:.2f}"),
    ]
    for ax, (key, errkey, title, fmt) in zip(axes, panels):
        values = [s[key] for s in stages]
        errors = [s.get(errkey, 0.0) for s in stages]
        bars = ax.bar(x, values, color=STAGE_RAMP, width=0.70,
                      edgecolor="white", linewidth=1.2)
        ax.errorbar(x, values, yerr=errors, fmt="none", ecolor=INK2,
                    elinewidth=0.9, capsize=2.5)
        ax.set_xticks(x)
        ax.set_xticklabels(names, fontsize=7.6)
        ax.set_title(title, fontsize=9.0)

        # Headroom first, then place each label clear of its own error bar.
        lo = min(0.0, min(v - e for v, e in zip(values, errors)))
        hi = max(0.0, max(v + e for v, e in zip(values, errors)))
        span = (hi - lo) or 1.0
        ax.set_ylim(lo - 0.18 * span, hi + 0.22 * span)
        pad = 0.045 * span
        for xi, value, error in zip(x, values, errors):
            if value >= 0:
                y, va = value + error + pad, "bottom"
            else:
                y, va = value - error - pad, "top"
            ax.annotate(fmt.format(value), xy=(xi, y), ha="center", va=va,
                        fontsize=7.0, color=INK)
        despine(ax)
        if lo < 0:
            ax.axhline(0, color=MUTED, linewidth=0.8)
    fig.suptitle("Each stage adds exactly one mechanism to the one before it",
                 fontsize=9.5, weight="bold")
    save(fig, "fig3_ablation")


# --------------------------------------------------------------------------- #
# Fig. 4 — control-plane latency against the two timescales
# --------------------------------------------------------------------------- #

def fig_control_latency(summary: Dict[str, Any]) -> None:
    index = {s["configuration"]: s for s in summary["stages"]}
    entries = []
    if "S5" in index and index["S5"]["mean_fast_decision_us"] > 0:
        entries.append(("Lyapunov DPP\nfast loop", index["S5"]["mean_fast_decision_us"] / 1000.0, AQUA))
    if "S3" in index:
        entries.append(("LoRA policy head\n(SmolLM2-135M, CPU)", index["S3"]["mean_control_latency_ms"], ORANGE))
    if "S1" in index:
        entries.append(("Zero-shot LLM\n(remote free tier)", index["S1"]["mean_control_latency_ms"], BLUE))
    if "S2" in index:
        entries.append(("LLM + self-critique\n(two passes)", index["S2"]["mean_control_latency_ms"], VIOLET))

    fig, ax = plt.subplots(figsize=(7.0, 2.7))
    names = [e[0] for e in entries]
    values = [max(e[1], 1e-4) for e in entries]
    colors = [e[2] for e in entries]
    y = list(range(len(entries)))
    bars = ax.barh(y, values, color=colors, height=0.6, edgecolor="white", linewidth=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=7.4)
    ax.set_xscale("log")
    ax.set_xlabel("Measured decision latency (ms, log scale)")
    ax.set_xlim(1e-3, max(values) * 12)
    ax.invert_yaxis()

    # Period markers are annotated inside the axes, in axes-fraction coordinates,
    # so the labels can never collide with the title however the bars are scaled.
    for marker, label, color, frac in ((100.0, "τ = 100 ms slot", INK, 0.07),
                                       (5000.0, "5 s window", MUTED, 0.07)):
        ax.axvline(marker, color=color, linewidth=1.0, linestyle="--")
        ax.annotate(label, xy=(marker, frac), xycoords=("data", "axes fraction"),
                    xytext=(3, 0), textcoords="offset points", rotation=90,
                    fontsize=6.9, color=color, ha="left", va="bottom")

    for bar, value in zip(bars, values):
        text = f"{value*1000:.0f} µs" if value < 1 else f"{value:,.0f} ms"
        ax.annotate(text, (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points", va="center",
                    fontsize=7.4, color=INK)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("Why the language model cannot sit in the fast loop", pad=8)
    save(fig, "fig4_control_latency")


# --------------------------------------------------------------------------- #
# Fig. 5 — queue trajectory against the Lyapunov bound
# --------------------------------------------------------------------------- #

def fig_queue(summary: Dict[str, Any], runs: List[Dict[str, Any]]) -> None:
    sys.path[:0] = [str(PROJECT_ROOT), str(SELFX_ROOT)]
    from eval.pipeline_model import BUFFER_MBIT

    seed = summary["seeds"][0]
    pick = {r["configuration"]: r for r in runs if r["seed"] == seed}
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    for cfg, color, label in (("S0", MUTED, "S0 static"),
                              ("S3", ORANGE, "S3 LoRA policy head"),
                              ("S5", BLUE, "S5 full pipeline (DPP fast loop)")):
        if cfg not in pick:
            continue
        rows = pick[cfg]["per_window"]
        t = [w["window"] * summary["window_sec"] for w in rows]
        q = [w["mean_queue_mbit"] for w in rows]
        ax.plot(t, q, color=color, linewidth=1.6 if cfg == "S5" else 1.2, label=label)
    ax.axhline(2 * BUFFER_MBIT, color=RED, linewidth=1.0, linestyle=":")
    ax.annotate(f"physical buffer ceiling {2*BUFFER_MBIT:.1f} Mbit (both paths)",
                (0, 2 * BUFFER_MBIT), xytext=(3, 3), textcoords="offset points",
                fontsize=7, color=RED)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Time-average backlog Q(t) (Mbit)")
    ax.set_title("Backlog: every controller fills the buffer; the fast loop drains it sooner")
    ax.legend(loc="upper right", ncol=1)
    despine(ax)
    save(fig, "fig5_queue")


# --------------------------------------------------------------------------- #
# Fig. 6 — V trade-off
# --------------------------------------------------------------------------- #

def fig_v_tradeoff() -> None:
    path = STUDY_DIR / "v_tradeoff.json"
    if not path.exists():
        print("  (skipping fig6: v_tradeoff.json not present)")
        return
    data = json.loads(path.read_text(encoding="utf-8"))["results"]
    v = [r["V"] for r in data]
    backlog = [r["mean_backlog_mbit"] for r in data]
    loss = [r["loss_pct"] for r in data]
    bound = [r["analytic_bound_mbit"] for r in data]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.5))
    ax = axes[0]
    ax.plot(v, backlog, color=BLUE, marker="o", markersize=4.5, linewidth=1.6,
            label="measured backlog")
    ax.plot(v, bound, color=MUTED, linestyle="--", linewidth=1.2, label="analytic bound (B+VC)/ε")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Lyapunov parameter V")
    ax.set_ylabel("Mean backlog (Mbit)")
    ax.set_title("Backlog grows as O(V)")
    ax.legend(loc="upper left")
    despine(ax)

    ax = axes[1]
    ax.plot(v, loss, color=ORANGE, marker="s", markersize=4.5, linewidth=1.6)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Lyapunov parameter V")
    ax.set_ylabel("Packet loss (%)")
    # The loss axis spans a few hundredths of a percentage point, so one decimal
    # renders every marker as the same number. Three decimals, and a title that
    # says what the data actually shows rather than what theory predicts.
    ax.set_title("Loss barely moves: the buffer binds, not $V$")
    for xi, yi in zip(v, loss):
        ax.annotate(f"{yi:.3f}", (xi, yi), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=6.6, color=INK2)
    span = max(loss) - min(loss)
    ax.set_ylim(min(loss) - 0.35 * span, max(loss) + 0.45 * span)
    despine(ax)
    fig.suptitle("The V knob trades queue backlog against the operating-cost penalty",
                 fontsize=9.5, weight="bold", y=1.06)
    save(fig, "fig6_v_tradeoff")


# --------------------------------------------------------------------------- #
# Fig. 7 — baseline comparison
# --------------------------------------------------------------------------- #

def fig_baselines(summary: Dict[str, Any]) -> None:
    order = ["S0", "threshold", "least_loaded", "tabular_q", "S2", "S5"]
    rows = stages_of(summary, order)
    # Short tick labels: at column width the descriptive ones collide into each
    # other. The full controller names are in Table V, which this figure sits with.
    labels = {
        "S0": "Static",
        "threshold": "Threshold",
        "least_loaded": "Least-\nloaded",
        "tabular_q": "Tabular\n$Q$",
        "S2": "Reflexive\nLLM",
        "S5": "SELF-X",
    }
    names = [labels[r["configuration"]] for r in rows]
    colors = [MUTED, YELLOW, AQUA, ORANGE, VIOLET, BLUE]
    x = range(len(rows))

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), constrained_layout=True)
    for ax, key, title, fmt in (
        (axes[0], "mean_latency_ms", "Mean delay (ms)", "{:.1f}"),
        (axes[1], "loss_pct", "Packet loss (%)", "{:.1f}"),
    ):
        values = [r[key] for r in rows]
        bars = ax.bar(x, values, color=colors, width=0.66, edgecolor="white", linewidth=1.2)
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, fontsize=7.0)
        ax.set_title(title)
        ax.set_ylim(0, max(values) * 1.24)
        label_bars(ax, bars, values, fmt)
        despine(ax)
    if rows and "oracle_floor_loss_pct" in rows[0]:
        floor = rows[0]["oracle_floor_loss_pct"]
        axes[1].axhline(floor, color=RED, linewidth=1.0, linestyle="--")
        axes[1].annotate(f"irreducible floor {floor:.1f}%",
                         (len(rows) - 0.5, floor), xytext=(0, -3),
                         textcoords="offset points", ha="right", va="top",
                         fontsize=6.8, color=RED)
    fig.suptitle("Comparison against non-LLM controllers on the identical trace",
                 fontsize=9.5, weight="bold")
    save(fig, "fig7_baselines")


# --------------------------------------------------------------------------- #
# Fig. 8 — loss decomposition
# --------------------------------------------------------------------------- #

def fig_loss_decomposition(summary: Dict[str, Any]) -> None:
    keys = ["S0", "S1", "S2", "S3", "S4", "S5"]
    rows = stages_of(summary, keys)
    if not rows or "excess_loss_pct" not in rows[0]:
        print("  (skipping fig8: oracle decomposition not present)")
        return
    names = [STAGE_SHORT[r["configuration"]] for r in rows]
    floor = [r["oracle_floor_loss_pct"] for r in rows]
    excess = [max(0.0, r["excess_loss_pct"]) for r in rows]
    x = range(len(rows))

    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    b1 = ax.bar(x, floor, color=MUTED, width=0.62, edgecolor="white", linewidth=1.4,
                label="Irreducible: demand above total capacity")
    b2 = ax.bar(x, excess, bottom=floor, color=BLUE, width=0.62, edgecolor="white",
                linewidth=1.4, label="Controller-addressable")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, fontsize=6.8)
    ax.set_ylabel("Packet loss (%)")
    ax.set_title("Only the upper band is the controller's to remove", pad=30)
    for xi, f, e in zip(x, floor, excess):
        ax.annotate(f"{e:.1f}", (xi, f + e), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7.2, color=INK)
    ax.set_ylim(0, max(f + e for f, e in zip(floor, excess)) * 1.16)
    # Legend outside the plotting area: at this aspect ratio an inside legend
    # lands on the tallest bar's value label.
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.10), ncol=2,
              borderaxespad=0.0)
    despine(ax)
    save(fig, "fig8_loss_decomposition")


# --------------------------------------------------------------------------- #
# Fig. 9 — reward convergence
# --------------------------------------------------------------------------- #

def fig_convergence(summary: Dict[str, Any], runs: List[Dict[str, Any]]) -> None:
    seed = summary["seeds"][0]
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    ends = []
    for cfg, color in zip(["S0", "S1", "S2", "S3", "S4", "S5"], STAGE_RAMP):
        match = [r for r in runs if r["configuration"] == cfg and r["seed"] == seed]
        if not match:
            continue
        rows = match[0]["per_window"]
        t = [w["window"] * summary["window_sec"] for w in rows]
        cumulative, running = [], 0.0
        for w in rows:
            running += w["reward"]
            cumulative.append(running)
        ax.plot(t, cumulative, color=color, linewidth=1.8 if cfg == "S5" else 1.1,
                label=cfg)
        ends.append((cumulative[-1], cfg, color))

    # End labels are nudged apart vertically: several stages finish within a point
    # or two of each other and their labels would otherwise sit on top of one another.
    ends.sort(key=lambda e: e[0])
    span = (max(e[0] for e in ends) - min(e[0] for e in ends)) or 1.0
    gap = 0.055 * span
    placed = []
    for value, cfg, color in ends:
        y = value
        while placed and y - placed[-1] < gap:
            y = placed[-1] + gap
        placed.append(y)
        ax.annotate(cfg, xy=(t[-1], y), xytext=(5, 0), textcoords="offset points",
                    fontsize=7, color=color, va="center")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Cumulative reward")
    ax.set_title(f"Cumulative reward over one run (seed {seed})")
    ax.axhline(0, color=MUTED, linewidth=0.8)
    despine(ax)
    save(fig, "fig9_convergence")


# --------------------------------------------------------------------------- #
# Fig. 10 — provider behaviour
# --------------------------------------------------------------------------- #

def fig_provider(summary: Dict[str, Any]) -> None:
    llm = summary.get("llm")
    if not llm:
        print("  (skipping fig10: no llm statistics)")
        return
    trace_path = STUDY_DIR / "llm_trace.jsonl"
    latencies: List[float] = []
    if trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # served_ms is the healthy-endpoint latency; elapsed_ms also counts
            # the walk past exhausted endpoints, which is a property of the chain
            # rather than of the model.
            if rec.get("status") == "ok" and rec.get("served_ms"):
                latencies.append(float(rec["served_ms"]))

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.5))
    ax = axes[0]
    if latencies:
        ordered = sorted(latencies)
        y = [(i + 1) / len(ordered) for i in range(len(ordered))]
        ax.plot(ordered, y, color=BLUE, linewidth=1.8)
        # Both period markers are labelled above the curve, not across it.
        for marker, text, color in ((100, "τ = 100 ms", INK),
                                    (5000, "5 s window", MUTED)):
            ax.axvline(marker, color=color, linestyle="--", linewidth=1.0)
            ax.annotate(text, xy=(marker, 1.0), xytext=(3, -2),
                        textcoords="offset points", rotation=90, fontsize=6.8,
                        color=color, ha="left", va="top")
        ax.set_xscale("log")
        ax.set_xlabel("Request latency (ms, log scale)")
        ax.set_ylabel("Empirical CDF")
        ax.set_title(f"Free-tier request latency (n = {len(ordered)})")
    despine(ax)

    ax = axes[1]
    served = llm.get("models_served", {})
    if served:
        names = [k.split("/")[-1].replace(":free", "") for k in served]
        values = list(served.values())
        colors = [BLUE, ORANGE, AQUA, YELLOW, VIOLET][:len(values)]
        bars = ax.barh(range(len(values)), values, color=colors, height=0.6,
                       edgecolor="white", linewidth=1.2)
        ax.set_yticks(range(len(values)))
        ax.set_yticklabels(names, fontsize=7)
        ax.invert_yaxis()
        ax.set_xlabel("Decisions served")
        ax.set_title("Which free endpoint answered")
        for bar, value in zip(bars, values):
            ax.annotate(str(value), (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                        xytext=(4, 0), textcoords="offset points", va="center",
                        fontsize=7.2, color=INK)
        ax.grid(axis="y", visible=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.suptitle(
        f"Served {llm['served_fraction']*100:.1f}% of decisions · "
        f"{llm['declared_fallbacks']} declared local fallbacks",
        fontsize=8.6, color=INK2, y=1.04)
    save(fig, "fig10_provider")


# --------------------------------------------------------------------------- #

def main() -> int:
    style()
    data = load()
    summary, runs = data["summary"], data["runs"]
    print(f"figures -> {FIG_DIR}")
    fig_architecture()
    fig_traffic()
    fig_ablation(summary)
    fig_control_latency(summary)
    fig_queue(summary, runs)
    fig_v_tradeoff()
    fig_baselines(summary)
    fig_loss_decomposition(summary)
    fig_convergence(summary, runs)
    fig_provider(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
