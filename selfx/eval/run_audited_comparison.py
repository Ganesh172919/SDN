"""Reproduce the audited SELF-X comparison on a shared fluid datapath."""
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
from statistics import mean
import sys

import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "selfx") not in sys.path:
    sys.path.insert(0, str(ROOT / "selfx"))
from agent.self_improvement.common import artifact_identity
from agent.self_improvement.policy import MODEL_ID, REVISION, ensure_model
from eval.audited_models import LocalModels, OBJECTIVES, episodic_memory, snapshot
from eval.neural_baselines import ACTIONS, NeuralController, action_for, observation
from eval.pipeline_model import (
    C_ALTERNATE_MBPS, GOVERNANCE_WINDOWS, NO_OP, SLOTS_PER_WINDOW, TAU_SEC, WINDOW_SEC,
    PipelineDPP, TabularQController, Telemetry, TwoPathDatapath, aggregate_window,
    demand_series, least_loaded_controller, threshold_controller, window_reward,
)
from eval.run_pipeline_study import DEFAULT_V, DEFAULT_WEIGHTS
import safety
from traffic_gen import generate_schedule

OUTPUT = ROOT / "paper" / "comparison"
ADAPTER = ROOT / "selfx" / "output" / "pipeline_study" / "adapter"
PROFILES = ("steady_bursty", "flash_crowd", "volatile_dpp")
CONFIGS = {
    "S0": "Static",
    "S1": "Base LM",
    "S2": "Base LM + critique",
    "S3": "LoRA policy",
    "S4": "Agentic at 5 s",
    "S5": "SELF-X Agentic",
    "threshold": "Capacity threshold",
    "least_loaded": "Least loaded",
    "tabular_q": "Tabular Q",
    "dqn": "DQN",
    "marl": "Two-agent IQL",
    "dpp": "DPP only",
    "no_lora": "Agentic without LoRA",
    "no_governor": "Agentic without governor",
}
DPP_ARMS = {"S4", "S5", "dpp", "no_lora", "no_governor"}
GOVERNOR_ARMS = {"S4", "S5", "no_lora"}
LORA_ARMS = {"S3", "S4", "S5", "no_governor"}
NEURAL_ARMS = ("dqn", "marl")
DIRECT_ARMS = {"S1", "S2", "S3"}
MODEL_PASS_SLOTS = 4
CRITIQUE_SLOTS = 2 * MODEL_PASS_SLOTS
# The five specialist prompts share one batch. The orchestrator runs after it.
GOVERNANCE_SLOTS = 2 * MODEL_PASS_SLOTS
LORA_PRIOR = 0.20


def safe_action(proposal, elephant):
    # This model has one steerable aggregate and no unrelated alternate traffic.
    # A flow already on the alternate path must not be counted twice.
    result = safety.check(safety.SafetyContext(
        action=proposal.kind,
        target_flow_rate_kbps=elephant * 1000,
        proposed_rate_limit_kbps=proposal.rate_limit_kbps,
        target_link_capacity_kbps=C_ALTERNATE_MBPS * 1000,
    ))
    return (proposal, False) if result.allowed else (NO_OP, True)


def optimise(controller, mice, elephant, queues, policy_v, weights, prior):
    feasible = tuple(
        kind for index, kind in enumerate(ACTIONS)
        if not safe_action(action_for(index, mice, elephant, "dpp"), elephant)[1]
    )
    baseline, _, scores = controller.decide(queues, mice, elephant, policy_v, weights, feasible)
    if prior not in feasible:
        return baseline, False
    preferred = min(feasible, key=lambda kind: scores[kind] + LORA_PRIOR * (kind != prior))
    return action_for(ACTIONS.index(preferred), mice, elephant, "dpp"), preferred != baseline.kind


def window_observation(index, mice, elephant, queues, last):
    return Telemetry(
        index, mice, elephant, *queues, last.latency_ms if last else 2.0,
        last.loss_pct if last else 0.0, last.throughput_mbps if last else 0.0,
        0.0, 0.0,
    )


