"""Explainer figures and benchmark tables from the saved v4 evidence.

Reads only committed results (output/benchmarks/v4); writes PNG + SVG and a
Markdown table file to output/explainer. No experiment is re-run.

    .venv\\Scripts\\python.exe -m scripts.explainer_figures
"""
from __future__ import annotations
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import config

SRC = config.PROJECT_ROOT / "output" / "benchmarks" / "v4"
OUT = config.PROJECT_ROOT / "output" / "explainer"

# Validated categorical slots (light surface): blue, orange, aqua.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, DIM = "#e1e0d9", "#c3c2b7", "#c9c7bf"
SCENARIOS = ["mixed", "flash", "alternate", "shift", "overload", "light", "recurring", "volatile"]
SCENARIO_NAMES = {"mixed": "Mixed", "flash": "Flash crowd", "alternate": "Alternate busy", "shift": "Traffic shift",
                  "overload": "Both overloaded", "light": "Light load", "recurring": "Recurring", "volatile": "Volatile"}
LADDER = [("A0", "Static path, no control"), ("B1", "Greedy least-loaded reroute"),
          ("A2", "Original similar-state memory"), ("H1", "Safety guard + fixed 20% meter"),
          ("H2", "Capacity-aware meter, no memory"), ("A4", "SELF-X: meter + episodic memory"),
          ("O2", "Oracle (peeks at outcomes)")]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10.5, "text.color": INK,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 1,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 1, "grid.linestyle": "-",
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    "legend.frameon": False, "lines.linewidth": 2, "lines.solid_capstyle": "round",
})


def load_rows():
    with (SRC / "metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for r in rows:
        for k in ("latency_ms", "throughput_kbps", "loss_pct", "reward", "primary_background_mbps",
                  "alternate_background_mbps", "elephant_mbps", "queue_primary_mbit", "queue_alternate_mbit"):
            r[k] = float(r[k])
        r["seed"], r["cycle"] = int(r["seed"]), int(r["cycle"])
    return rows


def seed_means(rows, condition, metric, scenarios=SCENARIOS):
    """Equal weight per scenario, one value per seed: the unit of inference used by the project."""
    cells = defaultdict(list)
    for r in rows:
        if r["condition"] == condition and r["scenario"] in scenarios:
            cells[(r["seed"], r["scenario"])].append(r[metric])
    seeds = sorted({s for s, _ in cells})
    return {s: mean(mean(cells[(s, sc)]) for sc in scenarios if (s, sc) in cells) for s in seeds}


def bootstrap(values, draws=4000, rng_seed=4099):
    rng = random.Random(rng_seed)
    stats = sorted(mean(rng.choices(values, k=len(values))) for _ in range(draws))
    return stats[int(.025 * draws)], stats[int(.975 * draws) - 1]


def title(fig, text, sub):
    fig.text(.012, .975, text, fontsize=15, fontweight="bold", va="top", color=INK)
    fig.text(.012, .918, sub, fontsize=10.5, va="top", color=INK2)


def footnote(fig, text):
    fig.text(.012, .018, text, fontsize=9, color=MUTED, va="bottom")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=170 if ext == "png" else None)
    plt.close(fig)
    return name


