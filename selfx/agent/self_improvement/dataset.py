"""Completed replay curation with seed-group separation and frozen manifests."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from agent.loss_aware_memory import capacity_policy
from agent.reward import compute_reward
from agent.schemas import DecisionOutput
from eval.simulator import BUFFER, CAPACITY, FluidNetwork, decision_for
from eval.run_benchmarks import scenario_trace
from .common import digest, finite, read, read_rows, sha256, write, write_rows

SPLIT_SEEDS = {"train": list(range(3000, 3008)), "stress": list(range(3100, 3104)),
               "holdout": list(range(3200, 3206))}
PROFILES = ("mixed", "flash", "alternate")


def verify_outcome(obs, params, outcome, reward):
    """Recompute completed calibrated-model episodes instead of trusting labels."""
    decision=DecisionOutput.model_validate(params)
    if not decision.is_well_formed():
        raise ValueError("malformed recorded action")
    demand={k:obs[k] for k in ("primary_background_mbps","alternate_background_mbps","elephant_mbps")}
    net=FluidNetwork();net.queue=list(obs["queues_mbit"])
    guard=net.validate(demand,decision)
    installed=decision if guard.allowed else decision_for("no_op",demand,"Independent recorded-action veto")
    measured=net.evaluate(demand,installed)
    baseline=net.evaluate(demand,decision_for("no_op",demand,"same-window reference"))
    for key in ("latency_ms","throughput_kbps","loss_pct"):
        if abs(finite(outcome[key],key)-getattr(measured,key))>1e-6:
            raise ValueError("completed outcome fails independent replay")
    expected=compute_reward(baseline.metrics(),measured.metrics()).reward
    if abs(finite(reward,"reward")-expected)>1e-6:
        raise ValueError("completed reward fails independent replay")
    return guard


def observation(state):
    """Use explicit model telemetry; never invent live queues or route feasibility."""
    if not isinstance(state, dict) or not isinstance(state.get("simulation"), dict):
        raise ValueError("local adapter requires calibrated simulation telemetry")
    s = state["simulation"]
    keys = ("capacity_mbps", "buffer_mbit", "primary_background_mbps", "alternate_background_mbps", "elephant_mbps")
    result = {k: finite(s[k], k) for k in keys}
    if result["capacity_mbps"] <= 0 or result["buffer_mbit"] <= 0 or any(result[k] < 0 for k in keys[2:]):
        raise ValueError("invalid capacity, buffer or offered demand")
    if result["capacity_mbps"] != CAPACITY or result["buffer_mbit"] != BUFFER:
        raise ValueError("telemetry does not match the calibrated two-path simulator")
    queues = s.get("queues_mbit")
    if not isinstance(queues, list) or len(queues) != 2:
        raise ValueError("two observed queues are required")
    result["queues_mbit"] = [finite(q, "queue") for q in queues]
    if any(q < 0 or q > result["buffer_mbit"] + 1e-8 for q in result["queues_mbit"]):
        raise ValueError("observed queue outside configured buffer")
    return result


def normalise(raw):
    """Accept new replay records and existing run_simulation trace.jsonl records."""
    metrics = raw.get("metrics", {})
    state = raw.get("state_summary", raw.get("state"))
    action = raw.get("params", raw.get("decision"))
    outcome = raw.get("outcome")
    if not isinstance(outcome, dict) or not isinstance(action, dict):
        raise ValueError("completed outcome and structured decision required")
    obs = observation(state)
    provenance = raw.get("provenance", metrics.get("provenance"))
    if provenance not in {"simulation", "recorded_testbed", "live"}:
        raise ValueError("explicit provenance required")
    seed = raw.get("seed", metrics.get("seed"))
    cycle = raw.get("cycle", metrics.get("cycle"))
    if type(seed) is not int or type(cycle) is not int or cycle < 0:
        raise ValueError("integer seed and completed cycle required")
    reward = finite(raw.get("reward", metrics.get("reward")), "reward")
    reflection = raw.get("reflection")
    if not isinstance(reflection, str) or not reflection.strip():
        raise ValueError("completed reflection required")
    decision = DecisionOutput.model_validate(action)
    if not decision.is_well_formed():
        raise ValueError("malformed recorded action")
    for k in ("latency_ms", "throughput_kbps", "loss_pct"):
        finite(outcome[k], k)
    demand = {k: obs[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps")}
    guard = verify_outcome(obs,action,outcome,reward)
    approved = raw.get("approved", raw.get("safety", {}).get("allowed"))
    if type(approved) is not bool:
        raise ValueError("explicit Boolean approval required")
    record = {"schema": "selfx.replay.v1", "seed": seed, "cycle": cycle,
              "profile": str(raw.get("profile", metrics.get("phase", "recorded"))),
              "observation": obs, "action": decision.action, "params": decision.model_dump(),
              "reward": reward, "reflection": reflection[:2000], "approved": approved and guard.allowed,
              "provenance": provenance, "outcome": {k: outcome[k] for k in ("latency_ms", "throughput_kbps", "loss_pct")}}
    record["context_sha256"] = digest(obs)
    record["episode_id"] = digest({k: record[k] for k in ("seed", "cycle", "profile", "observation", "action", "reward")})
    return record


def collect_bootstrap(folder, cycles=48, policy=None, seeds=None):
    """Retain measured heuristic bootstrap, or actual incumbent on-policy outcomes."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for split, split_seeds in (seeds or SPLIT_SEEDS).items():
        rows = []
        for seed in split_seeds:
            for profile in PROFILES:
                net = FluidNetwork()
                for cycle, demand in enumerate(scenario_trace(profile, seed, cycles)):
                    state = net.summary(demand)
                    chosen = policy(state, demand) if policy else capacity_policy(state, demand)
                    # Training retains failures for analysis, but never approves them for fitting.
                    if policy is None and cycle % 17 == 16:
                        chosen = decision_for("reroute", demand, "Explicit bootstrap exploration")
                    guard = net.validate(demand, chosen)
                    installed = chosen if guard.allowed else decision_for("no_op", demand, "Recorded safety veto")
                    before = net.evaluate(demand, decision_for("no_op", demand, "same-window reference"))
                    outcome = net.evaluate(demand, installed, commit=True)
                    reward = compute_reward(before.metrics(), outcome.metrics()).reward
                    rows.append({"schema": "selfx.replay.v1", "seed": seed, "cycle": cycle,
                        "profile": profile, "provenance": "simulation", "state_summary": state,
                        "params": chosen.model_dump(), "reward": reward, "approved": guard.allowed,
                        "outcome": outcome.__dict__, "reflection":
                        f"Requested {chosen.action}; installed {installed.action}; measured reward {reward:.6f}; guard: {guard.reason}",
                        "behavior": "active_adapter_on_policy" if policy else "capacity_heuristic_bootstrap"})
        path = folder / f"{split}_replay.jsonl"
        write_rows(path, rows)
        result.append(path)
    return result


