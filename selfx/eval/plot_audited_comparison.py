"""Generate the thirteen all-controller XY plots and paired effect report."""
from collections import Counter
import csv
import json
from pathlib import Path
from statistics import mean, variance
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from scipy.stats import t

OUT = Path(__file__).resolve().parents[2] / "paper" / "comparison"
PROFILES = ("steady_bursty", "flash_crowd", "volatile_dpp")
FULL = "S5"
FIGURES = (
    ("mean-delay", "Mean delay over time", "Mean delay (ms)", "latency_ms", "time"),
    ("tail-delay", "Tail delay over time", "P95 slot delay (ms)", "p95_latency_ms", "time"),
    ("goodput", "Goodput over time", "Goodput (Mbps)", "throughput_mbps", "time"),
    ("loss", "Loss over time", "Lost traffic (%)", "loss_pct", "time"),
    ("queue", "Backlog over time", "Mean backlog (Mbit)", "mean_queue_mbit", "time"),
    ("reward", "Cumulative control reward", "Sum of window rewards", "reward", "cumulative"),
    ("rule-churn", "Cumulative rule changes", "Number of effective changes", "installs", "cumulative"),
    ("delay-load", "Delay by offered load", "Mean delay (ms)", "latency_ms", "load"),
    ("goodput-load", "Goodput by offered load", "Goodput (Mbps)", "throughput_mbps", "load"),
    ("loss-load", "Loss by offered load", "Lost traffic (%)", "loss_pct", "load"),
    ("sla-load", "High-delay slots by offered load", "Slots above 50 ms (%)", "delay_over_50_pct", "load"),
    ("delay-cdf", "Distribution of window delay", "Share of windows (%)", "latency_ms", "cdf"),
    ("queue-cdf", "Distribution of peak window backlog", "Share of windows (%)", "max_queue_mbit", "cdf"),
)
PALETTE = (
    "#475569", "#795548", "#8e4678", "#7552bd", "#0d7896", "#111827", "#ba5d15",
    "#787518", "#557fb8", "#d12451", "#a13d12", "#007653", "#228c7b", "#9e7513",
)
MARKERS = ("o", "v", "^", "<", ">", "o", "s", "P", "X", "D", "p", "h", "*", "d")
INK = "#172434"
MUTED = "#526779"
ACCENT = "#006b58"
LOAD_EDGES = (0, 5, 8, 10, 12, 15, 20, float("inf"))


def group_runs(manifest):
    grouped = {name: {} for name in manifest["configs"]}
    expected_seeds = set(manifest["test_seeds"])
    if expected_seeds & set(manifest["train_seeds"]):
        raise ValueError("Train and test traces overlap")
    for run in manifest["runs"]:
        seeds = grouped[run["configuration"]]
        if run["seed"] in seeds:
            raise ValueError("Duplicate run")
        seeds[run["seed"]] = run
        if run["conservation_error_mbit"] > 1e-9:
            raise ValueError("Datapath conservation check failed")
    for seeds in grouped.values():
        if seeds.keys() != expected_seeds:
            raise ValueError("Unpaired controller runs")
        for seed, run in seeds.items():
            reference = grouped[FULL][seed]
            pairing = ("traffic_sha256", "profile")
            if any(run[key] != reference[key] for key in pairing):
                raise ValueError("Paired traffic differs")
            if [w["offered_mbps"] for w in run["windows"]] != [
                w["offered_mbps"] for w in reference["windows"]
            ]:
                raise ValueError("Paired traffic windows differ")
    return {name: dict(sorted(runs.items())) for name, runs in grouped.items()}


def run_metrics(run):
    rows = run["windows"]
    return {
        "latency_ms": mean(w["latency_ms"] for w in rows),
        "loss_pct": 100 * sum(w["lost_mbit"] for w in rows) / sum(w["offered_mbit"] for w in rows),
        "goodput_mbps": mean(w["throughput_mbps"] for w in rows),
        "reward": mean(w["reward"] for w in rows),
    }


def stratified_interval(differences):
    centers = [mean(values) for values in differences]
    n = len(centers)
    parts = [variance(values) / (len(values) * n**2) for values in differences]
    estimate = mean(centers)
    total = sum(parts)
    if total == 0:
        return estimate, [estimate, estimate], 1.0 if estimate == 0 else 0.0
    df = total**2 / sum(part**2 / (len(values) - 1) for part, values in zip(parts, differences))
    margin = float(t.ppf(.975, df)) * total**.5
    p = float(2 * t.sf(abs(estimate) / total**.5, df))
    return estimate, [estimate - margin, estimate + margin], p


