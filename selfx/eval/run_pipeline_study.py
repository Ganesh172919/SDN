"""
SELF-X incremental-pipeline study (Tables II and V of the paper).

Runs six controller configurations over one shared, frozen traffic trace so that
every stage differs from its predecessor by exactly one mechanism:

    S0  static                 fixed shortest-path rule, never changed
    S1  static LLM agent       one OpenRouter free model call per control window,
                               zero-shot, no memory, no critique
    S2  + self-critique        S1 plus an episodic replay buffer and a second LLM
                               pass that criticises the agent's own proposal
                               against the realised reward of the previous window
    S3  + LoRA fine-tuning     S2 plus a LoRA adapter (r=8, alpha=16, q_proj/v_proj)
                               over a pinned SmolLM2-135M-Instruct policy head;
                               the action token comes from adapter inference
    S4  + multi-agent governor 1 orchestrator + 5 specialists (one panel LLM call
                               per 30 s governance epoch) that set (V, w, mask)
    S5  full pipeline          S4 plus the Lyapunov drift-plus-penalty fast loop
                               deciding every tau = 100 ms

and four non-LLM comparison controllers for Table V: capacity-aware threshold,
greedy least-loaded, and a tabular Q-learning agent on the same reward.

Every proposed action passes the independent deterministic safety arbiter in
``safety.py`` before it reaches the datapath; vetoes are counted, not hidden.

Control-plane latency is *measured*, not assumed, and it is charged to the
datapath: an action that takes L seconds to produce only takes effect after
ceil(L / tau) slots of the window it was computed for. This is what separates
the LLM stages from the 100 ms DPP loop, and it is the central quantitative
claim of the paper.

Usage
-----
    python -m eval.run_pipeline_study --mode live     # needs OPENROUTER_API_KEY
    python -m eval.run_pipeline_study --mode replay   # no credential required
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SELFX_ROOT = PROJECT_ROOT / "selfx"
for path in (str(PROJECT_ROOT), str(SELFX_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import config  # noqa: E402
import safety  # noqa: E402
from agent.llm_decider import (  # noqa: E402
    DeciderError,
    FreeModelDecider,
    validate_action,
    validate_critique,
    validate_policy,
)
from eval.pipeline_model import (  # noqa: E402
    BUFFER_MBIT,
    C_ALTERNATE_MBPS,
    C_PRIMARY_MBPS,
    GOVERNANCE_WINDOWS,
    SLOTS_PER_WINDOW,
    TAU_SEC,
    WINDOW_SEC,
    Action,
    NO_OP,
    PipelineDPP,
    TabularQController,
    Telemetry,
    TwoPathDatapath,
    WindowResult,
    aggregate_window,
    backlog_bound_mbit,
    demand_series,
    least_loaded_controller,
    oracle_floor,
    static_controller,
    threshold_controller,
    window_reward,
)
from traffic_gen import generate_schedule  # noqa: E402

OUTPUT_DIR = SELFX_ROOT / "output" / "pipeline_study"
TRACE_PATH = OUTPUT_DIR / "llm_trace.jsonl"

STAGES = ("S0", "S1", "S2", "S3", "S4", "S5")
STAGE_LABEL = {
    "S0": "S0 Static forwarding (non-learning floor)",
    "S1": "S1 Static LLM agent (zero-shot, no memory)",
    "S2": "S2 + self-critique and episodic replay",
    "S3": "S3 + LoRA-adapted policy head (r=8, alpha=16)",
    "S4": "S4 + six-agent governance (V, w, action mask)",
    "S5": "S5 + Lyapunov DPP fast loop (full pipeline)",
}
BASELINES = ("threshold", "least_loaded", "tabular_q")
BASELINE_LABEL = {
    "threshold": "Capacity-aware threshold heuristic",
    "least_loaded": "Greedy least-loaded (ECMP-style)",
    "tabular_q": "Tabular Q-learning (same reward)",
}

DEFAULT_V = 8.0
DEFAULT_WEIGHTS = {
    "latency": 0.25,
    "throughput": 0.25,
    "loss": 0.25,
    "energy": 0.15,
    "resource": 0.10,
}
FULL_MASK = ("no_op", "reroute", "rate_limit")


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

ACTION_SYSTEM = (
    "You are the slow control loop of an OpenFlow 1.3 software-defined network. "
    "Two parallel paths connect the ingress and egress switch. The primary path has "
    f"{C_PRIMARY_MBPS:.0f} Mbps capacity and {2.0:.0f} ms propagation; the alternate path has "
    f"{C_ALTERNATE_MBPS:.0f} Mbps capacity and 12 ms propagation. Each path has a "
    f"{BUFFER_MBIT} Mbit buffer; traffic above the buffer is tail-dropped. "
    "Latency-sensitive mice traffic always uses the primary path. You control only the "
    "elephant aggregate.\n"
    "Choose exactly one action:\n"
    "  no_op       keep the elephant aggregate on the primary path\n"
    "  reroute     move the elephant aggregate to the alternate path (adds 10 ms propagation)\n"
    "  rate_limit  install a meter on the elephant aggregate; you must give rate_limit_kbps\n"
    "A meter below 512 kbps, or one discarding more than 20% of the measured flow rate, is "
    "vetoed by an independent safety arbiter and becomes no_op.\n"
    'Reply with exactly one JSON object: {"action": "...", "rate_limit_kbps": <int or null>, '
    '"reason": "<= 20 words"}. No prose outside the object.'
)

CRITIQUE_SYSTEM = (
    "You are reviewing your own previous software-defined-network control decision. "
    "You are given the realised reward of the last window and similar past episodes from "
    "an episodic replay buffer. Decide whether to keep the proposal or revise it.\n"
    'Reply with exactly one JSON object: {"verdict": "keep" | "revise", '
    '"revised_action": {"action": "...", "rate_limit_kbps": <int or null>, "reason": "..."}, '
    '"lesson": "<= 20 words"}. Use null for revised_action when the verdict is keep.'
)

PANEL_SYSTEM = (
    "You are the orchestrator of a six-agent software-defined-network governance board. "
    "Five specialists advise you: flow_sizing, routing, anomaly, security and slicing. "
    "Given one window of telemetry you must return every specialist's opinion and then your "
    "merged policy update for the fast-timescale Lyapunov controller.\n"
    "d_v in [-4, 4] shifts the drift-plus-penalty weight V: a larger V prioritises operating "
    "cost over queue backlog; a smaller V prioritises short queues.\n"
    "weight_deltas entries are in [-0.15, 0.15] over the keys latency, throughput, loss, "
    "energy, resource.\n"
    "enable_actions is the subset of [no_op, reroute, rate_limit] the fast loop may use.\n"
    'Reply with exactly one JSON object: {"specialists": {"flow_sizing": {"note": "..."}, '
    '"routing": {...}, "anomaly": {...}, "security": {...}, "slicing": {...}}, "d_v": <float>, '
    '"weight_deltas": {...}, "enable_actions": [...], "reason": "<= 20 words"}.'
)


def telemetry_prompt(raw: Telemetry) -> str:
    """Render one window of telemetry at the declared monitoring resolution.

    Only the four decision-relevant statistics are shown. Derived quantities
    (goodput, utilisation) are functions of these and would only inflate the
    prompt; the congestion regime is the poller's own flag.
    """
    t = raw.quantised()
    backlog = t.queue_primary_mbit + t.queue_alternate_mbit
    if backlog >= 1.5 * BUFFER_MBIT:
        regime = "saturated"
    elif backlog >= 0.5 * BUFFER_MBIT:
        regime = "congested"
    else:
        regime = "nominal"
    return (
        f"Telemetry for the last {WINDOW_SEC:.0f} s poll:\n"
        f"  mice demand on primary  = {t.mice_mbps:.1f} Mbps\n"
        f"  elephant aggregate      = {t.elephant_mbps:.1f} Mbps\n"
        f"  primary queue backlog   = {t.queue_primary_mbit:.1f} of {BUFFER_MBIT:.1f} Mbit\n"
        f"  alternate queue backlog = {t.queue_alternate_mbit:.1f} of {BUFFER_MBIT:.1f} Mbit\n"
        f"  congestion regime       = {regime}\n"
        "Choose the action for the next window."
    )


# --------------------------------------------------------------------------- #
# Episodic replay buffer (S2 onwards)
# --------------------------------------------------------------------------- #

class ReplayBuffer:
    """Bounded store of (quantised state, action, realised reward) episodes."""

    def __init__(self, capacity: int = config.MEMORY_MAX_ENTRIES) -> None:
        self.capacity = capacity
        self.episodes: List[Dict[str, Any]] = []

    def add(self, telemetry: Telemetry, action: Action, reward: float) -> None:
        q = telemetry.quantised()
        self.episodes.append({
            "observation": {
                "capacity_mbps": C_PRIMARY_MBPS,
                "primary_background_mbps": round(telemetry.mice_mbps, 3),
                "alternate_background_mbps": round(
                    telemetry.util_alternate_pct * C_ALTERNATE_MBPS / 100.0, 3),
                "elephant_mbps": round(telemetry.elephant_mbps, 3),
                "queue_primary_mbit": round(telemetry.queue_primary_mbit, 3),
                "queue_alternate_mbit": round(telemetry.queue_alternate_mbit, 3),
            },
            "digest": telemetry.digest(),
            "mice": q.mice_mbps,
            "elephant": q.elephant_mbps,
            "q_primary": q.queue_primary_mbit,
            "q_alternate": q.queue_alternate_mbit,
            "action": action.kind,
            "rate_limit_kbps": action.rate_limit_kbps,
            "reward": round(reward, 1),
        })
        if len(self.episodes) > self.capacity:
            self.episodes.pop(0)

    def similar(self, telemetry: Telemetry, k: int = 4) -> List[Dict[str, Any]]:
        target = telemetry.digest()

        def distance(ep: Dict[str, Any]) -> float:
            return sum(abs(a - b) for a, b in zip(ep["digest"], target))

        return sorted(self.episodes, key=distance)[:k]

    def render(self, telemetry: Telemetry) -> str:
        """Compact summary of what each action has actually been worth so far.

        Aggregating the buffer rather than listing raw episodes keeps the critique
        prompt short, keeps the set of distinct prompts finite and replayable, and
        gives the model the statistic it actually needs.
        """
        if not self.episodes:
            return "Replay buffer is empty; no action has been scored yet."
        lines = ["Mean realised reward per action over the replay buffer:"]
        for kind in ("no_op", "reroute", "rate_limit"):
            rows = [e for e in self.episodes if e["action"] == kind]
            if rows:
                mean = sum(e["reward"] for e in rows) / len(rows)
                lines.append(f"  {kind}: {mean:+.1f} mean reward over {len(rows)} episodes")
            else:
                lines.append(f"  {kind}: never tried")
        return "\n".join(lines)

    def training_rows(self) -> List[Dict[str, Any]]:
        return list(self.episodes)


# --------------------------------------------------------------------------- #
# Stage controllers
# --------------------------------------------------------------------------- #

class LoRAHead:
    """Lazy wrapper over the pinned SmolLM2-135M policy with its LoRA adapter."""

    _shared: Optional["LoRAHead"] = None

    def __init__(self, adapter_dir: Path) -> None:
        from agent.self_improvement.policy import LoRAPolicy

        self.adapter_dir = adapter_dir
        started = time.perf_counter()
        self.policy = LoRAPolicy(candidate=str(adapter_dir))
        self.load_seconds = round(time.perf_counter() - started, 2)
        self.calls = 0
        self.total_ms = 0.0

    @classmethod
    def shared(cls, adapter_dir: Path) -> "LoRAHead":
        if cls._shared is None:
            cls._shared = cls(adapter_dir)
        return cls._shared

    def act(self, telemetry: Telemetry) -> Tuple[Action, float]:
        obs = {
            "capacity_mbps": C_PRIMARY_MBPS,
            "primary_background_mbps": round(telemetry.mice_mbps, 3),
            "alternate_background_mbps": round(
                telemetry.util_alternate_pct * C_ALTERNATE_MBPS / 100.0, 3
            ),
            "elephant_mbps": round(telemetry.elephant_mbps, 3),
        }
        started = time.perf_counter()
        prediction = self.policy.predict([obs], "candidate")[0]
        elapsed_ms = 1000 * (time.perf_counter() - started)
        self.calls += 1
        self.total_ms += elapsed_ms
        kind = prediction["action"]
        rate = None
        if kind == "rate_limit":
            headroom = max(0.512, 0.90 * C_PRIMARY_MBPS - telemetry.mice_mbps)
            rate = int(min(headroom, telemetry.elephant_mbps * 0.85) * 1000)
        return Action(kind, rate, "lora", "LoRA action token"), elapsed_ms


def apply_safety(proposal: Action, telemetry: Telemetry) -> Tuple[Action, Optional[str]]:
    """Independent arbiter. Returns the installed action and a veto reason if any."""
    result = safety.check(safety.SafetyContext(
        action=proposal.kind,
        target_flow_rate_kbps=telemetry.elephant_mbps * 1000.0,
        proposed_rate_limit_kbps=proposal.rate_limit_kbps,
        target_link_capacity_kbps=C_ALTERNATE_MBPS * 1000.0,
        target_link_current_kbps=telemetry.util_alternate_pct * C_ALTERNATE_MBPS * 10.0,
    ))
    if result.allowed:
        return proposal, None
    return Action("no_op", None, "safety_veto", result.reason), result.reason


# --------------------------------------------------------------------------- #
# The run loop
# --------------------------------------------------------------------------- #

def run_configuration(
    name: str,
    seed: int,
    num_windows: int,
    decider: Optional[FreeModelDecider],
    lora_head: Optional[LoRAHead],
    profile: str = "steady_bursty",
) -> Dict[str, Any]:
    """Execute one controller configuration over one seed and return its record."""
    duration = int(num_windows * WINDOW_SEC)
    schedule = generate_schedule(profile, duration, seed)
    series = demand_series(schedule, num_windows)
    datapath = TwoPathDatapath()

    policy_v = DEFAULT_V
    weights = dict(DEFAULT_WEIGHTS)
    action_mask: Tuple[str, ...] = FULL_MASK
    # S4 and S5 run the SAME optimiser; they differ only in how often it runs
    # (once per control window vs once per fast slot). That is the comparison
    # the paper needs, so no other mechanism may differ between them.
    dpp = PipelineDPP() if name in ("S4", "S5") else None
    bound = backlog_bound_mbit(policy_v)

    replay = ReplayBuffer()
    q_learner = TabularQController(seed) if name == "tabular_q" else None

    installed = NO_OP
    previous_action = NO_OP
    epoch_action = NO_OP
    telemetry = Telemetry(
        window=0, mice_mbps=series[0][0], elephant_mbps=series[0][1],
        queue_primary_mbit=0.0, queue_alternate_mbit=0.0,
        latency_ms=2.0, loss_pct=0.0, throughput_mbps=0.0,
        util_primary_pct=0.0, util_alternate_pct=0.0,
    )

    windows: List[WindowResult] = []
    oracle_mbit = 0.0
    safety_vetoes = 0
    llm_calls_before = len(decider.records) if decider else 0
    governance_events: List[Dict[str, Any]] = []
    slot_decision_times_us: List[float] = []

    for w in range(num_windows):
        window_slots = series[w * SLOTS_PER_WINDOW:(w + 1) * SLOTS_PER_WINDOW]
        if not window_slots:
            break

        # ---- governance epoch (S4, S5) -------------------------------------
        if name in ("S4", "S5") and decider is not None and w % GOVERNANCE_WINDOWS == 0:
            update = governance_update(decider, telemetry)
            policy_v = max(0.5, min(32.0, policy_v + update["d_v"]))
            for key, delta in update["weight_deltas"].items():
                weights[key] = max(0.0, min(1.0, weights.get(key, 0.2) + delta))
            total = sum(weights.values()) or 1.0
            weights = {k: v / total for k, v in weights.items()}
            # The mask is advisory and scoped to the coming epoch only: it resets
            # to the full set first, so one bad epoch cannot latch the datapath
            # into no_op for the rest of the run. A mask leaving fewer than two
            # options, or omitting the always-safe no_op, is rejected.
            action_mask = FULL_MASK
            proposed = tuple(dict.fromkeys(update["enable_actions"]))
            if len(proposed) >= 2 and "no_op" in proposed:
                action_mask = proposed
            else:
                update["reason"] = (update.get("reason", "")
                                    + " [mask rejected: fewer than two admissible actions]")
            bound = backlog_bound_mbit(policy_v)
            governance_events.append({
                "window": w, "policy_v": round(policy_v, 3),
                "weights": {k: round(v, 4) for k, v in weights.items()},
                "mask": list(action_mask), "reason": update["reason"],
            })

        # ---- slow-loop action proposal -------------------------------------
        control_ms = 0.0
        proposal = NO_OP

        if name == "S0":
            proposal = static_controller(telemetry)
        elif name == "threshold":
            proposal = threshold_controller(telemetry)
        elif name == "least_loaded":
            proposal = least_loaded_controller(telemetry)
        elif name == "tabular_q":
            assert q_learner is not None
            proposal = q_learner.act(telemetry)
        elif name in ("S1", "S2"):
            # The remote model runs on the governance epoch, not every window: at a
            # measured ~1 s per request and a 50-request daily free-tier ceiling it
            # cannot be polled at window rate. Between epochs the installed rule stands.
            if w % GOVERNANCE_WINDOWS == 0:
                proposal, control_ms = llm_action(decider, telemetry)
                if name == "S2":
                    revised, critique_ms = self_critique(
                        decider, telemetry, proposal, replay,
                        windows[-1].reward if windows else 0.0)
                    control_ms += critique_ms
                    proposal = revised
                epoch_action = proposal
            else:
                proposal = epoch_action
                control_ms = 0.0
        elif name in ("S3", "S4", "S5"):
            assert lora_head is not None
            proposal, control_ms = lora_head.act(telemetry)
            if name == "S4" and dpp is not None:
                # Window-rate drift-plus-penalty over the governor's admissible
                # set, evaluated on the window's opening backlog. The LoRA pick
                # stands unless the objective strictly prefers another action.
                candidate, decision_us, _ = dpp.decide(
                    queue=datapath.queue, mice_mbps=telemetry.mice_mbps,
                    elephant_mbps=telemetry.elephant_mbps, policy_v=policy_v,
                    weights=weights, action_mask=action_mask or FULL_MASK)
                slot_decision_times_us.append(decision_us)
                control_ms += decision_us / 1000.0
                if candidate.kind != proposal.kind:
                    proposal = candidate

        proposal, veto = apply_safety(proposal, telemetry)
        if veto:
            safety_vetoes += 1

        # ---- actuation lag: a slow proposal only lands part-way through -----
        lag_slots = 0 if name == "S0" else min(SLOTS_PER_WINDOW,
                                               int(-(-control_ms / 1000.0 // TAU_SEC)))
        installs = 0 if proposal.key() == installed.key() else 1

        # ---- datapath ------------------------------------------------------
        oracle_mbit += sum(oracle_floor(m, e) for m, e in window_slots)
        outcomes = []
        for slot_idx, (mice, elephant) in enumerate(window_slots):
            if name == "S5" and dpp is not None and slot_idx >= lag_slots:
                candidate, decision_us, _ = dpp.decide(
                    queue=datapath.queue, mice_mbps=mice, elephant_mbps=elephant,
                    policy_v=policy_v, weights=weights,
                    action_mask=action_mask or FULL_MASK)
                slot_decision_times_us.append(decision_us)
                effective, slot_veto = apply_safety(candidate, telemetry)
                if slot_veto:
                    safety_vetoes += 1
            elif slot_idx < lag_slots:
                effective = previous_action     # old rule still in the TCAM
            else:
                effective = proposal
            outcomes.append(datapath.step(mice, elephant, effective))

        result = aggregate_window(
            index=w, slots=outcomes, action=proposal, installs=installs,
            control_latency_ms=control_ms, bound_mbit=bound,
            slot_decision_us=(statistics.mean(slot_decision_times_us[-SLOTS_PER_WINDOW:])
                              if slot_decision_times_us else 0.0),
        )
        windows.append(result)

        previous_action = proposal
        installed = proposal

        next_telemetry = Telemetry(
            window=w + 1,
            mice_mbps=statistics.mean(m for m, _ in window_slots),
            elephant_mbps=statistics.mean(e for _, e in window_slots),
            queue_primary_mbit=datapath.queue[0],
            queue_alternate_mbit=datapath.queue[1],
            latency_ms=result.latency_ms,
            loss_pct=result.loss_pct,
            throughput_mbps=result.throughput_mbps,
            util_primary_pct=100.0 * min(2.0, (statistics.mean(m for m, _ in window_slots)
                                               + (0.0 if proposal.kind == "reroute"
                                                  else statistics.mean(e for _, e in window_slots)))
                                         / C_PRIMARY_MBPS),
            util_alternate_pct=100.0 * min(2.0, (statistics.mean(e for _, e in window_slots)
                                                 if proposal.kind == "reroute" else 0.0)
                                           / C_ALTERNATE_MBPS),
        )

        if q_learner is not None:
            q_learner.learn(result.reward, next_telemetry)
        if name in ("S2", "S3", "S4", "S5"):
            replay.add(telemetry, proposal, result.reward)

        telemetry = next_telemetry

    return summarise_run(
        name=name, seed=seed, windows=windows, schedule=schedule, oracle_mbit=oracle_mbit,
        safety_vetoes=safety_vetoes,
        llm_calls=(len(decider.records) - llm_calls_before) if decider else 0,
        governance_events=governance_events,
        slot_decision_times_us=slot_decision_times_us,
        conservation_error=datapath.conservation_error_mbit,
        replay_rows=replay.training_rows(),
        policy_v=policy_v, weights=weights, mask=action_mask,
    )


def llm_action(decider: Optional[FreeModelDecider], telemetry: Telemetry) -> Tuple[Action, float]:
    """One zero-shot decision from an OpenRouter free model."""
    if decider is None:
        return NO_OP, 0.0
    messages = [
        {"role": "system", "content": ACTION_SYSTEM},
        {"role": "user", "content": telemetry_prompt(telemetry)},
    ]
    record = decider.decide(
        role="action", messages=messages, validate=validate_action,
        fallback={"action": "no_op", "rate_limit_kbps": None,
                  "reason": "declared local fallback: no usable model reply"},
    )
    parsed = record.parsed or {}
    origin = "llm" if record.status != "fallback" else "fallback"
    return (
        Action(parsed.get("action", "no_op"), parsed.get("rate_limit_kbps"), origin,
               parsed.get("reason", "")),
        record.elapsed_ms,
    )


def self_critique(decider: Optional[FreeModelDecider], telemetry: Telemetry,
                  proposal: Action, replay: ReplayBuffer,
                  last_reward: float) -> Tuple[Action, float]:
    """Second LLM pass that reviews the agent's own proposal against the replay buffer."""
    if decider is None:
        return proposal, 0.0
    user = (
        telemetry_prompt(telemetry)
        + f"\n\nYour proposal: {proposal.kind}"
        + (f" at {proposal.rate_limit_kbps} kbps" if proposal.rate_limit_kbps else "")
        + f"\nReason given: {proposal.reason}"
        + f"\nRealised reward of the previous window: {round(last_reward, 1):+.1f}\n\n"
        + replay.render(telemetry)
    )
    record = decider.decide(
        role="critique",
        messages=[{"role": "system", "content": CRITIQUE_SYSTEM},
                  {"role": "user", "content": user}],
        validate=validate_critique,
        fallback={"verdict": "keep", "revised_action": None,
                  "lesson": "declared local fallback: proposal kept"},
    )
    parsed = record.parsed or {}
    if parsed.get("verdict") == "revise" and parsed.get("revised_action"):
        rev = parsed["revised_action"]
        return (
            Action(rev["action"], rev.get("rate_limit_kbps"), "llm_critique",
                   parsed.get("lesson", "")),
            record.elapsed_ms,
        )
    return proposal, record.elapsed_ms


