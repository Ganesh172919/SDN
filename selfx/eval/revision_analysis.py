"""Compute trace-level sensitivity checks for the revised IEEE manuscript."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

import numpy as np

from plot_audited_comparison import PROFILES, effects as audited_effects, group_runs, run_metrics


ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "paper" / "comparison"
BOOTSTRAP_SEED = 466
BOOTSTRAP_DRAWS = 20000


def build(manifest_path, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["smoke"]:
        raise ValueError("Revision sensitivity analysis requires the full benchmark.")
    grouped = group_runs(manifest)
    seeds = [[seed for seed, run in grouped["S5"].items() if run["profile"] == profile]
             for profile in PROFILES]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = [rng.integers(0, len(group), size=(BOOTSTRAP_DRAWS, len(group)))
               for group in seeds]
    metrics = {arm: {seed: run_metrics(run) for seed, run in runs.items()}
               for arm, runs in grouped.items()}
    effects = {}
    for arm in grouped.keys() - {"S5"}:
        paired = [np.array([metrics["S5"][seed]["latency_ms"] - metrics[arm][seed]["latency_ms"]
                           for seed in group]) for group in seeds]
        draws = np.mean([vals[idx].mean(axis=1) for vals, idx in zip(paired, indices)], axis=0)
        effects[arm] = {
            "paired_delay_ms_by_profile": dict(zip(PROFILES, (float(v.mean()) for v in paired))),
            "stratified_trace_bootstrap_ci95_ms": np.quantile(draws, [.025, .975]).tolist(),
        }
    meters = {
        arm: mean(100 * sum(w["meter_mbit"] for w in r["windows"])
                  / sum(w["offered_mbit"] for w in r["windows"])
                  for r in grouped[arm].values())
        for arm in ("S5", "dqn", "marl", "dpp")
    }
    primary = audited_effects(grouped, manifest["configs"])["comparisons"]
    ordered = sorted((k for k in primary if k != "marl"),
                     key=lambda k: primary[k]["changes"]["latency_ms"]["p"])
    adjusted = 0.0
    for rank, arm in enumerate(ordered):
        adjusted = max(adjusted, min(1.0, (len(ordered) - rank)
                                    * primary[arm]["changes"]["latency_ms"]["p"]))
        effects[arm]["holm_p_dedup_neural"] = adjusted
    effects["marl"]["holm_p_dedup_neural"] = effects["dqn"]["holm_p_dedup_neural"]
    for arm, value in primary.items():
        effects[arm]["primary_delay"] = {
            **value["changes"]["latency_ms"], "holm_p": value["holm_p_delay"],
        }
    unchanged = all((effects[k]["holm_p_dedup_neural"] < .05)
                    == (primary[k]["holm_p_delay"] < .05) for k in primary)
    endings = {arm: {seed: max(0., sum(w["offered_mbit"] - w["served_mbit"] - w["lost_mbit"]
                                      for w in r["windows"])) for seed, r in runs.items()}
               for arm, runs in grouped.items()}
    undelivered_delta = mean(
        metrics["S5"][seed]["loss_pct"] - metrics["dqn"][seed]["loss_pct"]
        + 100 * (endings["S5"][seed] - endings["dqn"][seed])
        / sum(w["offered_mbit"] for w in grouped["S5"][seed]["windows"])
        for seed in endings["S5"])
    weighted_delay = {}
    for arm, runs in grouped.items():
        weighted_delay[arm] = mean(
            sum(w["latency_ms"] * w["served_mbit"] for w in r["windows"])
            / sum(w["served_mbit"] for w in r["windows"]) for r in runs.values())
    factorial = [metrics["S5"][seed]["latency_ms"] - metrics["no_lora"][seed]["latency_ms"]
                 - metrics["no_governor"][seed]["latency_ms"] + metrics["dpp"][seed]["latency_ms"]
                 for seed in grouped["S5"]]
    result = {
        "input_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "draws": BOOTSTRAP_DRAWS, "bootstrap_seed": BOOTSTRAP_SEED,
        "profiles": dict(zip(PROFILES, seeds)), "effects": effects,
        "mean_metered_share_pct": meters,
        "end_backlog_mbit_by_seed": endings,
        "s5_minus_dqn_undelivered_volume_pp": undelivered_delta,
        "mean_episode_volume_weighted_delay_ms": weighted_delay,
        "fast_arms_descriptive_delay_interaction_ms": mean(factorial),
        "dedup_neural_holm_conclusions_unchanged_at_0_05": unchanged,
    }
    def interval(arm):
        lo, hi = effects[arm]["stratified_trace_bootstrap_ci95_ms"]
        return f"[{lo:.2f}, {hi:.2f}]"
    macros = {
        "AuditInteraction": f"{mean(factorial):.2f}",
        "AuditUndeliveredDelta": f"{undelivered_delta:.2f}",
        "AuditBacklogFull": f"{mean(endings['S5'].values()):.2f}",
        "AuditBacklogDQN": f"{mean(endings['dqn'].values()):.2f}",
        "AuditGoodputThree": f"{mean(v['goodput_mbps'] for v in metrics['S5'].values()):.3f}",
        "AuditBootCadence": interval("S4"),
        "AuditBootNeural": interval("dqn"),
        "AuditBootDPP": interval("dpp"),
        "AuditMeterShare": f"{meters['S5']:.2f}",
        "AuditCadenceSteady": f"{effects['S4']['paired_delay_ms_by_profile']['steady_bursty']:.2f}",
        "AuditCadenceFlash": f"{effects['S4']['paired_delay_ms_by_profile']['flash_crowd']:.2f}",
        "AuditCadenceVolatile": f"{effects['S4']['paired_delay_ms_by_profile']['volatile_dpp']:.2f}",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "revision_analysis.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "revision_analysis.tex").write_text(
        "% Generated by revision_analysis.py\n"
        + "".join(f"\\newcommand{{\\{key}}}{{{value}}}\n" for key, value in macros.items()),
        encoding="utf-8")
    ids = ("S0", "S1", "S2", "S3", "S4", "threshold", "least_loaded", "tabular_q",
           "dqn", "marl", "dpp", "no_lora", "no_governor")
    short = dict(zip(ids, ("S0", "S1", "S2", "S3", "S4", "TH", "LL", "TQ", "DQN",
                           "IQL", "DPP", "NL", "NG")))
    rows = []
    for arm in ids:
        d = effects[arm]["primary_delay"]
        lo, hi = d["ci95"]
        rows.append(f"{short[arm]} & {d['delta']:+.3f} & [{lo:.3f}, {hi:.3f}] & "
                    f"{d['p']:.4f} & {d['holm_p']:.4f} " + chr(92)*2)
    with (output / "revision_analysis.tex").open("a", encoding="utf-8") as tex:
        tex.write(r"\newcommand{\AuditPairedRows}{%"+"\n"+"\n".join(rows)+"\n}\n")
    print(json.dumps(macros, indent=2))
    print("Deduplicated Holm decisions unchanged:", unchanged)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT / "runs.json")
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    build(args.runs, args.output)