def run_episode(name, series, model=None, neural=None, *, seed=0, training_offset=None):
    """Training and evaluation use the same executed actions and safety arbiter."""
    training = training_offset is not None
    datapath = TwoPathDatapath()
    counts = Counter()
    action_trace = sha256()
    ballots = Counter()
    memory = episodic_memory()
    dpp = PipelineDPP() if name in DPP_ARMS else None
    tabular = TabularQController(seed) if name == "tabular_q" else None
    installed = proposed = NO_OP
    held = 0
    ready = -1
    prior = None
    pending = None
    policy_v = DEFAULT_V
    weights = DEFAULT_WEIGHTS.copy()
    windows = []
    last = None

    for tick, (mice, elephant) in enumerate(series):
        window, slot = divmod(tick, SLOTS_PER_WINDOW)
        queues = datapath.queue
        if slot == 0:
            start = tick
            installs = vetoes = 0
            outcomes = []
            first_obs = window_observation(window, mice, elephant, queues, last)
            if name in GOVERNOR_ARMS and window % GOVERNANCE_WINDOWS == 0:
                merged, votes = model.govern(snapshot(mice, elephant, queues))
                counts["specialist_ballots"] += len(votes)
                counts["governance_calls"] += 1
                ballots.update([f"merged_{merged}"])
                ballots.update(f"{role}_{vote}" for role, vote in votes.items())
                pending = tick + GOVERNANCE_SLOTS, merged
            if name in DIRECT_ARMS or name in LORA_ARMS:
                adapted = name in LORA_ARMS
                held = model.action(mice, elephant, adapted)
                counts["lora_proposals" if adapted else "base_proposals"] += 1
                ready = tick + MODEL_PASS_SLOTS
                if name == "S2":
                    revised = model.critique(snapshot(mice, elephant, queues), held, memory)
                    counts["critique_calls"] += 1
                    counts["critique_revisions"] += int(revised != held)
                    counts["nonempty_memory_prompts"] += int(bool(memory))
                    held = revised
                    ready = tick + CRITIQUE_SLOTS
            if name == "threshold":
                proposed = threshold_controller(first_obs)
            if name == "least_loaded":
                proposed = least_loaded_controller(first_obs)
            if tabular:
                proposed = tabular.act(first_obs)

        if pending and tick == pending[0]:
            delta_v, deltas = OBJECTIVES[pending[1]]
            if delta_v or deltas:
                before = policy_v, weights
                policy_v = min(32, max(0.5, policy_v + delta_v))
                updated = {key: max(0.0, value + deltas.get(key, 0.0))
                           for key, value in weights.items()}
                total = sum(updated.values())
                weights = {key: value / total for key, value in updated.items()}
                counts["policy_changes"] += int((policy_v, weights) != before)
            pending = None
        if tick == ready:
            if name in DIRECT_ARMS:
                proposed = action_for(held, first_obs.mice_mbps, first_obs.elephant_mbps, "local_lm")
            elif name in LORA_ARMS:
                prior = ACTIONS[held]

        if dpp is not None and (name != "S4" or slot == 0):
            proposed, changed = optimise(dpp, mice, elephant, queues, policy_v, weights, prior)
            counts["dpp_decisions"] += 1
            counts["lora_prior_changed_decision"] += int(changed)
        if neural is not None:
            state = observation(mice, elephant, queues, installed)
            step = training_offset + tick if training else 0
            epsilon = max(0.05, 1.0 - step / 18_000) if training else 0.0
            index, choices = neural.choose(state, epsilon)
            proposed = action_for(index, mice, elephant, name)
            counts[f"neural_choice_{ACTIONS[index]}"] += 1

        effective, veto = safe_action(proposed, elephant)
        changed_rule = effective.key() != installed.key()
        installs += int(changed_rule)
        vetoes += int(veto)
        installed = effective
        outcome = datapath.step(mice, elephant, effective)
        outcomes.append(outcome)
        counts[f"effective_{effective.kind}"] += 1
        if not training:
            action_trace.update(f"{effective.kind}:{effective.rate_limit_kbps}\n".encode())

        if training:
            terminal = tick + 1 == len(series)
            following = (mice, elephant) if terminal else series[tick + 1]
            lost = outcome.overflow_mbit + outcome.meter_mbit
            reward = window_reward(
                outcome.served_mbit / TAU_SEC, outcome.delay_ms,
                100 * lost / max(outcome.offered_mbit, 1e-12),
                int(changed_rule) * SLOTS_PER_WINDOW,
            )
            neural.observe(state, choices, reward, observation(*following, datapath.queue, installed),
                           terminal, step)

        if slot + 1 == SLOTS_PER_WINDOW:
            last = aggregate_window(window, outcomes, installed, installs, 0.0, math.inf, 0.0)
            if name == "S2":
                memory.append((ACTIONS.index(installed.kind), last.reward))
            if tabular and tick + 1 < len(series):
                tabular.learn(last.reward, window_observation(window + 1, *series[tick + 1],
                                                              datapath.queue, last))
            if not training:
                row = asdict(last)
                row.update(
                    end_sec=(tick + 1) * TAU_SEC,
                    vetoes=vetoes,
                    delay_over_50_pct=100 * mean(o.delay_ms > 50 for o in outcomes),
                    offered_mbps=mean(m + e for m, e in series[start:tick + 1]),
                )
                windows.append(row)

    return {
        "windows": windows, "counts": dict(counts), "ballots": dict(ballots),
        "conservation_error_mbit": datapath.conservation_error_mbit,
        "effective_actions_sha256": action_trace.hexdigest() if not training else None,
    }