def governance_update(decider: FreeModelDecider, telemetry: Telemetry) -> Dict[str, Any]:
    """One panel call returning five specialist opinions plus the merged policy delta."""
    record = decider.decide(
        role="governance",
        messages=[{"role": "system", "content": PANEL_SYSTEM},
                  {"role": "user", "content": telemetry_prompt(telemetry)}],
        validate=validate_policy,
        fallback={"d_v": 0.0, "weight_deltas": {}, "enable_actions": FULL_MASK,
                  "reason": "declared local fallback: policy unchanged"},
    )
    parsed = dict(record.parsed or {})
    parsed.setdefault("d_v", 0.0)
    parsed.setdefault("weight_deltas", {})
    parsed.setdefault("enable_actions", FULL_MASK)
    parsed.setdefault("reason", "")
    return parsed


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #

def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def summarise_run(name: str, seed: int, windows: List[WindowResult], schedule: Dict[str, Any],
                  oracle_mbit: float, safety_vetoes: int, llm_calls: int, governance_events: List[Dict[str, Any]],
                  slot_decision_times_us: List[float], conservation_error: float,
                  replay_rows: List[Dict[str, Any]], policy_v: float,
                  weights: Dict[str, float], mask: Sequence[str]) -> Dict[str, Any]:
    latencies = [w.latency_ms for w in windows]
    rewards = [w.reward for w in windows]
    offered = sum(w.offered_mbit for w in windows)
    served = sum(w.served_mbit for w in windows)
    lost = sum(w.lost_mbit for w in windows)
    duration = len(windows) * WINDOW_SEC

    # Convergence: first window after which the 5-window moving mean reward stays
    # within 10% of the run's final-quarter mean.
    target = statistics.mean(rewards[-max(1, len(rewards) // 4):]) if rewards else 0.0
    convergence = len(windows)
    for i in range(len(rewards) - 5):
        block = rewards[i:i + 5]
        if all(abs(r - target) <= 0.1 * max(0.1, abs(target)) for r in block):
            convergence = i
            break

    return {
        "configuration": name,
        "seed": seed,
        "windows": len(windows),
        "duration_sec": duration,
        "traffic_profile": schedule["profile"],
        "traffic_sha256": hashlib.sha256(
            json.dumps(schedule, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "mean_latency_ms": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "p95_latency_ms": round(percentile(latencies, 0.95), 4),
        "mean_throughput_mbps": round(served / duration, 4) if duration else 0.0,
        "loss_pct": round(100.0 * lost / offered, 4) if offered else 0.0,
        "oracle_floor_loss_pct": round(100.0 * (offered - oracle_mbit) / offered, 4) if offered else 0.0,
        "excess_loss_pct": round(100.0 * (lost - (offered - oracle_mbit)) / offered, 4) if offered else 0.0,
        "mean_reward": round(statistics.mean(rewards), 5) if rewards else 0.0,
        "cumulative_reward": round(sum(rewards), 4),
        "mean_queue_mbit": round(statistics.mean(w.mean_queue_mbit for w in windows), 5),
        "max_queue_mbit": round(max((w.max_queue_mbit for w in windows), default=0.0), 5),
        "bound_violation_pct": round(
            100.0 * sum(w.bound_violations for w in windows) / max(1, len(windows) * SLOTS_PER_WINDOW), 4
        ),
        "mean_control_latency_ms": round(
            statistics.mean(w.control_latency_ms for w in windows), 3) if windows else 0.0,
        "p95_control_latency_ms": round(percentile([w.control_latency_ms for w in windows], 0.95), 3),
        "mean_fast_decision_us": round(statistics.mean(slot_decision_times_us), 3)
        if slot_decision_times_us else 0.0,
        "p99_fast_decision_us": round(percentile(slot_decision_times_us, 0.99), 3)
        if slot_decision_times_us else 0.0,
        "rule_installs": sum(w.installs for w in windows),
        "safety_vetoes": safety_vetoes,
        "llm_decisions": llm_calls,
        "convergence_window": convergence,
        "convergence_sec": convergence * WINDOW_SEC,
        "action_mix": {
            kind: sum(1 for w in windows if w.action_kind == kind)
            for kind in ("no_op", "reroute", "rate_limit")
        },
        "final_policy_v": round(policy_v, 3),
        "final_weights": {k: round(v, 4) for k, v in weights.items()},
        "final_mask": list(mask),
        "governance_events": governance_events,
        "conservation_error_mbit": conservation_error,
        "replay_episodes": len(replay_rows),
        "replay_rows": replay_rows,
        "per_window": [
            {
                "window": w.index,
                "latency_ms": round(w.latency_ms, 4),
                "p95_latency_ms": round(w.p95_latency_ms, 4),
                "throughput_mbps": round(w.throughput_mbps, 4),
                "loss_pct": round(w.loss_pct, 4),
                "reward": round(w.reward, 5),
                "mean_queue_mbit": round(w.mean_queue_mbit, 5),
                "max_queue_mbit": round(w.max_queue_mbit, 5),
                "action": w.action_kind,
                "origin": w.action_origin,
                "control_latency_ms": round(w.control_latency_ms, 3),
            }
            for w in windows
        ],
    }


def aggregate(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mean +/- standard error across seeds for one configuration."""
    def mean(key: str) -> float:
        return round(statistics.mean(r[key] for r in runs), 4)

    def sem(key: str) -> float:
        if len(runs) < 2:
            return 0.0
        return round(statistics.stdev(r[key] for r in runs) / (len(runs) ** 0.5), 4)

    return {
        "configuration": runs[0]["configuration"],
        "label": STAGE_LABEL.get(runs[0]["configuration"],
                                 BASELINE_LABEL.get(runs[0]["configuration"], runs[0]["configuration"])),
        "seeds": [r["seed"] for r in runs],
        "mean_latency_ms": mean("mean_latency_ms"),
        "sem_latency_ms": sem("mean_latency_ms"),
        "p95_latency_ms": mean("p95_latency_ms"),
        "mean_throughput_mbps": mean("mean_throughput_mbps"),
        "loss_pct": mean("loss_pct"),
        "sem_loss_pct": sem("loss_pct"),
        "oracle_floor_loss_pct": mean("oracle_floor_loss_pct"),
        "excess_loss_pct": mean("excess_loss_pct"),
        "mean_reward": mean("mean_reward"),
        "sem_reward": sem("mean_reward"),
        "cumulative_reward": mean("cumulative_reward"),
        "mean_queue_mbit": mean("mean_queue_mbit"),
        "max_queue_mbit": mean("max_queue_mbit"),
        "bound_violation_pct": mean("bound_violation_pct"),
        "mean_control_latency_ms": mean("mean_control_latency_ms"),
        "p95_control_latency_ms": mean("p95_control_latency_ms"),
        "mean_fast_decision_us": mean("mean_fast_decision_us"),
        "p99_fast_decision_us": mean("p99_fast_decision_us"),
        "rule_installs": mean("rule_installs"),
        "safety_vetoes": mean("safety_vetoes"),
        "llm_decisions": mean("llm_decisions"),
        "convergence_sec": mean("convergence_sec"),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def find_adapter(override: Optional[Path] = None) -> Path:
    """Locate the adapter the LoRA stages should load.

    Preference order: an explicit override, then the adapter this study trained on
    its own replay buffer, then the adapter promoted by the standalone
    self-improvement campaign. The chosen path is recorded in the run manifest.
    """
    if override is not None:
        if not (override / "adapter_model.safetensors").is_file():
            raise FileNotFoundError(f"no adapter at {override}")
        return override
    own = SELFX_ROOT / "output" / "pipeline_study" / "adapter"
    if (own / "adapter_model.safetensors").is_file():
        return own
    root = SELFX_ROOT / "output" / "self_improvement" / "ganesh_20261106" / "registry" / "artifacts"
    candidates = sorted(p for p in root.glob("*") if (p / "adapter_model.safetensors").is_file())
    if not candidates:
        raise FileNotFoundError("no promoted LoRA adapter found in the registry")
    return candidates[0]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SELF-X incremental pipeline study")
    parser.add_argument("--mode", choices=["live", "replay", "enumerate"], default="live")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1900, 1901, 1902, 1903, 1904])
    parser.add_argument("--windows", type=int, default=60,
                        help="control windows per run (5 s each)")
    parser.add_argument("--configurations", nargs="+",
                        default=list(STAGES) + list(BASELINES))
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--trace", type=Path, default=TRACE_PATH)
    parser.add_argument("--adapter", type=Path, default=None,
                        help="LoRA adapter directory for stages S3-S5")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    needs_llm = any(c in ("S1", "S2", "S4", "S5") for c in args.configurations)
    needs_lora = any(c in ("S3", "S4", "S5") for c in args.configurations)

    decider = None
    if needs_llm:
        decider = FreeModelDecider(trace_path=args.trace, mode=args.mode)
        print(f"[llm] mode={args.mode} chain={decider.model_chain}")

    lora_head = None
    if needs_lora:
        adapter = find_adapter(args.adapter)
        print(f"[lora] loading pinned SmolLM2-135M + adapter {adapter.name[:12]} ...")
        lora_head = LoRAHead.shared(adapter)
        print(f"[lora] ready in {lora_head.load_seconds}s")

    started = time.time()
    all_runs: List[Dict[str, Any]] = []
    for name in args.configurations:
        for seed in args.seeds:
            t0 = time.perf_counter()
            run = run_configuration(name, seed, args.windows, decider, lora_head)
            all_runs.append(run)
            print(
                f"{name:<13} seed {seed}  latency {run['mean_latency_ms']:6.2f} ms  "
                f"loss {run['loss_pct']:5.2f}%  reward {run['mean_reward']:+.4f}  "
                f"queue {run['mean_queue_mbit']:.4f} Mbit  "
                f"ctrl {run['mean_control_latency_ms']:7.1f} ms  "
                f"[{time.perf_counter() - t0:.1f}s]",
                flush=True,
            )

    by_config: Dict[str, List[Dict[str, Any]]] = {}
    for run in all_runs:
        by_config.setdefault(run["configuration"], []).append(run)

    summary = {
        "study": "SELF-X incremental pipeline study",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "seeds": args.seeds,
        "windows_per_run": args.windows,
        "window_sec": WINDOW_SEC,
        "tau_sec": TAU_SEC,
        "governance_epoch_windows": GOVERNANCE_WINDOWS,
        "wall_clock_sec": round(time.time() - started, 1),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "llm": decider.stats() if decider else None,
        "lora": ({"adapter": str(lora_head.adapter_dir), "calls": lora_head.calls,
                  "mean_inference_ms": round(lora_head.total_ms / lora_head.calls, 2)}
                 if lora_head and lora_head.calls else None),
        "stages": [aggregate(by_config[c]) for c in args.configurations if c in by_config],
        "max_conservation_error_mbit": max(r["conservation_error_mbit"] for r in all_runs),
    }

    # Export the self-critique stage's own experience as the LoRA training set.
    dataset = []
    for run in all_runs:
        if run["configuration"] != "S2":
            continue
        for row in run.get("replay_rows", []):
            dataset.append({"seed": run["seed"], **row})
    if dataset:
        with (args.out / "replay_dataset.jsonl").open("w", encoding="utf-8") as handle:
            for row in dataset:
                handle.write(json.dumps(row, separators=(",", ":")) + chr(10))
        print(f"exported {len(dataset)} S2 replay episodes -> replay_dataset.jsonl")

    (args.out / "pipeline_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    (args.out / "pipeline_runs.json").write_text(
        json.dumps(all_runs, indent=2), encoding="utf-8")

    fields = [k for k in summary["stages"][0] if k not in ("seeds",)]
    with (args.out / "pipeline_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary["stages"]:
            writer.writerow({k: row[k] for k in fields})

    with (args.out / "pipeline_windows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["configuration", "seed", "window", "latency_ms", "p95_latency_ms",
                         "throughput_mbps", "loss_pct", "reward", "mean_queue_mbit",
                         "max_queue_mbit", "action", "origin", "control_latency_ms"])
        for run in all_runs:
            for w in run["per_window"]:
                writer.writerow([run["configuration"], run["seed"], w["window"], w["latency_ms"],
                                 w["p95_latency_ms"], w["throughput_mbps"], w["loss_pct"],
                                 w["reward"], w["mean_queue_mbit"], w["max_queue_mbit"],
                                 w["action"], w["origin"], w["control_latency_ms"]])

    print(f"\nmax bit-conservation error: {summary['max_conservation_error_mbit']:.2e} Mbit")
    if decider:
        print(f"llm: {json.dumps(decider.stats(), indent=2)}")
    print(f"written -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