def build_dataset(sources, folder, split_seeds=None, min_reward=0.0):
    folder = Path(folder)
    if (folder / "manifest.json").exists():
        raise FileExistsError("dataset is immutable; select a new output directory")
    split_seeds = split_seeds or SPLIT_SEEDS
    if set(split_seeds) != {"train", "stress", "holdout"}:
        raise ValueError("train, stress and holdout splits required")
    flattened = [s for values in split_seeds.values() for s in values]
    if len(set(flattened)) != len(flattened):
        raise ValueError("seed groups must not overlap")
    seed_to_split = {seed: split for split, seeds in split_seeds.items() for seed in seeds}
    rows = {s: [] for s in split_seeds}
    rejected, seen_ids, seen_contexts, source_hashes = [], set(), {}, {}
    for source in sources:
        source = Path(source)
        source_hashes[str(source.resolve())] = sha256(source)
        if source.suffix == ".jsonl":
            raw_rows = read_rows(source)
        else:
            raw_rows = read(source)
            if not isinstance(raw_rows, list):
                raise ValueError("source must be an episode list or JSONL")
        for sequence, raw in enumerate(raw_rows):
            try:
                row = normalise(raw)
                split = seed_to_split[row["seed"]]
                if row["episode_id"] in seen_ids:
                    continue
                prior_split = seen_contexts.get(row["context_sha256"])
                if prior_split is not None and prior_split != split:
                    raise ValueError("duplicate observation across independent splits")
                seen_contexts[row["context_sha256"]] = split
                seen_ids.add(row["episode_id"])
                if split == "train" and (not row["approved"] or row["reward"] < min_reward):
                    rejected.append({"episode": row, "reason": "unsafe_or_below_training_reward"})
                else:
                    rows[split].append(row)
            except (ValueError, KeyError, TypeError) as exc:
                # Keep an audit locator, not arbitrary potentially sensitive source content.
                if "across independent splits" in str(exc):
                    raise
                rejected.append({"source_sha256": source_hashes[str(source.resolve())],
                                 "sequence": sequence, "reason": type(exc).__name__})
    if any(not entries for entries in rows.values()):
        raise ValueError("every independent split must contain completed episodes")
    manifest = {"schema": "selfx.lora.dataset.v1", "selection": "approved_completed_reward_threshold",
                "min_reward": finite(min_reward, "min_reward"), "split_seeds": split_seeds,
                "source_sha256": source_hashes, "splits": {}}
    for split, entries in rows.items():
        entries.sort(key=lambda r: (r["seed"], r["profile"], r["cycle"], r["episode_id"]))
        path = folder / f"{split}.jsonl"
        write_rows(path, entries)
        manifest["splits"][split] = {"file": path.name, "sha256": sha256(path), "count": len(entries),
                                     "actions": dict(Counter(r["action"] for r in entries))}
    write_rows(folder / "excluded.jsonl", rejected)
    manifest["excluded"] = {"count": len(rejected), "sha256": sha256(folder / "excluded.jsonl")}
    write(folder / "manifest.json", manifest)
    return manifest