def effects(grouped, labels):
    metrics = {name: {seed: run_metrics(r) for seed, r in runs.items()}
               for name, runs in grouped.items()}
    means = {name: {key: mean(m[key] for m in seed_rows.values())
                   for key in ("latency_ms", "loss_pct", "goodput_mbps", "reward")}
             for name, seed_rows in metrics.items()}
    comparisons = {}
    for name, seed_rows in metrics.items():
        if name == FULL:
            continue
        changes = {}
        for metric in means[FULL]:
            differences = [[metrics[FULL][seed][metric] - row[metric] for seed, row in seed_rows.items()
                            if grouped[name][seed]["profile"] == profile] for profile in PROFILES]
            delta, interval, p = stratified_interval(differences)
            changes[metric] = {"delta": delta, "ci95": interval, "p": p}
        comparisons[name] = {
            "label": labels[name], **means[name],
            "delay_reduction_pct": -100 * changes["latency_ms"]["delta"] / means[name]["latency_ms"],
            "loss_reduction_pp": -changes["loss_pct"]["delta"],
            "goodput_gain_pct": 100 * changes["goodput_mbps"]["delta"] / means[name]["goodput_mbps"],
            "changes": changes,
        }
    ordered = sorted(comparisons, key=lambda name: comparisons[name]["changes"]["latency_ms"]["p"])
    previous = 0.0
    for idx, name in enumerate(ordered):
        p = comparisons[name]["changes"]["latency_ms"]["p"]
        previous = max(previous, min(1.0, p * (len(ordered) - idx)))
        comparisons[name]["holm_p_delay"] = previous
    execution = {}
    for name, runs in grouped.items():
        counts = Counter()
        ballots = Counter()
        for run in runs.values():
            counts.update(run["counts"])
            ballots.update(run["ballots"])
        execution[name] = {"counts": dict(counts), "ballots": dict(ballots)}
    same_actions = all(
        run.get("effective_actions_sha256")
        and run["effective_actions_sha256"] == grouped["marl"][seed].get("effective_actions_sha256")
        for seed, run in grouped["dqn"].items()
    )
    return {
        "agentic": means[FULL], "comparisons": comparisons, "execution": execution,
        "neural_effective_actions_match": same_actions,
    }


def load_bins(reference):
    offered = np.array([w["offered_mbps"] for r in reference.values() for w in r["windows"]])
    indices = np.digitize(offered, LOAD_EDGES) - 1
    # Bin membership and horizontal coordinates are fixed by the shared input.
    groups = [indices == i for i in range(len(LOAD_EDGES) - 1)]
    groups = [mask for mask in groups if mask.sum() >= 8]
    return [(float(offered[m].mean()), m) for m in groups]


def curve(runs, metric, method, bins):
    values = np.array([[w[metric] for w in r["windows"]] for r in runs.values()])
    if method == "cdf":
        x = np.sort(values.ravel())
        return x, 100 * np.arange(1, len(x) + 1) / len(x)
    if method == "load":
        return [x for x, _ in bins], [values.ravel()[m].mean() for _, m in bins]
    x = [w["end_sec"] for w in next(iter(runs.values()))["windows"]]
    y = values.mean(axis=0)
    if method == "cumulative":
        return [0, *x], [0, *np.cumsum(y)]
    return x, y


