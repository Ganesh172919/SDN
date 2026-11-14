"""Reproduce and compare the raw proposals of the two frozen neural arms."""
import argparse
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

import torch
import run_audited_comparison as benchmark


DEFAULT = Path(__file__).resolve().parents[2] / "paper" / "comparison"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT / "runs.json")
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    ref = json.loads(args.runs.read_text(encoding="utf-8"))
    if ref["smoke"]:
        raise ValueError("Expected a full benchmark.")
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    policies, evidence = benchmark.train_baselines(len(ref["train_seeds"]), ref["training_sec_per_seed"])
    if evidence != ref["baseline_training"]:
        raise AssertionError("Neural training evidence differs.")
    expected = {(r["seed"], r["configuration"]): r for r in ref["runs"]}
    safe = benchmark.safe_action
    overall = Counter()
    for seed in ref["test_seeds"]:
        _, series, fingerprint = benchmark.trace(seed, ref["test_sec_per_seed"])
        traces = {}
        for arm, policy in policies.items():
            records = traces[arm] = []

            def record(action, elephant):
                effective, veto = safe(action, elephant)
                records.append((action.key(), effective.key(), veto))
                return effective, veto

            with patch.object(benchmark, "safe_action", record):
                actual = benchmark.run_episode(arm, series, neural=policy, seed=seed)
            original = expected[seed, arm]
            if (fingerprint != original["traffic_sha256"]
                    or actual["effective_actions_sha256"] != original["effective_actions_sha256"]
                    or actual["windows"] != original["windows"]
                    or len(records) != len(series)):
                raise AssertionError(f"Replay mismatch: {arm}, {seed}")
        for left, right in zip(traces["dqn"], traces["marl"], strict=True):
            p, x, veto_dqn = left
            q, y, veto_iql = right
            if x != y:
                raise AssertionError(f"Different effective actions on seed {seed}")
            overall["slots"] += 1
            if p != q:
                overall["raw_disagreements"] += 1
                overall["disagreements_mapped_to_primary"] += x[0] == "no_op"
                overall["disagreements_with_veto"] += veto_dqn or veto_iql
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "neural_guard_check.json").write_text(
        json.dumps(overall, indent=2) + "\n", encoding="utf-8")
    print(dict(overall))


if __name__ == "__main__":
    main()
