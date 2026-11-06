"""Step-by-step session over the real fluid model and controllers.

One call to Session.step() runs exactly one five-second control window with
the same logic as eval/run_v4_benchmarks.py (A0/B1/H1 via the v3 runner's
select(), H2/A4/O2 via the v4 policies), and returns everything the console
needs to explain it: loads, memory evidence, guard verdict, installed rule,
per-path queue/overflow and the same-window no-op counterfactual.
"""
from __future__ import annotations
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from agent.loss_aware_memory import LossAwareMemory, loss_aware_policy, capacity_policy, meter_decision, HEADROOMS
from agent.memory import MemoryStore
from agent.reward import compute_reward
from eval.run_adaptive_benchmarks import SCENARIOS, scenario_trace
from eval.run_benchmarks import select as v3_select
from eval.simulator import FluidNetwork, decision_for, CAPACITY, BUFFER, INTERVAL

CONTROLLERS = {
    "A0": "Static primary path (no control)",
    "B1": "Greedy least-loaded reroute",
    "H1": "Safety guard + fixed 20% meter",
    "H2": "Capacity-aware meter, no memory",
    "A4": "SELF-X: meter + episodic memory",
    "O2": "Oracle: peeks at outcomes (not deployable)",
}
PACKETS_PER_MBIT = 1e6 / (1500 * 8)  # display only: 1500-byte packets


@dataclass
class PathFlow:
    name: str
    arrival_mbps: float
    queue_before: float
    queue_after: float
    delivered_mbit: float
    overflow_mbit: float
    carries_elephant: bool


@dataclass
class Window:
    cycle: int
    phase: str
    demand: dict
    requested: object
    installed: object
    guard_allowed: bool
    guard_reason: str
    memory_scores: dict
    memory_support: list
    paths: list[PathFlow]
    meter_drop_mbit: float
    latency_ms: float
    loss_pct: float
    throughput_kbps: float
    offered_mbit: float
    dropped_mbit: float
    noop_latency_ms: float
    noop_loss_pct: float
    noop_dropped_mbit: float
    reward: float

    @property
    def primary_load_pct(self):
        return 10 * (self.demand["primary_background_mbps"] + self.demand["elephant_mbps"])

    @property
    def alternate_load_pct(self):
        return 10 * (self.demand["alternate_background_mbps"] + self.demand["elephant_mbps"])


def split_paths(queue_before, demand, decision) -> tuple[list[PathFlow], float]:
    """Per-path view of FluidNetwork.evaluate (same equations, kept per path)."""
    p, a, e = (demand[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps"))
    admitted = min(e, decision.rate_limit_kbps / 1000) if decision.action == "rate_limit" else e
    rates, on_alt = [p, a], decision.action == "reroute"
    rates[1 if on_alt else 0] += admitted
    flows = []
    for idx, (name, rate) in enumerate(zip(("primary", "alternate"), rates)):
        initial = queue_before[idx]
        raw = initial + (rate - CAPACITY) * INTERVAL
        final = min(BUFFER, max(0.0, raw))
        overflow = max(0.0, raw - BUFFER)
        flows.append(PathFlow(name, rate, initial, final, initial + rate * INTERVAL - final - overflow, overflow,
                              on_alt == (idx == 1)))
    return flows, (e - admitted) * INTERVAL


class Session:
    def __init__(self, controller="A4", scenario="mixed", seed=1900, cycles=120):
        if controller not in CONTROLLERS or scenario not in SCENARIOS:
            raise ValueError("unknown controller or scenario")
        self.controller, self.scenario, self.seed = controller, scenario, seed
        self.trace = scenario_trace(scenario, seed, cycles)
        self.net = FluidNetwork()
        self._tmp = tempfile.TemporaryDirectory(prefix="selfx-live-")
        path = str(Path(self._tmp.name) / "memory.json")
        # Same memory classes and settings as the benchmark: only A4 learns; nothing is saved.
        cls = LossAwareMemory if controller in {"H2", "A4", "O2"} else MemoryStore
        self.memory = cls(path, enabled=controller == "A4", autosave=False)
        self.memory.clear()
        self.cycle = 0
        self.history: list[Window] = []

    @property
    def done(self):
        return self.cycle >= len(self.trace)

    def _decide(self, state, demand):
        c = self.controller
        if c in {"A0", "B1", "H1"}:
            return v3_select(c, self.net, state, demand, self.memory)[0], [], {}
        if c == "H2":
            return capacity_policy(state, demand), [], {}
        if c == "A4":
            scores, _ = self.memory.meter_estimates(state, self.cycle)
            decision, used = loss_aware_policy(self.net, state, demand, self.memory, self.cycle)
            return decision, used, scores
        candidates = [decision_for(x, demand, "Privileged matched-action reference") for x in ("no_op", "reroute")]
        candidates += [meter_decision(state, demand, h, "Privileged meter reference") for h in HEADROOMS]
        before = self.net.evaluate(demand, decision_for("no_op", demand, "baseline"))
        best = max((d for d in candidates if self.net.validate(demand, d).allowed),
                   key=lambda d: compute_reward(before.metrics(), self.net.evaluate(demand, d).metrics()).reward)
        return best, [], {}

    def step(self) -> Window:
        if self.done:
            raise StopIteration("trace finished")
        demand = self.trace[self.cycle]
        queue_before = list(self.net.queue)
        state = self.net.summary(demand)
        decision, used, scores = self._decide(state, demand)
        guard = self.net.validate(demand, decision)
        installed = decision if guard.allowed else decision_for("no_op", demand, "Safety veto")
        before = self.net.evaluate(demand, decision_for("no_op", demand, "Same-window no-op measurement"))
        paths, meter_drop = split_paths(queue_before, demand, installed)
        after = self.net.evaluate(demand, installed, commit=True)
        reward = compute_reward(before.metrics(), after.metrics()).reward
        self.memory.add_record(self.cycle, state, installed.action, installed.model_dump(), reward,
                               f"Measured reward {reward:.6f}; loss {after.loss_pct:.6f}%")
        window = Window(self.cycle, demand["phase"], demand, decision, installed, guard.allowed, guard.reason,
                        scores, used, paths, meter_drop, after.latency_ms, after.loss_pct, after.throughput_kbps,
                        after.offered_mbit, after.dropped_mbit, before.latency_ms, before.loss_pct,
                        before.dropped_mbit, reward)
        self.history.append(window)
        self.cycle += 1
        return window

    def close(self):
        self._tmp.cleanup()