def figures(grouped, labels, directory):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "legend.fontsize": 9,
    })
    bins = load_bins(grouped[FULL])
    paths = []
    for number, (slug, title, ylabel, metric, method) in enumerate(FIGURES, 1):
        fig, ax = plt.subplots(figsize=(10, 5.55))
        fig.subplots_adjust(left=.105, right=.97, bottom=.29, top=.88)
        ax.spines[["top", "right"]].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#c6d1da")
        ax.grid(axis="y", color="#dfe6eb", linewidth=.7)
        ax.set_axisbelow(True)
        handles = {}
        for index, (name, runs) in enumerate(grouped.items()):
            x, y = curve(runs, metric, method, bins)
            stride = {"time": 6, "cumulative": 6, "load": 1, "cdf": 55}[method]
            marks = (index % stride, stride)
            if method == "load" and name in ("dqn", "marl"):
                marks = (int(name == "marl"), 2)
            emphasis = name == FULL
            handles[name], = ax.plot(
                x, y, label=labels[name], color=PALETTE[index], marker=MARKERS[index],
                markevery=marks, markersize=5 if emphasis else 4,
                markerfacecolor=PALETTE[index] if emphasis else "white",
                linestyle=("-", "--", "-.", ":")[index % 4] if not emphasis else "-",
                linewidth=2.6 if emphasis else 1.35, alpha=1 if emphasis else .9,
                zorder=6 if emphasis else 3,
                drawstyle="steps-post" if method == "cdf" else "default",
            )
        ax.set_title(title, loc="left", fontsize=18, weight="bold", color=INK, pad=15)
        ax.set_ylabel(ylabel)
        if method == "cdf":
            ax.set_xlabel("Mean window delay (ms)" if metric == "latency_ms" else "Peak window backlog (Mbit)")
            ax.set_ylim(0, 102)
        elif method == "load":
            ax.set_xlabel("Mean offered load within bin (Mbps)")
        else:
            ax.set_xlabel("Time (s)")
        if "%" in ylabel:
            ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        order = [FULL, *(key for key in grouped if key != FULL)]
        fig.legend(handles=[handles[k] for k in order], ncol=4, loc="lower center",
                   bbox_to_anchor=(.5, .025), frameon=False, handlelength=2.8)
        path = directory / f"{number:02d}-{slug}.png"
        fig.savefig(path, dpi=180, facecolor="white")
        plt.close(fig)
        paths.append(path)
    return paths, bins


def export_effects(report, directory):
    (directory / "effects.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    comparisons = report["comparisons"]
    counters = report["execution"]
    numbers = {
        "AuditDelay": f"{report['agentic']['latency_ms']:.2f}",
        "AuditLoss": f"{report['agentic']['loss_pct']:.2f}",
        "AuditGoodput": f"{report['agentic']['goodput_mbps']:.2f}",
        "AuditStaticReduction": f"{comparisons['S0']['delay_reduction_pct']:.2f}",
        "AuditCadenceReduction": f"{comparisons['S4']['delay_reduction_pct']:.2f}",
        "AuditNeuralReduction": f"{comparisons['dqn']['delay_reduction_pct']:.2f}",
        "AuditNeuralLossDelta": f"{comparisons['dqn']['changes']['loss_pct']['delta']:.2f}",
        "AuditNeuralGoodputDelta": f"{comparisons['dqn']['changes']['goodput_mbps']['delta']:.3f}",
        "AuditNeuralHolm": f"{comparisons['dqn']['holm_p_delay']:.4f}",
        "AuditDPPDelta": f"{comparisons['dpp']['changes']['latency_ms']['delta']:.2f}",
        "AuditDPPHolm": f"{comparisons['dpp']['holm_p_delay']:.4f}",
        "AuditNoLoRADelta": f"{comparisons['no_lora']['changes']['latency_ms']['delta']:.2f}",
        "AuditNoLoRAHolm": f"{comparisons['no_lora']['holm_p_delay']:.4f}",
        "AuditCritiqueCalls": counters["S2"]["counts"].get("critique_calls", 0),
        "AuditCritiqueRevisions": counters["S2"]["counts"].get("critique_revisions", 0),
        "AuditMemoryPrompts": counters["S2"]["counts"].get("nonempty_memory_prompts", 0),
        "AuditSpecialistBallots": counters[FULL]["counts"].get("specialist_ballots", 0),
        "AuditGovernorCalls": counters[FULL]["counts"].get("governance_calls", 0),
        "AuditPriorChanges": counters[FULL]["counts"].get("lora_prior_changed_decision", 0),
    }
    (directory / "results.tex").write_text(
        "% Generated by eval.plot_audited_comparison.\n"
        + "".join(f"\\newcommand{{\\{name}}}{{{value}}}\n" for name, value in numbers.items()),
        encoding="utf-8",
    )
    with (directory / "effects.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "comparator", "mean_delay_ms", "mean_loss_pct", "mean_goodput_mbps",
            "agentic_delay_reduction_pct", "agentic_minus_comparator_delay_ms", "delay_ci95_low_ms",
            "delay_ci95_high_ms", "holm_p_delay", "agentic_loss_reduction_pp", "agentic_goodput_gain_pct",
        ])
        for row in report["comparisons"].values():
            delay = row["changes"]["latency_ms"]
            writer.writerow([row["label"], row["latency_ms"], row["loss_pct"], row["goodput_mbps"],
                             row["delay_reduction_pct"], delay["delta"], *delay["ci95"],
                             row["holm_p_delay"], row["loss_reduction_pp"], row["goodput_gain_pct"]])