def trace(seed, duration):
    schedule = generate_schedule(PROFILES[seed % len(PROFILES)], duration, seed)
    series = demand_series(schedule, int(duration / WINDOW_SEC))
    return schedule, series, sha256(json.dumps(series, separators=(",", ":")).encode()).hexdigest()


def train_baselines(train_episodes, duration):
    training = [(1000 + i, trace(1000 + i, duration)[1]) for i in range(train_episodes)]
    baselines = {}
    evidence = {}
    for name in NEURAL_ARMS:
        controller = NeuralController(name, 3928)
        for i, (seed, series) in enumerate(training):
            run_episode(name, series, neural=controller, seed=seed, training_offset=i * len(series))
        baselines[name] = controller
        evidence[name] = [agent.evidence() for agent in controller.agents]
        for record in evidence[name]:
            if record["initial_sha256"] == record["trained_sha256"]:
                raise RuntimeError(f"{name} did not update its parameters")
        print(f"Trained {name}: {[a.updates for a in controller.agents]} optimizer steps", flush=True)
    return baselines, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--smoke", action="store_true", help="3 short seeds and abbreviated training")
    parser.add_argument("--adapter", type=Path, default=ADAPTER)
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    train_episodes, train_duration, test_episodes, test_duration = (
        (3, 15, 3, 10) if args.smoke else (18, 120, 12, 180)
    )
    baselines, evidence = train_baselines(train_episodes, train_duration)
    model = LocalModels(args.adapter)
    runs = []
    for seed in range(2100, 2100 + test_episodes):
        schedule, series, fingerprint = trace(seed, test_duration)
        for name in CONFIGS:
            result = run_episode(name, series, model, baselines.get(name), seed=seed)
            runs.append({
                "configuration": name, "seed": seed, "profile": schedule["profile"],
                "traffic_sha256": fingerprint, **result,
            })
        print(f"Evaluated seed {seed} ({schedule['profile']})", flush=True)
    for name in NEURAL_ARMS:
        if evidence[name] != [agent.evidence() for agent in baselines[name].agents]:
            raise AssertionError(f"{name} updated or explored on test traces")
    manifest = {
        "schema": "selfx.audited-comparison.v1", "smoke": args.smoke,
        "configs": CONFIGS, "train_seeds": list(range(1000, 1000 + train_episodes)),
        "test_seeds": list(range(2100, 2100 + test_episodes)),
        "training_sec_per_seed": train_duration, "test_sec_per_seed": test_duration,
        "window_sec": WINDOW_SEC, "slot_sec": TAU_SEC, "torch_version": torch.__version__,
        "baseline_training": evidence, "model": MODEL_ID, "model_revision": REVISION,
        "model_weights_sha256": json.loads(
            (ensure_model() / "download_manifest.json").read_text(encoding="utf-8")
        )["files"]["model.safetensors"]["sha256"],
        "adapter_identity": artifact_identity(args.adapter), "lora_prior": LORA_PRIOR,
        "forward_batches": dict(model.forward_batches), "fixed_model_pass_sec": MODEL_PASS_SLOTS * TAU_SEC,
        "runs": runs,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "runs.json"
    destination.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {destination}", flush=True)
    if not args.smoke:
        from eval.plot_audited_comparison import build

        build(args.output)


if __name__ == "__main__":
    main()

