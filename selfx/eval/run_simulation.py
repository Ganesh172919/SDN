"""Reproducible portable experiments, raw traces and paired seed-level intervals."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import platform
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

import config
from agent.memory import MemoryStore
from agent.loss_aware_memory import LossAwareMemory as AdaptiveMemory, loss_aware_policy as adaptive_policy
from agent.bounded_control import BoundedController as FastController
from agent.providers import RestLLM
from agent.schemas import DecisionOutput, ReflectionOutput
from agent import prompts
from agent.reward import compute_reward
from eval.simulator import FluidNetwork, traffic_trace, decision_for, reactive_policy, least_loaded, INTERVAL

LABELS = {"A0": "Static primary path", "B1": "Greedy least-loaded path", "A1": "Controller without memory", "A2": "Original state embedding memory", "A4": "Adaptive memory and fast control"}


def local_path(path: str | Path) -> Path:
    value = Path(path).resolve()
    if not value.is_relative_to(config.PROJECT_ROOT):
        raise ValueError("output must stay inside selfx")
    return value


def run_condition(condition, trace, seed, provider, out_dir, model=None):
    net = FluidNetwork()
    memory_cls=AdaptiveMemory if condition=='A4' else MemoryStore
    memory = memory_cls(str(out_dir / f"{condition}_{seed}_memory.json"), enabled=condition in {"A2","A4"},autosave=condition!='A4')
    memory.clear()
    llm = RestLLM(provider, model) if provider != "offline" and condition in ("A1", "A2") else None
    fast=FastController(provider,model=model) if provider!='offline' and condition=='A4' else None
    if fast:llm=fast.llm
    rows, detailed = [], []
    for cycle, demand in enumerate(trace):
        start = time.perf_counter()
        summary = net.summary(demand)
        examples = memory.few_shot_examples(k=4, query=summary)
        retrieved=[r['cycle'] for r in examples]
        error, origin, attempts = "", "static" if condition == "A0" else "offline", 0
        audit_start = len(llm.audit) if llm else 0
        decision = decision_for("no_op", demand, "Static primary path")
        if condition == "B1":
            decision, origin = least_loaded(summary), "heuristic"
        elif condition=='A4':
            if fast:
                decision,origin,retrieved,error=fast.decide(net,summary,demand,memory,cycle)
                attempts=int(origin in {'api','deadline_fallback','provider_fallback','validation_fallback'})
            else:decision,retrieved=adaptive_policy(net,summary,demand,memory,cycle)
        elif condition in ("A1", "A2"):
            if llm:
                origin = "api"
                for attempts in (1, 2):
                    try:
                        decision = llm.with_structured_output(DecisionOutput).invoke(prompts.build_decide_messages(summary, examples))
                        if not decision.is_well_formed():
                            raise ValueError("malformed_decision")
                        origin, error = "api", ""
                        break
                    except Exception as exc:
                        error = str(exc) if type(exc).__name__ == "ProviderError" else type(exc).__name__
                        decision = decision_for("no_op", demand, "Provider unavailable; explicit safe no_op fallback")
                        origin = "fallback_no_op"
            else:
                decision = reactive_policy(summary, examples, condition == "A2")
        guard = net.validate(demand, decision)
        installed = decision if guard.allowed else decision_for("no_op", demand, "Safety veto: " + guard.reason)
        before = net.evaluate(demand, decision_for("no_op", demand, "paired same-window no-op counterfactual"))
        outcome = net.evaluate(demand, installed, commit=True)
        reward = compute_reward(before.metrics(), outcome.metrics()).reward
        reflection_origin = "deterministic"
        reflection = f"{installed.action} changed modeled latency by {outcome.latency_ms - before.latency_ms:.2f} ms and total loss by {outcome.loss_pct - before.loss_pct:.2f} percentage points; reward {reward:.4f}."
        if llm and origin == "api" and condition!='A4':
            try:
                reflected = llm.with_structured_output(ReflectionOutput).invoke(prompts.build_reflect_messages(summary, installed.action, decision.model_dump(), outcome.metrics().__dict__, reward))
                reflection, reflection_origin = reflected.reflection, "api"
            except Exception:
                reflection_origin = "deterministic_after_api_failure"
        memory.add_record(cycle, summary, installed.action, installed.model_dump(), reward, reflection)
        audit = llm.audit[audit_start:] if llm else []
        if cycle==len(trace)-1 and fast:fast.llm.close()
        row = {"condition": condition, "seed": seed, "cycle": cycle, "time_sec": (cycle + 1) * INTERVAL,
               "phase": demand["phase"], "latency_ms": outcome.latency_ms,
               "throughput_kbps": outcome.throughput_kbps, "loss_pct": outcome.loss_pct,
               "reward": round(reward, 6), "requested_action": decision.action,
               "installed_action": installed.action, "safety_allowed": guard.allowed,
               "decision_origin": origin, "reflection_origin": reflection_origin,
               "memory_examples": len(retrieved), "provider_error": error,
               "decision_attempts": attempts, "control_elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
               "provenance": "simulation", "offered_mbit": outcome.offered_mbit,
               "delivered_mbit": outcome.delivered_mbit, "dropped_mbit": outcome.dropped_mbit,
               "meter_dropped_mbit": outcome.meter_dropped_mbit}
        rows.append(row)
        detailed.append({"metrics": row, "demand": demand, "state": summary, "decision": decision.model_dump(),
                         "safety": guard.__dict__, "outcome": outcome.__dict__, "reflection": reflection,
                         "retrieved_cycles": retrieved, "provider_calls": audit})
        if llm:
            print(f"{condition} seed={seed} cycle={cycle} origin={origin} action={installed.action} reward={reward:.3f}", flush=True)
    memory.flush()
    return rows, detailed, llm.audit if llm else []


def summarize(rows, seeds, provider, cycles, hashes, elapsed):
    conditions = list(dict.fromkeys(r["condition"] for r in rows))
    groups, per_seed = {}, {}
    for condition in conditions:
        selected = [r for r in rows if r["condition"] == condition]
        per_seed[condition] = {}
        for seed in seeds:
            sr = [r for r in selected if r["seed"] == seed]
            per_seed[condition][str(seed)] = {k: mean(r[k] for r in sr) for k in ("latency_ms", "throughput_kbps", "loss_pct", "reward")}
        groups[condition] = {"label": LABELS[condition], "windows": len(selected),
                             **{k: mean(r[k] for r in selected) for k in ("latency_ms", "throughput_kbps", "loss_pct", "reward", "control_elapsed_ms")},
                             "pooled_loss_pct": 100 * sum(r["dropped_mbit"] for r in selected) / sum(r["offered_mbit"] for r in selected),
                             "safety_vetoes": sum(not r["safety_allowed"] for r in selected),
                             "fallback_windows": sum(r["decision_origin"] in {"fallback_no_op","fallback_heuristic","deadline_fallback","provider_fallback","validation_fallback"} for r in selected),
                             "decision_origins":dict(Counter(r['decision_origin'] for r in selected)),
                             "api_decision_windows": sum(r["decision_origin"] == "api" for r in selected),
                             "api_reflection_windows": sum(r["reflection_origin"] == "api" for r in selected),
                             "actions": dict(Counter(r["installed_action"] for r in selected))}
    comparisons = {}
    for other in conditions:
        if other == "A0":
            continue
        comparisons[other + "_minus_A0"] = {}
        for k in ("latency_ms", "throughput_kbps", "loss_pct"):
            deltas = [per_seed[other][str(s)][k] - per_seed["A0"][str(s)][k] for s in seeds]
            n = len(deltas)
            critical = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 10: 2.262}.get(n)
            half = critical * stdev(deltas) / math.sqrt(n) if n > 1 and critical else None
            comparisons[other + "_minus_A0"][k] = {"mean_difference": mean(deltas), "ci95": [mean(deltas) - half, mean(deltas) + half] if half is not None else None}
    return {"schema": "selfx.simulation.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "provenance": "simulation", "decision_backend": provider, "seeds": seeds,
            "cycles_per_condition_seed": cycles, "simulated_seconds_per_condition_seed": cycles * INTERVAL,
            "wall_seconds": elapsed, "trace_sha256": hashes, "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "topology": "diamond-4-switch-8-host-logical-paths", "capacity_per_path_mbps": 10,
            "buffer_per_path_mbit": .5, "interval_seconds": INTERVAL,
            "conditions": groups, "seed_means": per_seed, "paired_seed_comparisons": comparisons,
            "limitations": ["Analytical fluid simulation; no packets or physical SDN measurements.",
                            "Offline controller results do not establish LLM effectiveness.",
                            "One workload family and topology; no external dataset calibration.",
                            "State embedding is hand-designed and normalized, not a trained neural representation.",
                            "Reward compares each action against a same-window no-op model counterfactual.",
                            "Mean window loss and pooled traffic-volume loss are different statistics.",
                            "No guarantee that reflection or memory improves results."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["offline", "auto", "gemini", "openrouter"], default="offline")
    parser.add_argument("--model")
    parser.add_argument("--cycles", type=int, default=120)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1729, 1730, 1731, 1732, 1733])
    parser.add_argument("--conditions", nargs="+", choices=list(LABELS), default=list(LABELS))
    parser.add_argument("--out-dir", default=str(config.PROJECT_ROOT / "output" / "experiments" / "adaptive"))
    args = parser.parse_args()
    if args.cycles < 1 or args.cycles > 10000 or len(set(args.seeds)) != len(args.seeds) or "A0" not in args.conditions:
        parser.error("use 1..10000 cycles, unique seeds, and include A0")
    out = local_path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    all_rows, all_details, audits, hashes = [], [], [], {}
    start = time.perf_counter()
    for seed in args.seeds:
        trace = traffic_trace(seed, args.cycles)
        encoded = json.dumps(trace, sort_keys=True).encode()
        hashes[str(seed)] = hashlib.sha256(encoded).hexdigest()
        (out / f"traffic_{seed}.json").write_bytes(encoded)
        for condition in args.conditions:
            rows, details, audit = run_condition(condition, trace, seed, args.provider, out, args.model)
            all_rows.extend(rows)
            all_details.extend(details)
            audits.extend(audit)
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    (out / "trace.jsonl").write_text("\n".join(json.dumps(r, allow_nan=False) for r in all_details) + "\n", encoding="utf-8")
    summary = summarize(all_rows, args.seeds, args.provider, args.cycles, hashes, time.perf_counter() - start)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (out / "provider_calls.json").write_text(json.dumps(audits, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "windows": len(all_rows), "conditions": summary["conditions"]}, indent=2))


if __name__ == "__main__":
    main()
