"""Frozen-replay stress evaluation, independent safety and seed-level attribution."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from agent.reward import compute_reward
from eval.simulator import FluidNetwork, decision_for
from .common import artifact_identity, digest, finite, now, read, read_rows, sha256, write, write_rows
from .dataset import verify_dataset
from .policy import LoRAPolicy, PROMPT_SHA256, REVISION, locally_bound


@dataclass(frozen=True)
class GatePolicy:
    min_mean_reward_gain: float = .002
    max_loss_regression_pct: float = .10
    max_latency_regression_ms: float = 1.0
    max_profile_reward_regression: float = .005
    max_installed_safety_violations: int = 0

    def __post_init__(self):
        for name in ("min_mean_reward_gain","max_loss_regression_pct","max_latency_regression_ms","max_profile_reward_regression"):
            if finite(getattr(self,name),name)<0:
                raise ValueError("gate tolerances must be non-negative")
        if type(self.max_installed_safety_violations) is not int or self.max_installed_safety_violations != 0:
            raise ValueError("installed safety violations must have a zero allowance")


def summaries(records):
    if not records:
        raise ValueError("empty evaluation campaign")
    result = {}
    for role in ("incumbent", "candidate"):
        selected = [r for r in records if r["role"] == role]
        if not selected:
            raise ValueError("both policy roles must be evaluated")
        per_seed, per_profile = defaultdict(list), defaultdict(list)
        for row in selected:
            for key in ("reward", "latency_ms", "throughput_kbps", "loss_pct"):
                finite(row[key], key)
            per_seed[str(row["seed"])].append(row["reward"])
            per_profile[row["profile"]].append(row["reward"])
        result[role] = {"windows": len(selected), "mean_reward": mean(r["reward"] for r in selected),
            "cumulative_reward": sum(r["reward"] for r in selected),
            **{k: mean(r[k] for r in selected) for k in ("latency_ms", "throughput_kbps", "loss_pct")},
            "proposed_unsafe": sum(not r["proposal_allowed"] for r in selected),
            "installed_safety_violations": sum(not r["installed_allowed"] for r in selected),
            "actions": dict(Counter(r["installed_action"] for r in selected)),
            "seed_cumulative_reward": {k: sum(v) for k, v in per_seed.items()},
            "profile_mean_reward": {k: mean(v) for k, v in per_profile.items()}}
    a = {(r["episode_id"], r["seed"], r["profile"]) for r in records if r["role"] == "incumbent"}
    b = {(r["episode_id"], r["seed"], r["profile"]) for r in records if r["role"] == "candidate"}
    if a != b or len(records) != len(a) * 2:
        raise ValueError("unpaired or duplicate evaluation episodes")
    return result


def judge(summary, policy=None):
    policy = policy or GatePolicy()
    candidate, incumbent = summary["candidate"], summary["incumbent"]
    reasons = []
    if candidate["installed_safety_violations"] > policy.max_installed_safety_violations:
        reasons.append("hard_safety_violation")
    if candidate["mean_reward"] - incumbent["mean_reward"] < policy.min_mean_reward_gain:
        reasons.append("insufficient_reward_gain")
    if candidate["loss_pct"] > incumbent["loss_pct"] + policy.max_loss_regression_pct:
        reasons.append("loss_regression")
    if candidate["latency_ms"] > incumbent["latency_ms"] + policy.max_latency_regression_ms:
        reasons.append("latency_regression")
    if candidate["proposed_unsafe"] > incumbent["proposed_unsafe"]:
        reasons.append("more_unsafe_proposals")
    for profile, reward in candidate["profile_mean_reward"].items():
        if reward < incumbent["profile_mean_reward"][profile] - policy.max_profile_reward_regression:
            reasons.append("profile_reward_regression:" + profile)
    return {"accepted": not reasons, "reasons": reasons or ["all_frozen_stress_criteria_passed"],
            "mean_reward_gain": candidate["mean_reward"] - incumbent["mean_reward"]}


def evaluate(candidate, dataset, output, incumbent=None, split="stress", gate_policy=None,
             model=None, threads=4):
    if split not in {"stress", "holdout"}:
        raise ValueError("evaluation split must be stress or holdout")
    output, dataset = Path(output), Path(dataset)
    if output.exists():
        raise FileExistsError("evaluation evidence is immutable")
    manifest = verify_dataset(dataset)
    candidate_id = artifact_identity(candidate)
    incumbent_id = artifact_identity(incumbent) if incumbent else "base:" + REVISION
    actor = model or LoRAPolicy(candidate, incumbent, threads=threads,cache_dir=dataset.parent/"inference_cache")
    if actor.identities["candidate"] != candidate_id:
        raise ValueError("loaded candidate differs from evaluated artifact")
    rows = read_rows(dataset / f"{split}.jsonl")
    observations = [r["observation"] for r in rows]
    records = []
    for role, adapter in (("incumbent", "incumbent" if incumbent else "base"), ("candidate", "candidate")):
        print(f"Evaluating {split}: {role}, {len(rows)} frozen observations", flush=True)
        predictions = actor.predict(observations, adapter)
        if len(predictions)!=len(rows):
            raise ValueError("policy returned an incomplete prediction batch")
        for row, prediction in zip(rows, predictions):
            obs = row["observation"]
            demand = {k: obs[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps")}
            net = FluidNetwork()
            net.queue = list(obs["queues_mbit"])
            decision = locally_bound(prediction["action"], obs, demand)
            guard = net.validate(demand, decision)
            installed = decision if guard.allowed else decision_for("no_op", demand, "Independent safety veto")
            outcome = net.evaluate(demand, installed)
            before = net.evaluate(demand, decision_for("no_op", demand, "same frozen-window reference"))
            records.append({"episode_id": row["episode_id"], "seed": row["seed"], "profile": row["profile"],
                "cycle": row["cycle"], "role": role, "policy_sha256": prediction["policy_sha256"],
                "requested_action": prediction["action"], "installed_action": installed.action,
                "proposal_allowed": guard.allowed, "installed_allowed": net.validate(demand, installed).allowed,
                "decision": installed.model_dump(), "observation": obs, "probabilities": prediction["probabilities"],
                "adapter_used": prediction.get("adapter_used",role=="candidate"),
                "adapter_fraction": prediction.get("adapter_fraction",1.0 if role=="candidate" else 0.0),
                "reward": compute_reward(before.metrics(), outcome.metrics()).reward,
                "latency_ms": outcome.latency_ms, "throughput_kbps": outcome.throughput_kbps,
                "loss_pct": outcome.loss_pct, "provenance": "simulation_frozen_replay"})
    summary = summaries(records)
    policy = gate_policy or GatePolicy()
    write_rows(output / "trace.jsonl", records)
    report = {"schema": "selfx.lora.evaluation.v1", "created_at_utc": now(), "split": split,
        "candidate_sha256": candidate_id, "incumbent_sha256": incumbent_id,
        "dataset_manifest_sha256": sha256(dataset/"manifest.json"),
        "split_sha256": manifest["splits"][split]["sha256"], "prompt_sha256": PROMPT_SHA256,
        "memory": "disabled for both policies", "network": "fixed replay queues; independent same-window outcomes",
        "provenance": "simulation_frozen_replay", "policy": asdict(policy), "summary": summary,
        "trace_sha256": sha256(output/"trace.jsonl"), "gate": judge(summary, policy)}
    if split == "holdout":
        report["attribution"] = paired_attribution(summary)
        report["not_a_promotion_gate"] = True
    write(output / "report.json", report)
    return report


def paired_attribution(summary):
    from scipy.stats import ttest_rel, t
    import math
    from statistics import stdev
    a, b = summary["candidate"]["seed_cumulative_reward"], summary["incumbent"]["seed_cumulative_reward"]
    seeds = sorted(a)
    differences = [a[s]-b[s] for s in seeds]
    if len(seeds) < 2:
        return {"seeds": seeds, "p_value": None, "mean_cumulative_reward_gain": mean(differences)}
    result = ttest_rel([a[s] for s in seeds], [b[s] for s in seeds])
    if stdev(differences) == 0:
        p_value = 0. if differences[0] != 0 else 1.
        half = 0.
    else:
        p_value = float(result.pvalue)
        half = float(t.ppf(.975, len(seeds)-1)) * stdev(differences)/math.sqrt(len(seeds))
    return {"seeds": seeds, "unit_of_replication": "independent seed, cumulative reward over 3 profiles",
            "test": "two-sided paired t-test, adapter versus bare base; not A1-to-A5",
            "p_value": p_value, "mean_cumulative_reward_gain": mean(differences),
            "ci95": [mean(differences)-half, mean(differences)+half],
            "same_prompt": True, "same_memory": "disabled", "only_learned_difference": "LoRA weights"}


def verify_report(folder, expected_candidate, expected_incumbent, expected_stress_hash, policy, dataset, expected_split="stress"):
    folder = Path(folder)
    dataset = Path(dataset)
    if expected_split not in {"stress","holdout"}:
        raise ValueError("unknown verification split")
    dataset_manifest = verify_dataset(dataset)
    if dataset_manifest["splits"][expected_split]["sha256"] != expected_stress_hash:
        raise ValueError("unexpected frozen stress data")
    cases = {row["episode_id"]: row for row in read_rows(dataset/f"{expected_split}.jsonl")}
    report = read(folder/"report.json")
    if report["split"] != expected_split or (expected_split=="stress" and report.get("not_a_promotion_gate")):
        raise ValueError("holdout results cannot authorize promotion")
    if (report["candidate_sha256"], report["incumbent_sha256"], report["split_sha256"]) != (
        expected_candidate, expected_incumbent, expected_stress_hash):
        raise ValueError("stale or mismatched promotion evidence")
    if report["dataset_manifest_sha256"] != sha256(dataset/"manifest.json"):
        raise ValueError("evaluation dataset-manifest lineage mismatch")
    if report["policy"] != asdict(policy) or report["prompt_sha256"] != PROMPT_SHA256:
        raise ValueError("promotion thresholds or input representation changed")
    if sha256(folder/"trace.jsonl") != report["trace_sha256"]:
        raise ValueError("evaluation trace hash mismatch")
    records = read_rows(folder/"trace.jsonl")
    for row in records:
        source = cases.get(row["episode_id"])
        if source is None or any(row[k] != source[k] for k in ("seed", "cycle", "profile", "observation")):
            raise ValueError("evaluation case differs from frozen stress observation")
        obs = row["observation"]
        demand = {k: obs[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps")}
        net = FluidNetwork()
        net.queue = list(obs["queues_mbit"])
        requested = locally_bound(row["requested_action"], obs, demand)
        guard = net.validate(demand, requested)
        installed = requested if guard.allowed else decision_for("no_op", demand, "Independent safety veto")
        probabilities=row["probabilities"]
        from .policy import ACTIONS
        if (set(probabilities)!=set(ACTIONS) or any(not 0<=finite(v,"action probability")<=1 for v in probabilities.values())
            or abs(sum(probabilities.values())-1)>1e-5
            or max(ACTIONS,key=lambda a:probabilities[a])!=row["requested_action"]):
            raise ValueError("invalid policy action probabilities")
        outcome = net.evaluate(demand, installed)
        before = net.evaluate(demand, decision_for("no_op", demand, "same frozen-window reference"))
        expected_metrics = {"latency_ms": outcome.latency_ms, "throughput_kbps": outcome.throughput_kbps,
            "loss_pct": outcome.loss_pct, "reward": compute_reward(before.metrics(), outcome.metrics()).reward}
        if any(abs(row[k]-v) > 1e-9 for k, v in expected_metrics.items()):
            raise ValueError("reported metrics fail independent replay")
        if (row["proposal_allowed"] != guard.allowed or row["installed_allowed"] is not True
            or row["installed_action"] != installed.action):
            raise ValueError("reported safety outcome fails independent replay")
        if row["decision"] != installed.model_dump() or row["provenance"] != "simulation_frozen_replay":
            raise ValueError("decision or provenance differs from independent replay")
    summary = summaries(records)
    if summary != report["summary"]:
        raise ValueError("summary differs from raw evaluation evidence")
    if summary["candidate"]["windows"] != len(cases):
        raise ValueError("stress campaign is incomplete")
    for row in records:
        expected = expected_candidate if row["role"] == "candidate" else expected_incumbent
        if row["policy_sha256"] != expected:
            raise ValueError("evaluated policy identity mismatch")
    return report, judge(summary, policy)