def paragraph(pdf, content, x, top, width, size=10, leading=15, color=INK):
    style = ParagraphStyle("text", fontName="Helvetica", fontSize=size, leading=leading,
                           textColor=colors.HexColor(color))
    block = Paragraph(content, style)
    _, height = block.wrap(width, 600)
    block.drawOn(pdf, x, top - height)
    return top - height


def page_header(pdf, label, title, page):
    pdf.setFillColor(colors.HexColor(ACCENT))
    pdf.rect(34, 548, 9, 9, fill=1, stroke=0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(51, 548, label)
    pdf.setFillColor(colors.HexColor(INK))
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(34, 505, title)
    pdf.setStrokeColor(colors.HexColor("#d4dfe7"))
    pdf.line(34, 48, 808, 48)
    pdf.setFillColor(colors.HexColor(MUTED))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(34, 31, "SELF-X  /  AUDITED FLUID-SIMULATION STUDY")
    pdf.drawRightString(808, 31, f"{page:02d} / {len(FIGURES) + 2:02d}")


def comparison_table(pdf, report):
    rows = [["Comparator", "Delay (ms)", "Delay reduction", "Paired 95% CI (ms)", "Holm p",
             "Loss reduction (pp)", "Goodput gain"]]
    for row in report["comparisons"].values():
        low, high = row["changes"]["latency_ms"]["ci95"]
        rows.append([
            row["label"], f"{row['latency_ms']:.2f}", f"{row['delay_reduction_pct']:+.1f}%",
            f"[{low:+.2f}, {high:+.2f}]", f"{row['holm_p_delay']:.3g}",
            f"{row['loss_reduction_pp']:+.2f}", f"{row['goodput_gain_pct']:+.1f}%",
        ])
    table = Table(rows, colWidths=[153, 83, 98, 117, 64, 120, 95], rowHeights=[24] + [19] * (len(rows) - 1))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(INK)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#eef4f6"), colors.white]),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    _, height = table.wrap(774, 360)
    table.drawOn(pdf, 34, 420 - height)


def pdf_atlas(manifest, report, charts, bins, directory):
    pdf = Canvas(str(directory / "SELF_X_Algorithm_Comparison.pdf"), pagesize=(842, 595), invariant=1)
    pdf.setTitle("SELF-X Audited Algorithm Comparison")
    page_header(pdf, "RESULTS", "SELF-X algorithm comparison", 1)
    full = report["agentic"]
    paragraph(pdf, (
        f"SELF-X Agentic averaged <b>{full['latency_ms']:.2f} ms delay</b>, "
        f"<b>{full['loss_pct']:.2f}% loss</b> and <b>{full['goodput_mbps']:.2f} Mbps goodput</b> "
        f"across {len(manifest['test_seeds'])} paired held-out traces."
    ), 34, 478, 774, size=12, leading=17)
    neural = report["comparisons"]["dqn"]
    dpp = report["comparisons"]["dpp"]
    paragraph(pdf, (
        f"Against DQN, Agentic delay reduction was {neural['delay_reduction_pct']:+.2f}% and "
        f"loss reduction was {neural['loss_reduction_pp']:+.2f} pp. Against DPP alone, the delay "
        f"difference was {dpp['changes']['latency_ms']['delta']:+.2f} ms "
        f"(Holm p = {dpp['holm_p_delay']:.3g})."
    ), 34, 452, 774, color=MUTED)
    comparison_table(pdf, report)
    paragraph(pdf, (
        "Positive reductions and gains favour Agentic. The confidence interval is for Agentic delay minus "
        "comparator delay, so negative values favour Agentic. Intervals are pointwise. Holm p-values adjust "
        "the 13 two-sided delay comparisons. Loss reduction is in percentage points."
    ), 34, 132, 774, color=MUTED)
    pdf.showPage()

    page_header(pdf, "METHODS AND EXECUTION", "Which components actually ran?", 2)
    e = report["execution"]
    full_counts = e[FULL]["counts"]
    critique = e["S2"]["counts"]
    net = manifest["baseline_training"]
    merged = [key for key, n in e[FULL]["ballots"].items() if key.startswith("merged_") and n]
    governance_note = (
        "The orchestrator chose the same adjustment at every epoch. "
        if len(merged) == 1 else f"The orchestrator used {len(merged)} distinct adjustments. "
    )
    neural_note = (
        "The guard reduced their different proposals to identical effective action sequences. "
        if report["neural_effective_actions_match"] else ""
    )
    top = 475
    for content in (
        "<b>Matched traces.</b> Four seeds per profile for steady bursts, flash crowds and volatile traffic. "
        "Each controller saw identical demand per seed on two finite-buffer 10 Mbps paths. All actions went "
        "through the same guard. The evaluation models traffic in bits and delay in fluid slots.",
        f"<b>DQN and two-agent independent Q-learning.</b> DQN ran {net['dqn'][0]['optimizer_steps']:,} "
        f"gradient steps. Routing and metering agents ran {net['marl'][0]['optimizer_steps']:,} each, "
        "with separate networks and replay buffers and a shared reward. Neural policies were frozen and "
        "greedy at test time. " + neural_note + "The MARL baseline is project-specific.",
        f"<b>Critique and adaptation.</b> S2 invoked critique {critique.get('critique_calls', 0):,} times, "
        f"used nonempty outcome memory {critique.get('nonempty_memory_prompts', 0):,} times and revised "
        f"{critique.get('critique_revisions', 0):,} proposals. S3 used the shipped SmolLM2 adapter. "
        "The full stack uses its output as a bounded DPP action preference.",
        f"<b>Governance and ablations.</b> The full stack requested {full_counts.get('governance_calls', 0)} "
        f"orchestrator decisions and {full_counts.get('specialist_ballots', 0)} role ballots from one shared "
        f"local model. {governance_note}It changed the objective {full_counts.get('policy_changes', 0)} times. "
        f"The LoRA prior changed {full_counts.get('lora_prior_changed_decision', 0):,} of "
        f"{full_counts.get('dpp_decisions', 0):,} optimiser choices. Separate arms disable each layer, "
        "disable both, or run the same optimisation every 5 s.",
        "<b>Timing and inference.</b> Fast controllers saw current slot observations every 100 ms. Slow "
        "controllers sampled every 5 s. Each local model pass was assigned 400 ms of simulated delay. "
        "Specialists formed one parallel batch followed by the orchestrator. Prompt results were memoised. "
        "The timing budget is an experimental assumption.",
        "<b>Scope.</b> The paired tests estimate differences over traffic seeds for these trained "
        "policies and this topology. The study does not measure hardware performance or establish novelty. "
        "Earlier proxy-based comparisons are superseded.",
    ):
        top = paragraph(pdf, content, 34, top, 760, size=11, leading=16) - 12
    pdf.showPage()

    bin_counts = ", ".join(str(int(mask.sum())) for _, mask in bins)
    for i, (spec, chart) in enumerate(zip(FIGURES, charts), 1):
        page_header(pdf, f"FIGURE {i:02d}  /  ALL {len(manifest['configs'])} CONFIGURATIONS", "", i + 2)
        pdf.drawImage(str(chart), 37, 73, width=768, height=426, preserveAspectRatio=True, mask="auto")
        method = spec[-1]
        if method == "load":
            caption = f"Common demand bins with at least eight windows. Left-to-right counts per controller: {bin_counts}."
        elif method == "cdf":
            caption = "Empirical distribution of 5 s windows pooled across the paired test traces."
        else:
            caption = "Means across paired test seeds at each 5 s window. Overlapping curves can share a position."
        paragraph(pdf, escape(caption), 37, 70, 768, size=9, leading=11, color=MUTED)
        pdf.showPage()
    pdf.save()


def write_gallery(manifest, report, charts, directory):
    full = report["agentic"]
    comparisons = report["comparisons"]
    static = comparisons["S0"]["delay_reduction_pct"]
    dqn = comparisons["dqn"]["delay_reduction_pct"]
    dpp = comparisons["dpp"]["changes"]["latency_ms"]["delta"]
    rows = []
    for row in report["comparisons"].values():
        delay = row["changes"]["latency_ms"]
        low, high = delay["ci95"]
        rows.append(
            f"<tr><th scope='row'>{escape(row['label'])}</th>"
            f"<td>{row['latency_ms']:.2f}</td><td>{row['delay_reduction_pct']:+.2f}%</td>"
            f"<td>[{low:+.2f}, {high:+.2f}]</td><td>{row['holm_p_delay']:.4g}</td>"
            f"<td>{row['loss_reduction_pp']:+.2f}</td><td>{row['goodput_gain_pct']:+.2f}%</td></tr>"
        )
    figures = []
    for i, (spec, chart) in enumerate(zip(FIGURES, charts, strict=True), 1):
        slug, title, *_ = spec
        figures.append(
            f'<figure id="{slug}"><figcaption>{i:02d} {escape(title)}</figcaption>'
            f'<a href="{chart.name}"><img src="{chart.name}" width="1800" height="999" '
            f'alt="{escape(title)} comparing all 14 configurations" '
            f'loading="{"eager" if i == 1 else "lazy"}"></a></figure>'
        )
    neural_note = (
        " DQN and two-agent IQL have identical curves because their executed actions match on every test trace."
        if report["neural_effective_actions_match"] else ""
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SELF-X algorithm comparison</title>
<style>
:root {{ color-scheme: light; font: 16px/1.55 Inter, system-ui, sans-serif;
  color: #172434; background: #f4f7f8; }}
body {{ max-width: 1460px; margin: auto; padding: 2rem clamp(1rem, 4vw, 4rem); }}
h1 {{ font-size: clamp(1.8rem, 4vw, 3rem); line-height: 1.15; margin: .5rem 0; }}
h2 {{ font-size: 1.25rem; }}
p {{ max-width: 78ch; }}
a {{ color: #00614f; text-underline-offset: .2em; }}
nav {{ display: flex; flex-wrap: wrap; gap: .6rem 1.5rem; margin: 1rem 0 2rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 510px), 1fr)); gap: 1rem; }}
figure {{ margin: 0; padding: .65rem; background: white; border: 1px solid #d5e0e5; border-radius: .5rem; }}
figcaption {{ font-weight: 650; padding: .35rem .4rem 0; }}
img {{ width: 100%; height: auto; display: block; }}
details {{ border: 1px solid #d5e0e5; background: white; border-radius: .5rem; padding: .75rem 1rem; }}
summary {{ cursor: pointer; font-weight: 650; }}
.scroll {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; font-variant-numeric: tabular-nums; }}
th, td {{ padding: .4rem .65rem; text-align: right; white-space: nowrap; }}
th:first-child {{ text-align: left; }}
tbody tr:nth-child(odd) {{ background: #f1f5f7; }}
</style>
</head>
<body>
<header>
<h1>SELF-X algorithm comparison</h1>
<p>All {len(charts)} XY graphs compare the same {len(manifest["configs"])} configurations across
{len(manifest["test_seeds"])} paired traffic traces in the fluid simulator.
Agentic averaged <strong>{full["latency_ms"]:.2f} ms</strong> delay,
<strong>{full["loss_pct"]:.2f}%</strong> traffic loss and <strong>{full["goodput_mbps"]:.2f} Mbps</strong> goodput.</p>
<p>Agentic lowered mean delay by <strong>{static:.2f}%</strong> against static forwarding
and <strong>{dqn:.2f}%</strong> against DQN. Its mean delay was <strong>{dpp:+.2f} ms</strong>
relative to fast DPP alone.</p>
<nav aria-label="Results files">
<a href="SELF_X_Algorithm_Comparison.pdf">Open PDF atlas</a>
<a href="effects.csv">Download effects CSV</a>
<a href="runs.json">Download per-seed data</a>
</nav>
</header>
<main>
<details>
<summary>Agentic performance against every comparator</summary>
<p>Positive reductions and gains favour Agentic. The delay interval is the pointwise paired
95% interval for Agentic minus comparator. Holm adjustment applies to the delay tests.</p>
<div class="scroll"><table><thead><tr>
<th scope="col">Comparator</th><th scope="col">Delay (ms)</th><th scope="col">Delay reduction</th>
<th scope="col">Paired 95% CI (ms)</th><th scope="col">Holm p</th><th scope="col">Loss reduction (pp)</th>
<th scope="col">Goodput gain</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
</details>
<h2>Comparison graphs</h2>
<p>Select any graph to open the full-size image.{neural_note}</p>
<div class="grid">{"".join(figures)}</div>
</main>
</body>
</html>
"""
    (directory / "index.html").write_text(html, encoding="utf-8")


def build(directory=OUT):
    manifest = json.loads((directory / "runs.json").read_text(encoding="utf-8"))
    if manifest["smoke"]:
        raise ValueError("The report requires the full benchmark, with four seeds per traffic profile")
    grouped = group_runs(manifest)
    report = effects(grouped, manifest["configs"])
    export_effects(report, directory)
    charts, bins = figures(grouped, manifest["configs"], directory)
    pdf_atlas(manifest, report, charts, bins, directory)
    write_gallery(manifest, report, charts, directory)
    print(f"Generated {len(charts)} charts, paired effects, and PDF in {directory}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    build(parser.parse_args().output)

