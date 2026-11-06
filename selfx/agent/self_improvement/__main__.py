"""CLI for prepare -> train -> stress-gate -> activate/reject -> held-out attribution."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .common import now, read, sha256, write
from .dataset import SPLIT_SEEDS, build_dataset, collect_bootstrap, verify_dataset
from .evaluation import GatePolicy, evaluate
from .policy import MODEL_ID, PROMPT_SHA256, REVISION
from .registry import Registry
from .runtime import RegisteredPolicy
from .training import train
from .deployment import canary


def run(output, steps=120, cycles=48, threads=4):
    output = Path(output)
    if output.exists():
        raise FileExistsError("use a new run directory to preserve previous evidence")
    output.mkdir(parents=True)
    contract = {"schema": "selfx.lora.run.v1", "created_at_utc": now(), "steps": steps, "cycles": cycles,
        "base_model": MODEL_ID, "revision": REVISION, "split_seeds": SPLIT_SEEDS,
        "gate_policy": asdict(GatePolicy()), "prompt_sha256": PROMPT_SHA256,
        "deployment_adapter_fraction": .25,
        "final_test": "holdout evaluated once after stress decisions; no subsequent adapter selection",
        "network_provenance": "fluid simulation; not a live Mininet deployment"}
    write(output/"run_contract.json", contract)
    dataset = output/"dataset"
    sources = collect_bootstrap(output/"replay", cycles)
    manifest = build_dataset(sources, dataset)
    registry = Registry(output/"registry", manifest["splits"]["stress"]["sha256"])
    fitted = train(dataset, output/"trained_weights", steps=steps, threads=threads)
    candidate = canary(fitted,output/"candidate",fraction=.25)
    return finish(output, dataset, candidate, registry, threads)


def finish(output, dataset, candidate, registry=None, threads=4):
    """Finish a previously trained immutable candidate without refitting it."""
    output, dataset, candidate = Path(output), Path(dataset), Path(candidate)
    manifest = verify_dataset(dataset)
    registry = registry or Registry(output/"registry", manifest["splits"]["stress"]["sha256"])
    if (output/"completion.json").exists():
        result = read(output/"completion.json")
        if registry.active()["id"] != result["candidate_sha256"]:
            raise ValueError("completed run has a changed incumbent; start a new cycle")
        return result
    entry = registry.register(candidate)
    before = registry.active()
    if (output/"promotion.json").exists():
        promoted = read(output/"promotion.json")
        before = {"id": read(output/"promotion_stress/report.json")["incumbent_sha256"]}
    else:
        if not (output/"promotion_stress/report.json").exists():
            evaluate(candidate, dataset, output/"promotion_stress", incumbent=registry.path(before), threads=threads)
        promoted = registry.consider(entry, output/"promotion_stress", dataset)
        write(output/"promotion.json", promoted)
    if not promoted["accepted"]:
        return {"status": "candidate_rejected", "decision": promoted, "tasks_complete": False}
    # A real, earlier trained checkpoint exercises the rejection path. No invented scores.
    early = candidate/"checkpoint_1"
    early_entry = registry.register(early)
    if not (output/"rejection_stress/report.json").exists():
        evaluate(early, dataset, output/"rejection_stress", incumbent=registry.path(registry.active()), threads=threads)
    pointer_before = sha256(registry.root/"active.json")
    rejected = read(output/"rejection.json") if (output/"rejection.json").exists() else registry.consider(early_entry, output/"rejection_stress", dataset)
    if rejected["accepted"]:
        raise RuntimeError("earlier checkpoint also improved; rejection demonstration requires another genuine candidate")
    if sha256(registry.root/"active.json") != pointer_before:
        raise AssertionError("rejected candidate modified active policy")
    write(output/"rejection.json", rejected)
    # Controlled runtime fault: verify automatic restoration without damaging real weights.
    def unavailable(*args, **kwargs):
        raise RuntimeError("controlled adapter load fault")
    from eval.simulator import FluidNetwork, traffic_trace
    demand = traffic_trace(3000, 1)[0]
    if not (output/"rollback_demo.json").exists():
        runtime = RegisteredPolicy(registry, policy_factory=unavailable)
        decision = runtime.decide(FluidNetwork().summary(demand), demand)
        rolled = registry.active()
        if decision.action != "no_op" or rolled["id"] != before["id"]:
            raise AssertionError("automatic fault rollback failed")
        write(output/"rollback_demo.json", {"controlled_fault": True, "runtime": runtime.last_event,
            "fallback": decision.model_dump(), "restored": rolled})
    # The same frozen evidence is still valid against the same restored incumbent identity.
    if registry.active()["id"] != entry["id"]:
        restored = registry.consider(entry, output/"promotion_stress", dataset)
        if not restored["accepted"]:
            raise AssertionError("approved adapter could not be reactivated")
    # Retain actual on-policy episodes for the NEXT cycle; they do not train this candidate.
    active_runtime = RegisteredPolicy(registry, threads=threads)
    on_policy_path = output/"on_policy_replay/train_replay.jsonl"
    on_policy = [on_policy_path] if on_policy_path.exists() else collect_bootstrap(output/"on_policy_replay", cycles=8,
        policy=active_runtime.decide, seeds={"train": [3007]})
    holdout = read(output/"heldout_attribution/report.json") if (output/"heldout_attribution/report.json").exists() else evaluate(
        candidate, dataset, output/"heldout_attribution", threads=threads, split="holdout")
    result = {"schema": "selfx.lora.completion.v1", "status": "completed", "owner": "Ganesh",
        "task_ids": [f"T{i}" for i in range(20,26)], "completed_at_utc": now(),
        "candidate_sha256": entry["id"], "active": registry.active(), "fine_tune_iterations": 1,
        "deployment": read(candidate/"training.json").get("deployment",{"adapter_fraction":1.0}),
        "promotion": promoted["gate"] if "gate" in promoted else {k:v for k,v in promoted.items() if k!="active"},
        "rejected_checkpoint": early_entry["id"], "rejection_pointer_unchanged": True,
        "automatic_rollback": "controlled load failure restored prior incumbent",
        "on_policy_sources": {p.name: sha256(p) for p in on_policy},
        "holdout_summary": holdout["summary"], "weight_attribution": holdout["attribution"],
        "scope": "CPU LoRA action policy and frozen-replay evidence; live SDN and full A1-A5 remain separate tasks"}
    write(output/"completion.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", required=True)
    p.add_argument("--cycles", type=int, default=48)
    p.add_argument("--sources", nargs="+")
    p = sub.add_parser("train")
    p.add_argument("--dataset", required=True); p.add_argument("--output", required=True)
    p.add_argument("--steps", type=int, default=120); p.add_argument("--threads", type=int, default=4)
    p.add_argument("--initial-adapter")
    p = sub.add_parser("evaluate")
    p.add_argument("--dataset", required=True); p.add_argument("--candidate", required=True)
    p.add_argument("--output", required=True); p.add_argument("--incumbent")
    p.add_argument("--split", choices=["stress", "holdout"], default="stress")
    p = sub.add_parser("promote")
    p.add_argument("--registry", required=True); p.add_argument("--candidate", required=True)
    p.add_argument("--evaluation", required=True); p.add_argument("--dataset", required=True)
    p = sub.add_parser("rollback")
    p.add_argument("--registry", required=True); p.add_argument("--reason", required=True)
    p = sub.add_parser("status"); p.add_argument("--registry", required=True)
    for name in ("run", "finish"):
        p = sub.add_parser(name); p.add_argument("--output", required=True)
        p.add_argument("--threads", type=int, default=4)
        if name == "run":
            p.add_argument("--steps", type=int, default=120); p.add_argument("--cycles", type=int, default=48)
    args = parser.parse_args()
    if args.command == "prepare":
        root = Path(args.output)
        sources = args.sources or collect_bootstrap(root/"replay", args.cycles)
        result = build_dataset(sources, root/"dataset")
    elif args.command == "train":
        result = {"candidate": str(train(args.dataset,args.output,steps=args.steps,threads=args.threads,initial_adapter=args.initial_adapter))}
    elif args.command == "evaluate":
        result = evaluate(args.candidate,args.dataset,args.output,incumbent=args.incumbent,split=args.split)
    elif args.command == "promote":
        m = verify_dataset(args.dataset)
        registry = Registry(args.registry,m["splits"]["stress"]["sha256"])
        result = registry.consider(registry.register(args.candidate),args.evaluation,args.dataset)
    elif args.command == "rollback":
        result = Registry(args.registry).rollback(args.reason)
    elif args.command == "status":
        registry = Registry(args.registry); result = {"active":registry.active(),"audit_events":len(registry.audit())}
    elif args.command == "finish":
        output = Path(args.output)
        result = finish(output,output/"dataset",output/"candidate",threads=args.threads)
    else:
        result = run(args.output,args.steps,args.cycles,args.threads)
    print(json.dumps(result,indent=2,allow_nan=False))
    if result.get("status") == "candidate_rejected":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
