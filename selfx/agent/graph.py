"""
Phase 3/4 — the agent itself: an explicit LangGraph state machine.

    observe -> decide -> act -> wait -> observe_after -> compute_reward -> reflect -> memorize

`observe`/`decide`/`act`/`reflect` are the four phases named in the spec's
architecture section; `wait`/`observe_after`/`compute_reward`/`memorize`
are the bookkeeping the spec describes happening between "act" and
"reflect" (wait one window, measure the outcome, compute the reward,
THEN reflect and persist).

The graph represents exactly one control-loop cycle. eval/run_ablation.py
calls `app.invoke(...)` once per cycle in a plain Python for-loop (so it
can interleave traffic-generator ticks between cycles), threading
`raw_state_prev` from one cycle's output into the next cycle's input so
rate calculations always have a "before" snapshot.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import StateGraph, END

import config
import ryu_client
import safety
from agent import metrics, prompts, reward as reward_mod
from agent.memory import MemoryStore
from agent.schemas import DecisionOutput, ReflectionOutput


class GraphState(TypedDict, total=False):
    cycle: int
    raw_state_prev: Optional[dict]     # carried in from the previous cycle
    raw_state_before: dict
    state_summary: dict
    latency_before_ms: float
    decision: dict
    decision_attempts: int
    safety_result: dict
    installed_action: str
    raw_state_after: dict
    latency_after_ms: float
    metrics_before: dict
    metrics_after: dict
    reward: float
    reward_breakdown: dict
    reflection: str


@dataclass
class AgentDeps:
    llm: Any                                            # a ChatAnthropic instance
    memory: MemoryStore
    get_state_fn: Callable[[], dict] = ryu_client.get_state
    add_flow_fn: Callable = ryu_client.add_flow
    add_meter_fn: Callable = ryu_client.add_meter
    latency_fn: Callable[[], float] = field(default=lambda: 0.0)
    wait_fn: Callable[[float], None] = time.sleep
    interval_sec: float = config.CONTROL_LOOP_INTERVAL_SEC
    link_capacity_kbps: float = config.LINK_BW_MBPS * 1000


def _lookup_flow_rate(state_summary: dict, target_match: Optional[dict]) -> float:
    flows = state_summary.get("top_flows", [])
    if not flows:
        return 0.0
    if target_match:
        for f in flows:
            if f["match"] == target_match:
                return f["rate_kbps"]
    return flows[0]["rate_kbps"]  # best-effort fallback: the hottest known flow


def _lookup_port_current_kbps(state_summary: dict, dpid: Optional[int]) -> float:
    ports = state_summary.get("hot_ports", [])
    if not ports:
        return 0.0
    if dpid is not None:
        matches = [p for p in ports if str(p["dpid"]) == str(dpid)]
        if matches:
            return max(p["tx_kbps"] for p in matches)
    return ports[0]["tx_kbps"]


def _meter_id_for(match: dict) -> int:
    return (abs(hash(json.dumps(match, sort_keys=True))) % 4999) + 1


def build_graph(deps: AgentDeps):
    graph = StateGraph(GraphState)

    def observe(state: GraphState) -> dict:
        raw_before = deps.get_state_fn()
        lat_before = deps.latency_fn()
        summary = metrics.build_state_summary(
            raw_before, state.get("raw_state_prev"), deps.interval_sec, lat_before
        )
        return {"raw_state_before": raw_before, "state_summary": summary,
                "latency_before_ms": lat_before}

    def decide(state: GraphState) -> dict:
        few_shot = deps.memory.few_shot_examples()
        messages = prompts.build_decide_messages(state["state_summary"], few_shot)
        structured_llm = deps.llm.with_structured_output(DecisionOutput)

        decision, attempts = None, 0
        for attempt in range(config.MALFORMED_OUTPUT_MAX_RETRIES + 1):
            attempts = attempt + 1
            try:
                candidate = structured_llm.invoke(messages)
            except Exception:
                candidate = None
            if candidate is not None and candidate.is_well_formed():
                decision = candidate
                break
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "That response was malformed or missing required "
                        "parameters for the chosen action. Return a single, "
                        "corrected, well-formed decision."
                    ),
                }
            ]

        if decision is None:
            decision = DecisionOutput(
                action="no_op",
                rationale="Falling back to no_op: malformed output after retry.",
            )
        return {"decision": decision.model_dump(), "decision_attempts": attempts}

    def act(state: GraphState) -> dict:
        decision = state["decision"]
        action = decision["action"]

        ctx = safety.SafetyContext(
            action=action,
            target_flow_rate_kbps=_lookup_flow_rate(
                state["state_summary"], decision.get("target_flow_match")
            ),
            proposed_rate_limit_kbps=decision.get("rate_limit_kbps"),
            target_link_capacity_kbps=deps.link_capacity_kbps,
            target_link_current_kbps=_lookup_port_current_kbps(
                state["state_summary"], decision.get("target_dpid")
            ),
        )
        result = safety.check(ctx)
        installed_action = result.safe_action

        if installed_action == "reroute" and decision.get("target_dpid") is not None:
            deps.add_flow_fn(
                decision["target_dpid"],
                decision["target_flow_match"],
                [{"type": "OUTPUT", "port": decision["reroute_out_port"]}],
                priority=200,
            )
        elif installed_action == "rate_limit" and decision.get("target_dpid") is not None:
            meter_id = _meter_id_for(decision["target_flow_match"])
            deps.add_meter_fn(decision["target_dpid"], meter_id, decision["rate_limit_kbps"])
            deps.add_flow_fn(
                decision["target_dpid"],
                decision["target_flow_match"],
                [{"type": "METER", "meter_id": meter_id}],
                priority=200,
            )
        # installed_action == "no_op" -> nothing to install

        return {
            "installed_action": installed_action,
            "safety_result": {
                "allowed": result.allowed,
                "reason": result.reason,
                "safe_action": result.safe_action,
            },
        }

    def wait(state: GraphState) -> dict:
        deps.wait_fn(deps.interval_sec)
        return {}

    def observe_after(state: GraphState) -> dict:
        raw_after = deps.get_state_fn()
        lat_after = deps.latency_fn()
        return {"raw_state_after": raw_after, "latency_after_ms": lat_after}

    def compute_reward(state: GraphState) -> dict:
        tp_after, loss_after = metrics.network_throughput_and_loss(
            state["raw_state_before"], state["raw_state_after"], deps.interval_sec
        )
        before = reward_mod.CycleMetrics(
            latency_ms=state["latency_before_ms"],
            throughput_kbps=state["state_summary"]["throughput_kbps"],
            loss_pct=state["state_summary"]["loss_pct"],
        )
        after = reward_mod.CycleMetrics(
            latency_ms=state["latency_after_ms"],
            throughput_kbps=tp_after,
            loss_pct=loss_after,
        )
        breakdown = reward_mod.compute_reward(before, after)
        return {
            "metrics_before": before.__dict__,
            "metrics_after": after.__dict__,
            "reward": breakdown.reward,
            "reward_breakdown": breakdown.__dict__,
        }

    def reflect(state: GraphState) -> dict:
        messages = prompts.build_reflect_messages(
            state["state_summary"],
            state["installed_action"],
            state["decision"],
            state["metrics_after"],
            state["reward"],
        )
        structured_llm = deps.llm.with_structured_output(ReflectionOutput)
        try:
            out = structured_llm.invoke(messages)
            reflection_text = out.reflection
        except Exception as exc:
            reflection_text = f"reflection call failed ({exc}); no additional insight recorded."
        return {"reflection": reflection_text}

    def memorize(state: GraphState) -> dict:
        deps.memory.add_record(
            cycle=state["cycle"],
            state_summary=state["state_summary"],
            action=state["installed_action"],
            params=state["decision"],
            reward=state["reward"],
            reflection=state["reflection"],
        )
        return {}

    graph.add_node("observe", observe)
    graph.add_node("decide", decide)
    graph.add_node("act", act)
    graph.add_node("wait", wait)
    graph.add_node("observe_after", observe_after)
    graph.add_node("compute_reward", compute_reward)
    graph.add_node("reflect", reflect)
    graph.add_node("memorize", memorize)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "decide")
    graph.add_edge("decide", "act")
    graph.add_edge("act", "wait")
    graph.add_edge("wait", "observe_after")
    graph.add_edge("observe_after", "compute_reward")
    graph.add_edge("compute_reward", "reflect")
    graph.add_edge("reflect", "memorize")
    graph.add_edge("memorize", END)

    return graph.compile()


def run_cycle(app, cycle: int, raw_state_prev: Optional[dict]) -> dict:
    """Invoke the compiled graph for one cycle; returns the final GraphState."""
    result = app.invoke({"cycle": cycle, "raw_state_prev": raw_state_prev})
    return result
