"""Check exact reproduction of the recorded audited experimental evidence."""
import argparse
import json
from pathlib import Path


def check(reference, reproduced):
    if reference["smoke"] or reproduced["smoke"]:
        raise ValueError("Both manifests must be from full runs.")
    ref_meta = {key: value for key, value in reference.items() if key != "runs"}
    out_meta = {key: value for key, value in reproduced.items() if key != "runs"}
    if ref_meta != out_meta:
        keys = sorted(key for key in ref_meta.keys() | out_meta.keys()
                      if ref_meta.get(key) != out_meta.get(key))
        raise ValueError(f"Experiment metadata differs: {', '.join(keys)}")
    expected = {(r["configuration"], r["seed"]): r for r in reference["runs"]}
    actual = {(r["configuration"], r["seed"]): r for r in reproduced["runs"]}
    if (expected.keys() != actual.keys() or len(expected) != len(reference["runs"])
            or len(actual) != len(reproduced["runs"])):
        raise ValueError("The paired run inventory is missing runs or contains duplicates.")
    for key, want in expected.items():
        got = actual[key]
        if got != want:
            fields = sorted(field for field in want.keys() | got.keys()
                            if want.get(field) != got.get(field))
            raise ValueError(f"{key}: fields differ: {', '.join(fields)}")
    print(f"Exact match: {len(expected)} controller/seed runs, "
          f"{sum(len(r['windows']) for r in expected.values())} windows, model and neural fingerprints.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("reproduced", type=Path)
    args = parser.parse_args()
    check(json.loads(args.reference.read_text(encoding="utf-8")),
          json.loads(args.reproduced.read_text(encoding="utf-8")))