# ---------------------------------------------------------------------------
def fig_where_gain_comes_from(rows):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), sharey=True)
    fig.subplots_adjust(left=.235, right=.97, top=.78, bottom=.16, wspace=.12)
    title(fig, "Where the improvement comes from",
          "Change against the static baseline (A0), averaged over 8 scenarios x 10 seeds. Lower is better on both.")
    for ax, metric, label in ((axes[0], "latency_ms", "Modeled delay, % change vs A0"),
                              (axes[1], "loss_pct", "Total loss, % change vs A0")):
        base = seed_means(rows, "A0", metric)
        for i, (cond, _) in enumerate(LADDER):
            vals = seed_means(rows, cond, metric)
            pct = [100 * (vals[s] - base[s]) / base[s] for s in base]
            m, (lo, hi) = mean(pct), bootstrap(pct)
            y = len(LADDER) - 1 - i
            color = BLUE if cond == "A4" else (MUTED if cond == "A0" else DIM)
            ax.barh(y, m, height=.5, color=color, zorder=2)
            if cond != "A0":
                ax.plot([lo, hi], [y, y], color=INK2, lw=1.2, zorder=3)
            pad = .8 if metric == "latency_ms" else .35
            if cond == "A0":
                ax.text(-pad, y, "baseline", va="center", ha="right", fontsize=10, color=MUTED)
            else:
                ax.text(min(m, lo) - pad if m < 0 else max(m, hi) + pad, y, f"{m:+.1f}%",
                        va="center", ha="right" if m < 0 else "left", fontsize=10, color=INK,
                        fontweight="bold" if cond == "A4" else "normal")
        ax.axvline(0, color=AXIS, lw=1, zorder=1)
        ax.set_xlabel(label)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(ax.get_xlim()[0] * 1.28, 6)
    axes[0].set_yticks(range(len(LADDER)))
    axes[0].set_yticklabels([f"{c}  {name}" for c, name in reversed(LADDER)])
    for tick in axes[0].get_yticklabels():
        if tick.get_text().startswith("A4"):
            tick.set_color(INK); tick.set_fontweight("bold")
    footnote(fig, "Whiskers: paired 95% seed bootstrap (4,000 draws). Most of the gain arrives with rerouting + the guarded meter (B1 -> H2). "
                  "H2 vs A4 isolates memory: about zero.\nV3 equals H1 and A3 sits between H1 and H2; both are omitted. "
                  "Fluid-model results, not packet measurements. Source: output/benchmarks/v4/metrics.csv")
    return save(fig, "01_where_the_gain_comes_from")


# ---------------------------------------------------------------------------
def fig_one_episode(rows, scenario="mixed", seed=1900, windows=48):
    pick = lambda c: sorted((r for r in rows if r["scenario"] == scenario and r["seed"] == seed and r["condition"] == c
                             and r["cycle"] < windows), key=lambda r: r["cycle"])
    a0, a4 = pick("A0"), pick("A4")
    x = [r["cycle"] for r in a4]
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, .55, 1.6, 1.6], "hspace": .28})
    fig.subplots_adjust(left=.085, right=.85, top=.83, bottom=.115)
    title(fig, "One episode, window by window: doing nothing (A0) vs SELF-X (A4)",
          f"Scenario '{scenario}', seed {seed}, first {windows} five-second windows (= {windows * 5 // 60} simulated minutes).")
    shades = {"light": "#f3f2ee", "primary_burst": SURFACE, "alternate_busy": "#f3f2ee", "both_busy": SURFACE}
    for ax in axes:
        start = 0
        for i in range(1, len(a4) + 1):
            if i == len(a4) or a4[i]["phase"] != a4[start]["phase"]:
                ax.axvspan(start - .5, i - .5, color=shades[a4[start]["phase"]], zorder=0, lw=0)
                start = i
    phase_names = {"light": "light", "primary_burst": "burst", "alternate_busy": "alt busy", "both_busy": "both busy"}
    for i, r in enumerate(a4[:12]):
        if i % 3 == 0:
            axes[0].text(i + 1, 19.4, phase_names[r["phase"]], ha="center", fontsize=8.5, color=MUTED)

    ax = axes[0]
    primary = [r["primary_background_mbps"] + r["elephant_mbps"] for r in a4]
    alternate = [r["alternate_background_mbps"] + r["elephant_mbps"] for r in a4]
    ax.step(x, primary, where="mid", color=ORANGE, label="Primary path if nothing is done")
    ax.step(x, alternate, where="mid", color=AQUA, label="Alternate path if the elephant moves")
    ax.axhline(10, color=INK2, lw=1.2, ls=(0, (4, 3)))
    ax.text(1.005, 10.6 / 20.5, "capacity\n10 Mbps", transform=ax.transAxes, va="bottom", fontsize=9, color=INK2)
    ax.axhline(9, color=MUTED, lw=1, ls=(0, (1, 2)))
    ax.text(1.005, 8.6 / 20.5, "90% reroute\nceiling", transform=ax.transAxes, va="top", fontsize=8.5, color=MUTED)
    ax.set_ylabel("Offered load (Mbps)")
    ax.set_ylim(0, 20.5)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, fontsize=9.5)

    ax = axes[1]
    colors = {"no_op": DIM, "reroute": BLUE, "rate_limit": ORANGE}
    for r in a4:
        ax.add_patch(Rectangle((r["cycle"] - .45, 0), .9, 1, color=colors[r["installed_action"]], lw=0))
    ax.set_ylim(0, 1); ax.set_yticks([]); ax.grid(False)
    ax.set_ylabel("A4 action", rotation=0, ha="right", va="center")
    ax.spines["left"].set_visible(False)
    for i, (k, lab) in enumerate((("no_op", "no_op (leave it)"), ("reroute", "reroute elephant"), ("rate_limit", "meter elephant"))):
        ax.add_patch(Rectangle((1.015, .72 - i * .34), .012, .22, color=colors[k], transform=ax.transAxes, clip_on=False))
        ax.text(1.032, .83 - i * .34, lab, transform=ax.transAxes, fontsize=9, va="center", color=INK2)

    for ax, metric, ylabel in ((axes[2], "latency_ms", "Delay (ms)"), (axes[3], "loss_pct", "Loss (%)")):
        ax.step(x, [r[metric] for r in a0], where="mid", color=MUTED, label="A0 static")
        ax.step(x, [r[metric] for r in a4], where="mid", color=BLUE, label="A4 SELF-X")
        ax.set_ylabel(ylabel)
        ax.text(1.005, .3 if ax is axes[2] else .5,
                f"mean\nA0 {mean(r[metric] for r in a0):.1f}\nA4 {mean(r[metric] for r in a4):.1f}",
                transform=ax.transAxes, fontsize=9, color=INK2, va="center")
    axes[2].legend(loc="upper left", bbox_to_anchor=(1.0, 1.02), fontsize=9)
    axes[3].set_xlabel("Control window (5 s each)")
    axes[3].set_xlim(-.5, windows - .5)
    footnote(fig, "Each window: observe demand -> pick an action -> guard checks it -> fluid model computes queues, delay and loss. "
                  "Queues carry over between windows.\nIn 'both busy' windows there is nowhere to send the elephant, so the meter trims it instead. "
                  "Source: output/benchmarks/v4/metrics.csv")
    return save(fig, "02_one_episode_A0_vs_A4")


