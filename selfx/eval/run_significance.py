"""
Paired significance tests over the pipeline study.

Pairing is per (seed, window): every configuration saw the identical offered
demand in window w of seed s, so window-level differences are matched and the
paired test is the right one. Pairing on 5 seeds alone would leave n = 5, which
is too few to say anything; pairing on matched windows gives n = seeds x windows
while keeping the comparison matched.

Window-level observations inside one seed are serially dependent, so the paired
t-test is reported alongside a Wilcoxon signed-rank test and a seed-level
cluster bootstrap, which resamples whole seeds and therefore respects that
dependence. Where the three disagree the bootstrap interval is the one to
believe, and the paper reports it.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY = PROJECT_ROOT / "selfx" / "output" / "pipeline_study"

#: (name, baseline configuration, treatment configuration, metric, direction)
COMPARISONS = [
    ("S5vsS0", "S0", "S5", "reward", "higher"),
    ("S5vsS1", "S1", "S5", "reward", "higher"),
    ("S5vsS2", "S2", "S5", "reward", "higher"),
    ("S5vsS3", "S3", "S5", "reward", "higher"),
    ("S5vsS4", "S4", "S5", "reward", "higher"),
    ("S5vsQ", "tabular_q", "S5", "reward", "higher"),
    ("LatS5vsS0", "S0", "S5", "latency_ms", "lower"),
    ("LossS5vsS0", "S0", "S5", "loss_pct", "lower"),
]

BOOTSTRAP_DRAWS = 10_000
SEED = 20261109


def paired_series(runs: List[Dict[str, Any]], base: str, treat: str,
                  metric: str) -> Tuple[List[float], List[int]]:
    """Return per-window differences (treatment - baseline) and their seed labels."""
    index: Dict[Tuple[str, int], Dict[int, float]] = {}
    for run in runs:
        key = (run["configuration"], run["seed"])
        index[key] = {w["window"]: w[metric] for w in run["per_window"]}

    diffs: List[float] = []
    seeds: List[int] = []
    for (cfg, seed), rows in index.items():
        if cfg != treat:
            continue
        other = index.get((base, seed))
        if other is None:
            continue
        for window, value in sorted(rows.items()):
            if window in other:
                diffs.append(value - other[window])
                seeds.append(seed)
    return diffs, seeds


def cluster_bootstrap(diffs: Sequence[float], seeds: Sequence[int],
                      draws: int = BOOTSTRAP_DRAWS) -> Tuple[float, float]:
    """95% interval for the mean difference, resampling whole seeds."""
    by_seed: Dict[int, List[float]] = {}
    for diff, seed in zip(diffs, seeds):
        by_seed.setdefault(seed, []).append(diff)
    clusters = list(by_seed.values())
    rng = random.Random(SEED)
    means: List[float] = []
    for _ in range(draws):
        sample: List[float] = []
        for _ in range(len(clusters)):
            sample.extend(clusters[rng.randrange(len(clusters))])
        means.append(statistics.mean(sample))
    means.sort()
    lo = means[int(0.025 * draws)]
    hi = means[int(0.975 * draws) - 1]
    return lo, hi


def p_value_tex(p: float) -> str:
    if p == 0.0 or p < 1e-12:
        return "$<10^{-12}$"
    if p < 1e-4:
        exponent = int(math.floor(math.log10(p)))
        return f"$<10^{{{exponent + 1}}}$"
    return f"${p:.4f}$"


def main() -> int:
    runs = json.loads((STUDY / "pipeline_runs.json").read_text(encoding="utf-8"))
    available = {r["configuration"] for r in runs}

    tests: Dict[str, Any] = {}
    for name, base, treat, metric, direction in COMPARISONS:
        if base not in available or treat not in available:
            continue
        diffs, seeds = paired_series(runs, base, treat, metric)
        if len(diffs) < 3:
            continue
        t_stat, p_two = stats.ttest_rel(
            [d for d in diffs], [0.0] * len(diffs)
        ) if False else stats.ttest_1samp(diffs, 0.0)
        try:
            w_stat, w_p = stats.wilcoxon(diffs)
        except ValueError:
            w_stat, w_p = float("nan"), float("nan")
        sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
        cohens_d = statistics.mean(diffs) / sd if sd else 0.0
        lo, hi = cluster_bootstrap(diffs, seeds)
        tests[name] = {
            "baseline": base,
            "treatment": treat,
            "metric": metric,
            "better_is": direction,
            "n": len(diffs),
            "n_seeds": len(set(seeds)),
            "mean_difference": round(statistics.mean(diffs), 5),
            "std_difference": round(sd, 5),
            "t_statistic": round(float(t_stat), 4),
            "p_value": float(p_two),
            "p_value_tex": p_value_tex(float(p_two)),
            "wilcoxon_statistic": None if math.isnan(w_stat) else float(w_stat),
            "wilcoxon_p": None if math.isnan(w_p) else float(w_p),
            "cohens_d": round(cohens_d, 4),
            "ci95": [round(lo, 5), round(hi, 5)],
            "ci95_method": f"seed-level cluster bootstrap, {BOOTSTRAP_DRAWS} draws",
            "significant_after_bonferroni": bool(float(p_two) < 0.05 / max(1, len(COMPARISONS))),
            "bootstrap_excludes_zero": bool(lo > 0 or hi < 0),
        }

    report = {
        "test": "Paired window-level comparisons over the SELF-X pipeline study",
        "pairing": "matched (seed, window) pairs on identical offered demand",
        "family_size": len(tests),
        "bonferroni_alpha": round(0.05 / max(1, len(COMPARISONS)), 6),
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": SEED,
        "tests": tests,
    }
    (STUDY / "significance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{'comparison':<12} {'n':>5} {'mean diff':>11} {'t':>9} {'p':>12} "
          f"{'d':>7} {'bootstrap 95% CI':>24}")
    for name, rec in tests.items():
        print(f"{name:<12} {rec['n']:>5} {rec['mean_difference']:>11.4f} "
              f"{rec['t_statistic']:>9.3f} {rec['p_value']:>12.3e} {rec['cohens_d']:>7.2f} "
              f"[{rec['ci95'][0]:>9.4f}, {rec['ci95'][1]:>9.4f}]")
    print(f"\nwritten -> {STUDY / 'significance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