def verify_dataset(folder):
    folder = Path(folder)
    m = read(folder / "manifest.json")
    if m.get("schema")!="selfx.lora.dataset.v1" or set(m["split_seeds"])!={"train","stress","holdout"}:
        raise ValueError("invalid dataset manifest")
    finite(m["min_reward"],"training reward threshold")
    seeds = [s for values in m["split_seeds"].values() for s in values]
    if not seeds or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("overlapping split seed groups")
    contexts, episode_ids = {}, set()
    for split in ("train", "stress", "holdout"):
        entry = m["splits"][split]
        if entry["file"] != f"{split}.jsonl" or sha256(folder / entry["file"]) != entry["sha256"]:
            raise ValueError("dataset artifact hash mismatch")
        rows = read_rows(folder / entry["file"])
        if len(rows) != entry["count"] or not rows:
            raise ValueError("dataset row count mismatch")
        for row in rows:
            if row["episode_id"] in episode_ids:
                raise ValueError("duplicate curated episode")
            episode_ids.add(row["episode_id"])
            if type(row["approved"]) is not bool or type(row["cycle"]) is not int or row["cycle"]<0:
                raise ValueError("invalid completed episode metadata")
            if row["provenance"] not in {"simulation","recorded_testbed","live"}:
                raise ValueError("invalid curated provenance")
            checked=observation({"simulation":row["observation"]})
            if checked!=row["observation"] or row["params"]["action"]!=row["action"]:
                raise ValueError("curated observation or action mismatch")
            if not isinstance(row["reflection"],str) or not row["reflection"].strip():
                raise ValueError("completed reflection is missing")
            expected_id=digest({k:row[k] for k in ("seed","cycle","profile","observation","action","reward")})
            if expected_id!=row["episode_id"]:
                raise ValueError("episode identity mismatch")
            guard=verify_outcome(checked,row["params"],row["outcome"],row["reward"])
            if row["seed"] not in m["split_seeds"][split]:
                raise ValueError("episode assigned to wrong split")
            fingerprint = digest(row["observation"])
            if fingerprint != row["context_sha256"]:
                raise ValueError("observation hash mismatch")
            if fingerprint in contexts and contexts[fingerprint] != split:
                raise ValueError("cross-split observation leakage")
            contexts[fingerprint] = split
            if split == "train" and (row["approved"] is not True or not guard.allowed or row["reward"] < m["min_reward"]):
                raise ValueError("unapproved training episode")
        if dict(Counter(r["action"] for r in rows))!=entry["actions"]:
            raise ValueError("dataset action counts differ from manifest")
    if sha256(folder/"excluded.jsonl")!=m["excluded"]["sha256"] or len(read_rows(folder/"excluded.jsonl"))!=m["excluded"]["count"]:
        raise ValueError("excluded-record audit mismatch")
    return m
