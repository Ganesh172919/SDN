"""Test whether a fixed governance schedule reproduces S5 on the audited traces."""
import argparse
import json
from pathlib import Path

from run_audited_comparison import ADAPTER, LocalModels, run_episode, trace


ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "paper" / "comparison"
ROLES = ("flow sizing", "routing", "congestion", "safety", "service")


class FixedGovernor:
    def __init__(self, model):
        self.model = model

    def action(self, mice, elephant, adapted):
        return self.model.action(mice, elephant, adapted)

    def govern(self, _):
        return "A", dict.fromkeys(ROLES, "A")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT / "runs.json")
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    reference = json.loads(args.runs.read_text(encoding="utf-8"))
    if reference["smoke"]:
        raise ValueError("This diagnostic requires the full benchmark.")
    model = FixedGovernor(LocalModels(ADAPTER))
    matched = []
    for expected in reference["runs"]:
        if expected["configuration"] != "S5":
            continue
        seed = expected["seed"]
        _, offered, fingerprint = trace(seed, reference["test_sec_per_seed"])
        if fingerprint != expected["traffic_sha256"]:
            raise AssertionError(f"Seed {seed}: offered traffic differs")
        actual = run_episode("S5", offered, model, seed=seed)
        for key in ("windows", "effective_actions_sha256", "conservation_error_mbit"):
            if actual[key] != expected[key]:
                raise AssertionError(f"Seed {seed}: {key} differs")
        matched.append({"seed": seed, "effective_actions_sha256": actual["effective_actions_sha256"],
                        "matched_windows": len(actual["windows"])})
    if len(matched) != len(reference["test_seeds"]):
        raise AssertionError("Missing S5 test traces")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "fixed_governor_check.json").write_text(
        json.dumps({"arm": "S5", "governance_option": "A", "matched_runs": matched}, indent=2)
        + "\n", encoding="utf-8")
    print(f"Fixed governance reproduced all S5 window records and action hashes on {len(matched)} seeds.")


if __name__ == "__main__":
    main()