# ---------------------------------------------------------------------------
def fig_scenarios(rows):
    agg = defaultdict(list)
    for r in rows:
        agg[(r["scenario"], r["condition"], "latency_ms")].append(r["latency_ms"])
        agg[(r["scenario"], r["condition"], "loss_pct")].append(r["loss_pct"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    fig.subplots_adjust(left=.13, right=.97, top=.80, bottom=.15, wspace=.1)
    title(fig, "Scenario scorecard: what each traffic pattern gains",
          "Each row moves from the static baseline (grey) to SELF-X A4 (blue). A short line means there was little to fix.")
    order = list(reversed(SCENARIOS))
    for ax, metric, label in ((axes[0], "latency_ms", "Modeled delay (ms)"), (axes[1], "loss_pct", "Total loss (%)")):
        for y, sc in enumerate(order):
            base, ours = mean(agg[(sc, "A0", metric)]), mean(agg[(sc, "A4", metric)])
            ax.plot([base, ours], [y, y], color=DIM, lw=2.5, zorder=2, solid_capstyle="butt")
            ax.scatter([base], [y], s=70, color=MUTED, zorder=3, edgecolor=SURFACE, linewidth=2)
            ax.scatter([ours], [y], s=70, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=2)
            change = 100 * (ours - base) / base if base else 0
            note = "no change" if abs(change) < .05 else f"{change:+.0f}%"
            ax.text(max(base, ours) + (.9 if metric == "latency_ms" else .7), y, note, va="center", fontsize=9.5,
                    color=INK if abs(change) >= .05 else MUTED)
        ax.set_xlabel(label)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, ax.get_xlim()[1] * 1.12)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([SCENARIO_NAMES[s] for s in order])
    axes[1].scatter([], [], s=70, color=MUTED, label="A0 static"); axes[1].scatter([], [], s=70, color=BLUE, label="A4 SELF-X")
    axes[1].legend(loc="lower right", fontsize=9.5)
    footnote(fig, "'Both overloaded': both paths are full, so no reroute or meter can deliver more; every controller ties. "
                  "'Light load': nothing is congested, so nothing is done.\n"
                  "Means over 10 seeds x 120 windows. Loss includes deliberate meter drops. Source: output/benchmarks/v4/metrics.csv")
    return save(fig, "03_scenario_scorecard")


# ---------------------------------------------------------------------------
def fig_decision_map(rows, seed=1900):
    pts = [r for r in rows if r["condition"] == "A4" and r["seed"] == seed]
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.subplots_adjust(left=.1, right=.78, top=.83, bottom=.14)
    title(fig, "The decision map: how SELF-X picks an action",
          "Every dot is one control window (all 8 scenarios, seed 1900), placed by the two loads the controller checks.")
    xmax, ymax = 215, 215
    ax.add_patch(Rectangle((0, 0), 100, ymax, color="#f0efec", lw=0, zorder=0))
    ax.add_patch(Rectangle((100, 0), xmax - 100, 90, color="#e4eefa", lw=0, zorder=0))
    ax.add_patch(Rectangle((100, 90), xmax - 100, ymax - 90, color="#fde9e0", lw=0, zorder=0))
    ax.axvline(100, color=INK2, lw=1.2); ax.axhline(90, xmin=100 / xmax, color=INK2, lw=1.2)
    ax.text(50, 205, "NO_OP\nprimary fits, leave it", ha="center", va="top", fontsize=10, color=INK2, fontweight="bold")
    ax.text(157, 45, "REROUTE\nprimary overloaded,\nalternate has room", ha="center", va="center", fontsize=10, color=INK2, fontweight="bold")
    ax.text(104, 210, "RATE_LIMIT (meter)\nboth paths too busy:\ntrim elephant by <= 20%", ha="left", va="top", fontsize=10,
            color=INK2, fontweight="bold", zorder=5, bbox=dict(boxstyle="round,pad=.3", fc="#fde9e0", ec="none", alpha=.92))
    colors = {"no_op": MUTED, "reroute": BLUE, "rate_limit": ORANGE}
    for action in ("no_op", "reroute", "rate_limit"):
        sel = [r for r in pts if r["installed_action"] == action]
        ax.scatter([10 * (r["primary_background_mbps"] + r["elephant_mbps"]) for r in sel],
                   [10 * (r["alternate_background_mbps"] + r["elephant_mbps"]) for r in sel],
                   s=22, color=colors[action], edgecolor=SURFACE, linewidth=.8, zorder=3,
                   label=f"{action} ({len(sel)} windows)")
    ax.set_xlim(0, xmax); ax.set_ylim(0, ymax)
    ax.set_xlabel("Primary path load if nothing changes (% of capacity)")
    ax.set_ylabel("Alternate path load if the elephant is rerouted (% of capacity)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=9.5, title="A4 installed", title_fontsize=9.5)
    ax.text(1.01, .62, "The lines are the rule in\nagent/loss_aware_memory.py\n(capacity_policy):\n\n"
                       "  primary <= 100%  -> no_op\n  alternate <= 90% -> reroute\n  otherwise        -> meter\n\n"
                       "Memory only tunes HOW HARD\nto meter (0 / 0.1 / 0.3 Mbps\nheadroom). It never changes\nwhich region a window is in.",
            transform=ax.transAxes, fontsize=9, color=INK2, va="top", family=["Consolas", "DejaVu Sans Mono"])
    footnote(fig, "Both axes include the elephant flow. The independent safety guard re-checks every action (90% reroute ceiling, <= 20% flow drop, "
                  ">= 512 kbps floor).\nSource: output/benchmarks/v4/metrics.csv")
    return save(fig, "04_decision_map")


# ---------------------------------------------------------------------------
def fig_memory(rows):
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.35, 1, 1], "wspace": .42})
    fig.subplots_adjust(left=.06, right=.98, top=.78, bottom=.3)
    title(fig, "Does the memory help? It learns, but adds almost nothing over a good fixed rule",
          "Left: how A4's meter decisions shift from trying options to using evidence. Right: A4 minus H2 (same meter, no memory).")
    meters = [r for r in rows if r["condition"] == "A4" and r["installed_action"] == "rate_limit"]
    bins = list(range(0, 120, 10))
    explore = [sum(1 for r in meters if b <= r["cycle"] < b + 10 and "exploration" in r["rationale"]) for b in bins]
    exploit = [sum(1 for r in meters if b <= r["cycle"] < b + 10 and "Episodic" in r["rationale"]) for b in bins]
    share = [100 * e / (e + x) if e + x else 0 for e, x in zip(exploit, explore)]
    ax = axes[0]
    ax.bar([b + 5 for b in bins], [100] * len(bins), width=8.4, color="#fbd9cb", zorder=2)
    ax.bar([b + 5 for b in bins], share, width=8.4, color=BLUE, zorder=3)
    ax.set_xlabel("Window (10-window bins)"); ax.set_ylabel("Share of meter decisions (%)")
    ax.set_ylim(0, 100); ax.set_xlim(-2, 122); ax.grid(axis="x", visible=False)
    ax.add_patch(Rectangle((.02, -.27), .03, .05, color=BLUE, transform=ax.transAxes, clip_on=False))
    ax.text(.065, -.245, "chosen from >= 3 similar past episodes", transform=ax.transAxes, fontsize=9, color=INK2, va="center")
    ax.add_patch(Rectangle((.02, -.36), .03, .05, color="#fbd9cb", transform=ax.transAxes, clip_on=False))
    ax.text(.065, -.335, "exploration (not enough evidence yet)", transform=ax.transAxes, fontsize=9, color=INK2, va="center")

    order = list(reversed(SCENARIOS))
    for ax, metric, label in ((axes[1], "latency_ms", "Delay difference (ms)"), (axes[2], "loss_pct", "Loss difference (pp)")):
        for y, sc in enumerate(order):
            a4, h2 = seed_means(rows, "A4", metric, [sc]), seed_means(rows, "H2", metric, [sc])
            delta = [a4[s] - h2[s] for s in a4]
            m, (lo, hi) = mean(delta), bootstrap(delta)
            ax.plot([lo, hi], [y, y], color=INK2, lw=1.2, zorder=2)
            ax.scatter([m], [y], s=55, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.axvline(0, color=AXIS, lw=1)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([SCENARIO_NAMES[s] for s in order] if ax is axes[1] else [])
        ax.set_xlabel(label); ax.grid(axis="y", visible=False)
        ax.text(.5, -.22, "left of 0 = memory better", transform=ax.transAxes, ha="center", fontsize=9, color=MUTED)
    footnote(fig, "Dots: mean over 10 seeds; whiskers: paired 95% bootstrap. Memory mostly converges to 0.0 Mbps headroom, "
                  "which trims loss by hundredths of a point and costs a fraction of a ms. Source: output/benchmarks/v4/metrics.csv")
    return save(fig, "05_does_memory_help")


# ---------------------------------------------------------------------------
def fig_llm_timing():
    groups = {"answered": ("api",), "reused / skipped": ("api_cache", "local_rule_cache", "healthy_bypass", "episodic_memory")}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    fig.subplots_adjust(left=.07, right=.8, top=.78, bottom=.16, wspace=.08)
    title(fig, "Real LLM calls vs the 5-second control window",
          "Every window of the final pooled pilot (seeds 1980/1981, 'bounded' mode). Observations arrive every 5 wall-clock seconds.")
    for ax, provider in zip(axes, ("gemini", "openrouter")):
        with (SRC / f"latency_{provider}_pooled" / "metrics.csv").open(encoding="utf-8") as handle:
            rows = [r for r in csv.DictReader(handle) if r["mode"] == "bounded"]
        for i, r in enumerate(rows):
            origin = r["origin"]
            kind = next((k for k, v in groups.items() if origin in v), "LLM failed -> local rule")
            color = {"answered": BLUE, "reused / skipped": MUTED}.get(kind, ORANGE)
            ax.scatter(i, float(r["control_elapsed_ms"]) / 1000, s=46, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.axhline(5, color=INK2, lw=1.2, ls=(0, (4, 3)))
        ax.axhline(3.8, color=MUTED, lw=1, ls=(0, (1, 2)))
        ax.set_title(provider.capitalize() if provider == "gemini" else "OpenRouter (free router)", fontsize=11, loc="left", color=INK)
        ax.set_xlabel("Window (both seeds)"); ax.set_ylim(-.15, 5.6)
    axes[0].set_ylabel("Control time per window (s)")
    axes[1].text(1.01, 5 / 5.75 + .02, "5 s window", transform=axes[1].transAxes, fontsize=9, color=INK2, va="center")
    axes[1].text(1.01, 3.95 / 5.75 + .02, "3.8 s wait budget", transform=axes[1].transAxes, fontsize=9, color=MUTED, va="center")
    for i, (label, color) in enumerate((("LLM answered", BLUE), ("reused or skipped\n(cache, memory, healthy)", MUTED),
                                        ("LLM timed out or failed\n-> local rule installed", ORANGE))):
        axes[1].scatter([], [], s=46, color=color, label=label)
    axes[1].legend(loc="upper left", bbox_to_anchor=(1.0, .55), fontsize=9)
    footnote(fig, "No window missed the 5 s deadline. The LLM only suggests; local code rebuilds the exact rule and the guard validates it. "
                  "Sources: output/benchmarks/v4/latency_*_pooled/metrics.csv")
    return save(fig, "06_llm_calls_vs_deadline")


# ---------------------------------------------------------------------------
def tables(rows):
    agg = defaultdict(list)
    for r in rows:
        for k in ("latency_ms", "throughput_kbps", "loss_pct", "reward"):
            agg[(r["scenario"], r["condition"], k)].append(r[k])
    controllers = ["A0", "B1", "H1", "H2", "A4", "O2"]
    lines = ["# SELF-X benchmark tables (generated)", "",
             "Generated by `scripts/explainer_figures.py` from `output/benchmarks/v4/metrics.csv`.",
             "Fluid-model simulation: 8 scenarios x 10 seeds x 120 windows per controller.", "",
             "## Overall (equal weight per scenario)", "",
             "| Controller | What it is | Delay ms | vs A0 | Loss % | vs A0 | Goodput Mbps |", "|---|---|---:|---:|---:|---:|---:|"]
    names = dict(LADDER)
    base = {k: mean(mean(agg[(sc, "A0", k)]) for sc in SCENARIOS) for k in ("latency_ms", "loss_pct")}
    for c in ["A0", "B1", "A2", "H1", "H2", "A4", "O2"]:
        d = mean(mean(agg[(sc, c, "latency_ms")]) for sc in SCENARIOS)
        l = mean(mean(agg[(sc, c, "loss_pct")]) for sc in SCENARIOS)
        g = mean(mean(agg[(sc, c, "throughput_kbps")]) for sc in SCENARIOS) / 1000
        lines.append(f"| {'**A4**' if c == 'A4' else c} | {names[c]} | {d:.2f} | {100 * (d - base['latency_ms']) / base['latency_ms']:+.1f}% "
                     f"| {l:.2f} | {100 * (l - base['loss_pct']) / base['loss_pct']:+.1f}% | {g:.2f} |")
    for metric, label in (("latency_ms", "Delay (ms) by scenario"), ("loss_pct", "Total loss (%) by scenario")):
        lines += ["", f"## {label}", "", "| Scenario | " + " | ".join(controllers) + " | A4 vs A0 |",
                  "|---|" + "---:|" * (len(controllers) + 1)]
        for sc in SCENARIOS:
            vals = [mean(agg[(sc, c, metric)]) for c in controllers]
            change = 100 * (vals[4] - vals[0]) / vals[0] if vals[0] else 0
            lines.append(f"| {SCENARIO_NAMES[sc]} | " + " | ".join(f"{v:.2f}" for v in vals) +
                         f" | {'no change' if abs(change) < .05 else f'{change:+.1f}%'} |")
    lines += ["", "A0 static · B1 greedy least-loaded · H1 guard + fixed 20% meter · H2 capacity-aware meter, no memory · "
              "A4 SELF-X meter + memory · O2 oracle with privileged outcome access (not deployable).", ""]
    (OUT / "benchmark_tables.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = load_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    made = [fig_where_gain_comes_from(rows), fig_one_episode(rows), fig_scenarios(rows),
            fig_decision_map(rows), fig_memory(rows), fig_llm_timing()]
    tables(rows)
    (OUT / "manifest.json").write_text(json.dumps({"source": "output/benchmarks/v4", "figures": made,
                                                   "tables": "benchmark_tables.md"}, indent=2), encoding="utf-8")
    print("\n".join(str(OUT / f"{m}.png") for m in made))


if __name__ == "__main__":
    main()
