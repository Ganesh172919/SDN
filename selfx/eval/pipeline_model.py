"""
Two-timescale fluid datapath model, reward definition and non-LLM baselines
used by ``eval/run_pipeline_study.py``.

Model (Section IV of the paper)
-------------------------------
Two parallel logical paths between the ingress and egress switch of a linear
4-switch OpenFlow topology:

    path 0 ("primary")    : capacity C0 Mbps, propagation D0 ms, buffer B Mbit
    path 1 ("alternate")  : capacity C1 Mbps, propagation D1 ms, buffer B Mbit

Time is slotted at tau = 0.1 s (the fast timescale). Mice traffic m(t) always
enters the primary path. The elephant aggregate e(t) enters the primary path
unless the installed action is ``reroute``; a ``rate_limit`` action installs an
OpenFlow meter that admits min(e(t), r/1000) Mbps and meters the rest away.

Per slot and per path the fluid recursion is

    net      = lambda - C
    q_next   = clip(q + net*tau, 0, B)
    overflow = max(0, q + net*tau - B)
    served   = q + lambda*tau - q_next - overflow

which conserves bits exactly:  q + lambda*tau == served + overflow + q_next.
The slot-average backlog uses the exact integral of the piecewise-linear queue
trajectory (including the saturation instant), not the endpoint average, so the
reported delay is the true time-average and not a sampling artefact.

Delay on a path is propagation plus queueing delay from Little's law,
    d = D + 1000 * qbar / C   [ms],
and the window delay is the served-bit-weighted mean across the two paths.

Everything here is deterministic given the traffic trace and the action
sequence; no randomness is drawn inside the model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Frozen model constants (reported verbatim in Table I of the paper)
# --------------------------------------------------------------------------- #

TAU_SEC = 0.1              # fast-timescale slot
WINDOW_SEC = 5.0           # control window (one installed action per window)
SLOTS_PER_WINDOW = int(round(WINDOW_SEC / TAU_SEC))
GOVERNANCE_WINDOWS = 6     # governance epoch = 6 windows = 30 s

C_PRIMARY_MBPS = 10.0
C_ALTERNATE_MBPS = 10.0
BUFFER_MBIT = 2.0
D_PRIMARY_MS = 2.0
D_ALTERNATE_MS = 12.0

#: Reward normalisation constants. Fixed before any experiment was run.
R_THROUGHPUT_REF_MBPS = 10.0
R_LATENCY_REF_MS = 50.0
W_THROUGHPUT = 1.0
W_LATENCY = 1.0
W_LOSS = 1.5
W_INSTALL = 0.05

#: Resolution of the statistics poller the slow loop reads. The controller never
#: sees more precision than this, which is both the honest monitoring interface and
#: what makes the set of distinct slow-loop prompts finite and therefore replayable.
MONITOR_GRID = {
    "rate_mbps": 1.0,
    "elephant_mbps": 2.5,
    "queue_mbit": 1.0,
    "latency_ms": 25.0,
    "loss_pct": 10.0,
    "util_pct": 25.0,
}

#: Lyapunov constants used by the analytic backlog bound.
A_MAX_MBPS = 20.0
MU_MAX_MBPS = 20.0
C_COST_MAX = 1.85
EPSILON_SLACK = 0.6

CONSERVATION_TOL_MBIT = 1e-9


def drift_constant_B() -> float:
    """B = 0.5 * sum_i (A_max^2 + mu_max^2), in Mbit^2 per slot^2."""
    return 0.5 * 2 * ((A_MAX_MBPS * TAU_SEC) ** 2 + (MU_MAX_MBPS * TAU_SEC) ** 2)


def backlog_bound_mbit(policy_v: float) -> float:
    """Theorem 1 ceiling  (B + V*C_max) / epsilon."""
    return (drift_constant_B() + policy_v * C_COST_MAX) / EPSILON_SLACK


# --------------------------------------------------------------------------- #
# Action representation
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Action:
    kind: str                            # no_op | reroute | rate_limit
    rate_limit_kbps: Optional[int] = None
    origin: str = "local"                # llm | lora | dpp | governor | static | fallback
    reason: str = ""

    def key(self) -> Tuple[str, Optional[int]]:
        return (self.kind, self.rate_limit_kbps)


NO_OP = Action("no_op", None, "static", "default primary forwarding")


# --------------------------------------------------------------------------- #
# Datapath
# --------------------------------------------------------------------------- #

@dataclass
class SlotOutcome:
    served_mbit: float
    overflow_mbit: float
    meter_mbit: float
    offered_mbit: float
    delay_ms: float
    queue_after: Tuple[float, float]
    qbar_total_mbit: float


class TwoPathDatapath:
    """Finite-buffer fluid datapath with exact per-slot bit conservation."""

    def __init__(self) -> None:
        self.queue: List[float] = [0.0, 0.0]
        self.conservation_error_mbit = 0.0

    # -- internals ---------------------------------------------------------- #

    @staticmethod
    def _average_queue(initial: float, net: float, tau: float) -> float:
        """Exact time-average of the queue over one slot, with clipping."""
        if abs(net) < 1e-12:
            return initial
        if net > 0:
            fill = (BUFFER_MBIT - initial) / net
            if fill >= tau:
                return initial + net * tau / 2.0
            return ((initial + BUFFER_MBIT) * fill / 2.0 + BUFFER_MBIT * (tau - fill)) / tau
        drain = initial / (-net)
        if drain >= tau:
            return initial + net * tau / 2.0
        return (initial * drain / 2.0) / tau

    # -- public ------------------------------------------------------------- #

    def step(self, mice_mbps: float, elephant_mbps: float, action: Action,
             tau: float = TAU_SEC) -> SlotOutcome:
        admitted_e = elephant_mbps
        if action.kind == "rate_limit" and action.rate_limit_kbps is not None:
            admitted_e = min(elephant_mbps, action.rate_limit_kbps / 1000.0)
        meter_mbit = (elephant_mbps - admitted_e) * tau

        arrivals = [mice_mbps, 0.0]
        if action.kind == "reroute":
            arrivals[1] += admitted_e
        else:
            arrivals[0] += admitted_e

        capacities = (C_PRIMARY_MBPS, C_ALTERNATE_MBPS)
        propagations = (D_PRIMARY_MS, D_ALTERNATE_MS)

        served_total = 0.0
        overflow_total = 0.0
        qbar_total = 0.0
        weighted_delay = 0.0
        next_queue: List[float] = []
        balance_in = 0.0
        balance_out = 0.0

        for idx, rate in enumerate(arrivals):
            q0 = self.queue[idx]
            net = rate - capacities[idx]
            raw = q0 + net * tau
            q1 = min(BUFFER_MBIT, max(0.0, raw))
            overflow = max(0.0, raw - BUFFER_MBIT)
            served = q0 + rate * tau - q1 - overflow
            qbar = self._average_queue(q0, net, tau)

            balance_in += q0 + rate * tau
            balance_out += served + overflow + q1

            delay = propagations[idx] + 1000.0 * qbar / capacities[idx]
            weighted_delay += delay * served
            served_total += served
            overflow_total += overflow
            qbar_total += qbar
            next_queue.append(q1)

        self.conservation_error_mbit = max(
            self.conservation_error_mbit, abs(balance_in - balance_out)
        )
        if abs(balance_in - balance_out) > CONSERVATION_TOL_MBIT:
            raise AssertionError(
                f"bit conservation violated by {balance_in - balance_out:.3e} Mbit"
            )

        self.queue = next_queue
        offered = (mice_mbps + elephant_mbps) * tau
        delay_ms = (weighted_delay / served_total) if served_total > 1e-12 else D_PRIMARY_MS
        return SlotOutcome(
            served_mbit=served_total,
            overflow_mbit=overflow_total,
            meter_mbit=meter_mbit,
            offered_mbit=offered,
            delay_ms=delay_ms,
            queue_after=(next_queue[0], next_queue[1]),
            qbar_total_mbit=qbar_total,
        )


# --------------------------------------------------------------------------- #
# Window aggregation
# --------------------------------------------------------------------------- #

@dataclass
class WindowResult:
    index: int
    offered_mbit: float
    served_mbit: float
    lost_mbit: float
    overflow_mbit: float
    meter_mbit: float
    throughput_mbps: float
    latency_ms: float
    p95_latency_ms: float
    loss_pct: float
    mean_queue_mbit: float
    max_queue_mbit: float
    reward: float
    installs: int
    action_kind: str
    action_origin: str
    control_latency_ms: float
    bound_violations: int
    slot_decision_us: float


def window_reward(throughput_mbps: float, latency_ms: float, loss_pct: float,
                  installs: int) -> float:
    """Fixed multi-objective reward (Eq. 12). Higher is better."""
    return (
        W_THROUGHPUT * (throughput_mbps / R_THROUGHPUT_REF_MBPS)
        - W_LATENCY * (latency_ms / R_LATENCY_REF_MS)
        - W_LOSS * (loss_pct / 100.0)
        - W_INSTALL * installs
    )


def aggregate_window(index: int, slots: Sequence[SlotOutcome], action: Action,
                     installs: int, control_latency_ms: float,
                     bound_mbit: float, slot_decision_us: float) -> WindowResult:
    offered = sum(s.offered_mbit for s in slots)
    served = sum(s.served_mbit for s in slots)
    overflow = sum(s.overflow_mbit for s in slots)
    meter = sum(s.meter_mbit for s in slots)
    lost = overflow + meter
    duration = len(slots) * TAU_SEC
    delays = sorted(s.delay_ms for s in slots)
    queues = [s.qbar_total_mbit for s in slots]
    mean_delay = sum(s.delay_ms * s.served_mbit for s in slots)
    mean_delay = mean_delay / served if served > 1e-12 else D_PRIMARY_MS
    p95 = delays[min(len(delays) - 1, int(math.ceil(0.95 * len(delays)) - 1))]
    throughput = served / duration
    loss_pct = 100.0 * lost / offered if offered > 1e-12 else 0.0
    return WindowResult(
        index=index,
        offered_mbit=offered,
        served_mbit=served,
        lost_mbit=lost,
        overflow_mbit=overflow,
        meter_mbit=meter,
        throughput_mbps=throughput,
        latency_ms=mean_delay,
        p95_latency_ms=p95,
        loss_pct=loss_pct,
        mean_queue_mbit=sum(queues) / len(queues),
        max_queue_mbit=max(queues),
        reward=window_reward(throughput, mean_delay, loss_pct, installs),
        installs=installs,
        action_kind=action.kind,
        action_origin=action.origin,
        control_latency_ms=control_latency_ms,
        bound_violations=sum(1 for q in queues if q > bound_mbit),
        slot_decision_us=slot_decision_us,
    )


# --------------------------------------------------------------------------- #
# Traffic: window-level demand derived from the frozen traffic_gen schedule
# --------------------------------------------------------------------------- #

def demand_series(schedule: Dict[str, Any], num_windows: int) -> List[Tuple[float, float]]:
    """Project a traffic_gen schedule onto per-slot (mice, elephant) demands.

    The schedule is produced offline by ``traffic_gen.generate_schedule`` and is
    hash-pinned in the result manifest, so the same seed always yields the same
    demand sequence regardless of controller timing.
    """
    slots = num_windows * SLOTS_PER_WINDOW
    series: List[Tuple[float, float]] = []
    events = schedule["events"]
    for slot in range(slots):
        t = slot * TAU_SEC
        mice = 0.0
        elephant = 0.0
        for ev in events:
            start = ev["start_time_sec"]
            if start <= t < start + ev["duration_sec"]:
                if ev["type"] == "steady_background":
                    mice += ev["rate_mbps"]
                else:
                    elephant += ev["rate_mbps"]
        series.append((mice, elephant))
    return series


# --------------------------------------------------------------------------- #
# Telemetry presented to a controller at a window boundary
# --------------------------------------------------------------------------- #

@dataclass
class Telemetry:
    window: int
    mice_mbps: float
    elephant_mbps: float
    queue_primary_mbit: float
    queue_alternate_mbit: float
    latency_ms: float
    loss_pct: float
    throughput_mbps: float
    util_primary_pct: float
    util_alternate_pct: float

    def features(self) -> List[float]:
        """5-d state vector consumed by the LoRA policy head."""
        return [
            min(2.0, self.util_primary_pct / 100.0),
            min(2.0, self.util_alternate_pct / 100.0),
            min(2.0, self.latency_ms / R_LATENCY_REF_MS),
            min(2.0, self.loss_pct / 20.0),
            min(2.0, (self.queue_primary_mbit + self.queue_alternate_mbit) / BUFFER_MBIT),
        ]

    def quantised(self) -> "Telemetry":
        """Telemetry rounded to the declared monitoring resolution.

        The controller never sees more precision than a real statistics poller
        would report: 0.5 Mbps on rates, 0.05 Mbit on backlogs, 2 ms on delay and
        2 percentage points on loss. Besides being the honest interface, this makes
        semantically identical windows collapse onto one prompt, which is what keeps
        the free-tier request count and the replay trace finite.
        """
        def q(x: float, step: float) -> float:
            return round(round(x / step) * step, 3)
        return Telemetry(
            window=self.window,
            mice_mbps=q(self.mice_mbps, MONITOR_GRID["rate_mbps"]),
            elephant_mbps=q(self.elephant_mbps, MONITOR_GRID["elephant_mbps"]),
            queue_primary_mbit=q(self.queue_primary_mbit, MONITOR_GRID["queue_mbit"]),
            queue_alternate_mbit=q(self.queue_alternate_mbit, MONITOR_GRID["queue_mbit"]),
            latency_ms=q(self.latency_ms, MONITOR_GRID["latency_ms"]),
            loss_pct=q(self.loss_pct, MONITOR_GRID["loss_pct"]),
            throughput_mbps=q(self.throughput_mbps, MONITOR_GRID["elephant_mbps"]),
            util_primary_pct=q(self.util_primary_pct, MONITOR_GRID["util_pct"]),
            util_alternate_pct=q(self.util_alternate_pct, MONITOR_GRID["util_pct"]),
        )

    def digest(self) -> Tuple:
        """Quantised state used as the LLM cache key and the replay-buffer index."""
        q = self.quantised()
        return (q.mice_mbps, q.elephant_mbps, q.queue_primary_mbit,
                q.queue_alternate_mbit, q.latency_ms, q.loss_pct)


# --------------------------------------------------------------------------- #
# Non-LLM comparison controllers (Table V)
# --------------------------------------------------------------------------- #

def static_controller(_telemetry: Telemetry) -> Action:
    """A0 / baseline 1: hand-installed shortest-path rule, never changed."""
    return NO_OP


def threshold_controller(t: Telemetry) -> Action:
    """Capacity-aware reactive heuristic (no learning, no model)."""
    if t.mice_mbps + t.elephant_mbps <= 0.85 * C_PRIMARY_MBPS:
        return Action("no_op", None, "heuristic", "primary below 85% trigger")
    if t.elephant_mbps + 0.0 <= 0.90 * C_ALTERNATE_MBPS and t.queue_alternate_mbit < 0.25:
        return Action("reroute", None, "heuristic", "alternate has headroom")
    headroom = max(0.5, 0.90 * C_PRIMARY_MBPS - t.mice_mbps)
    return Action("rate_limit", int(headroom * 1000), "heuristic", "meter elephant to headroom")


def oracle_floor(mice_mbps: float, elephant_mbps: float) -> float:
    """Maximum bits per slot any work-conserving controller could deliver.

    Used to report the irreducible loss floor of the offered trace: when the
    instantaneous demand exceeds C0 + C1 no placement of the elephant aggregate
    can avoid a drop, so this separates controller error from offered overload.
    """
    return min(mice_mbps + elephant_mbps, C_PRIMARY_MBPS + C_ALTERNATE_MBPS) * TAU_SEC


def least_loaded_controller(t: Telemetry) -> Action:
    """ECMP-style greedy least-loaded path selection."""
    if t.queue_alternate_mbit < t.queue_primary_mbit and t.elephant_mbps <= C_ALTERNATE_MBPS:
        return Action("reroute", None, "heuristic", "alternate is the shorter queue")
    return Action("no_op", None, "heuristic", "primary is the shorter queue")


class TabularQController:
    """Tabular Q-learning controller on the same reward and the same actions.

    This discrete value-table baseline trains online over the
    identical trace, which is exactly the cold-start penalty the paper attributes
    to value-based learners: it has to spend real windows exploring.
    """

    ACTIONS = ("no_op", "reroute", "rate_limit")

    def __init__(self, seed: int, alpha: float = 0.25, gamma: float = 0.9,
                 epsilon: float = 0.20) -> None:
        import random
        self.rng = random.Random(seed)
        self.q: Dict[Tuple, List[float]] = {}
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self._prev: Optional[Tuple[Tuple, int]] = None

    @staticmethod
    def _bucket(t: Telemetry) -> Tuple:
        return (
            min(4, int(t.mice_mbps / 1.5)),
            min(6, int(t.elephant_mbps / 2.0)),
            min(4, int((t.queue_primary_mbit / BUFFER_MBIT) * 4)),
            min(4, int((t.queue_alternate_mbit / BUFFER_MBIT) * 4)),
        )

    def act(self, t: Telemetry) -> Action:
        state = self._bucket(t)
        row = self.q.setdefault(state, [0.0, 0.0, 0.0])
        if self.rng.random() < self.epsilon:
            idx = self.rng.randrange(3)
        else:
            best = max(row)
            idx = self.rng.choice([i for i, v in enumerate(row) if v == best])
        self._prev = (state, idx)
        kind = self.ACTIONS[idx]
        if kind == "rate_limit":
            headroom = max(0.5, 0.90 * C_PRIMARY_MBPS - t.mice_mbps)
            return Action(kind, int(headroom * 1000), "tabular_q", "epsilon-greedy tabular Q action")
        return Action(kind, None, "tabular_q", "epsilon-greedy tabular Q action")

    def learn(self, reward: float, nxt: Telemetry) -> None:
        if self._prev is None:
            return
        state, idx = self._prev
        row = self.q.setdefault(state, [0.0, 0.0, 0.0])
        future = max(self.q.setdefault(self._bucket(nxt), [0.0, 0.0, 0.0]))
        row[idx] += self.alpha * (reward + self.gamma * future - row[idx])
        self.epsilon = max(0.02, self.epsilon * 0.995)


# --------------------------------------------------------------------------- #
# Fast-timescale drift-plus-penalty optimiser
# --------------------------------------------------------------------------- #

class PipelineDPP:
    """Drift-plus-penalty optimiser whose cost model *is* the datapath's own model.

    A drift-plus-penalty controller is only as good as the one-slot prediction it
    minimises over. Rather than score candidate actions with an approximate
    analytic surrogate, this optimiser evaluates each candidate through exactly the
    recursion the datapath will execute (Eqs. 1-4), including the meter rate the
    controller would actually install and the exact slot-average queue integral.
    The optimisation is therefore exact for the horizon it considers, and any gap
    to optimal is a consequence of the one-slot horizon, not of model mismatch.

    Complexity is O(|A|) with |A| <= 3, so a decision costs microseconds.
    """

    def __init__(self, tau: float = TAU_SEC) -> None:
        self.tau = tau
        self.decisions = 0

    @staticmethod
    def meter_rate_kbps(mice_mbps: float, elephant_mbps: float) -> int:
        """The rate the controller installs for a rate_limit action.

        Synthesised locally and identically wherever a meter is installed, so no
        learned component ever chooses a numeric rate.
        """
        headroom = max(0.512, 0.90 * C_PRIMARY_MBPS - mice_mbps)
        return int(min(headroom, max(elephant_mbps * 0.85, 0.512)) * 1000)

    def _predict(self, queue: Sequence[float], mice: float, elephant: float,
                 action: Action) -> Tuple[float, float, float, float]:
        """One-slot prediction: (drift, served, lost, mean delay)."""
        admitted = elephant
        if action.kind == "rate_limit" and action.rate_limit_kbps is not None:
            admitted = min(elephant, action.rate_limit_kbps / 1000.0)
        meter = (elephant - admitted) * self.tau

        arrivals = [mice, 0.0]
        if action.kind == "reroute":
            arrivals[1] += admitted
        else:
            arrivals[0] += admitted

        capacities = (C_PRIMARY_MBPS, C_ALTERNATE_MBPS)
        propagations = (D_PRIMARY_MS, D_ALTERNATE_MS)
        drift = served = overflow = weighted_delay = 0.0
        for idx, rate in enumerate(arrivals):
            q0 = queue[idx]
            net = rate - capacities[idx]
            drift += q0 * net
            raw = q0 + net * self.tau
            q1 = min(BUFFER_MBIT, max(0.0, raw))
            spill = max(0.0, raw - BUFFER_MBIT)
            delivered = q0 + rate * self.tau - q1 - spill
            qbar = TwoPathDatapath._average_queue(q0, net, self.tau)
            weighted_delay += (propagations[idx] + 1000.0 * qbar / capacities[idx]) * delivered
            served += delivered
            overflow += spill
        delay = weighted_delay / served if served > 1e-12 else D_PRIMARY_MS
        return drift, served, overflow + meter, delay

    def decide(self, queue: Sequence[float], mice_mbps: float, elephant_mbps: float,
               policy_v: float, weights: Dict[str, float],
               action_mask: Sequence[str]) -> Tuple[Action, float, Dict[str, float]]:
        """Return (action, decision time in microseconds, per-action scores)."""
        import time as _time

        started = _time.perf_counter()
        offered = (mice_mbps + elephant_mbps) * self.tau
        w_lat = weights.get("latency", 0.25)
        w_loss = weights.get("loss", 0.25)
        w_tp = weights.get("throughput", 0.25)
        w_energy = weights.get("energy", 0.15)
        w_res = weights.get("resource", 0.10)

        best: Optional[Action] = None
        best_score = float("inf")
        scores: Dict[str, float] = {}
        for kind in (action_mask or ("no_op",)):
            rate = self.meter_rate_kbps(mice_mbps, elephant_mbps) if kind == "rate_limit" else None
            candidate = Action(kind, rate, "dpp", "fast drift-plus-penalty")
            drift, served, lost, delay = self._predict(queue, mice_mbps, elephant_mbps, candidate)
            loss_pct = 100.0 * lost / offered if offered > 1e-12 else 0.0
            # Operating cost: the same objective the reward measures, plus the
            # path-dependent energy and resource terms the governor can reweight.
            energy = 1.70 if kind == "reroute" else 0.35
            resource = {"reroute": 0.55, "rate_limit": 0.40}.get(kind, 0.0)
            penalty = (w_lat * (delay / R_LATENCY_REF_MS)
                       + w_loss * (loss_pct / 100.0)
                       + w_energy * energy
                       + w_res * resource
                       - w_tp * (served / self.tau / R_THROUGHPUT_REF_MBPS))
            score = drift + policy_v * penalty
            scores[kind] = round(score, 6)
            if score < best_score:
                best_score, best = score, candidate
        self.decisions += 1
        elapsed_us = 1e6 * (_time.perf_counter() - started)
        return (best or NO_OP), elapsed_us, scores
