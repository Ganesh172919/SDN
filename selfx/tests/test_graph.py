"""
Exercises the full observe->decide->act->wait->observe_after->
compute_reward->reflect->memorize LangGraph cycle with a fake LLM and
fake get_state()/add_flow()/add_meter(), so it needs neither a live
Anthropic API key nor a live Mininet/Ryu pair. Run directly:

    python3 -m tests.test_graph
"""

import os

from agent.graph import AgentDeps, build_graph, run_cycle
from agent.memory import MemoryStore
from agent.schemas import DecisionOutput, ReflectionOutput


class FakeStructuredLLM:
    """Stands in for `llm.with_structured_output(Schema).invoke(messages)`."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        resp = self._responses.pop(0) if self._responses else self._responses[-1]
        if isinstance(resp, Exception):
            raise resp
        return resp


class FakeLLM:
    """Stands in for a ChatAnthropic instance across BOTH the decide and
    reflect calls; hands out a fresh FakeStructuredLLM per schema so each
    call site gets its own scripted response queue."""

    def __init__(self, decide_responses, reflect_responses):
        self._decide = FakeStructuredLLM(decide_responses)
        self._reflect = FakeStructuredLLM(reflect_responses)

    def with_structured_output(self, schema):
        if schema is DecisionOutput:
            return self._decide
        if schema is ReflectionOutput:
            return self._reflect
        raise AssertionError(f"unexpected schema {schema}")


_STATE_CALL_COUNT = {"n": 0}


def fake_get_state():
    """Alternates between a 'before' and 'after' snapshot so throughput
    deltas are non-zero and deterministic across the two get_state() calls
    per cycle (observe, observe_after)."""
    _STATE_CALL_COUNT["n"] += 1
    base_bytes = 100_000 * _STATE_CALL_COUNT["n"]
    return {
        "switches": {
            "1": {
                "flows": [
                    {
                        "table_id": 0,
                        "priority": 100,
                        "match": {"in_port": 1, "ipv4_dst": "10.0.0.8"},
                        "byte_count": base_bytes,
                        "packet_count": base_bytes // 500,
                    }
                ],
                "aggregate": {"byte_count": base_bytes, "packet_count": base_bytes // 500,
                               "flow_count": 1},
                "ports": [
                    {
                        "port_no": 1,
                        "tx_bytes": base_bytes,
                        "rx_bytes": base_bytes,
                        "tx_packets": base_bytes // 500,
                        "rx_packets": base_bytes // 500,
                        "tx_dropped": 0, "rx_dropped": 0,
                        "tx_errors": 0, "rx_errors": 0,
                    }
                ],
            }
        }
    }


def test_full_cycle_reroute_allowed():
    installed = {}

    def fake_add_flow(dpid, match, actions, priority=100, **kw):
        installed["flow"] = (dpid, match, actions, priority)

    def fake_add_meter(dpid, meter_id, rate_kbps, **kw):
        installed["meter"] = (dpid, meter_id, rate_kbps)

    decision = DecisionOutput(
        action="reroute",
        target_dpid=1,
        target_flow_match={"in_port": 1, "ipv4_dst": "10.0.0.8"},
        reroute_out_port=3,
        rationale="link 1->2 looked hot, moving this flow to port 3",
    )
    reflection = ReflectionOutput(reflection="Rerouting reduced loss without hurting latency.")

    llm = FakeLLM(decide_responses=[decision], reflect_responses=[reflection])
    memory = MemoryStore(path="_scratch_graph_memory.json", enabled=True)
    memory.clear()

    deps = AgentDeps(
        llm=llm,
        memory=memory,
        get_state_fn=fake_get_state,
        add_flow_fn=fake_add_flow,
        add_meter_fn=fake_add_meter,
        latency_fn=lambda: 10.0,
        wait_fn=lambda secs: None,   # don't actually sleep in a test
        interval_sec=5.0,
    )
    app = build_graph(deps)
    result = run_cycle(app, cycle=0, raw_state_prev=None)

    assert result["installed_action"] == "reroute", result["installed_action"]
    assert "flow" in installed and installed["flow"][0] == 1
    assert result["reflection"] == "Rerouting reduced loss without hurting latency."
    assert memory.all_records(), "expected the cycle to be persisted to memory"
    rec = memory.all_records()[0]
    assert rec["action"] == "reroute"
    print("full cycle (reroute, allowed):", result["installed_action"],
          "reward=", round(result["reward"], 3), "attempts=", result["decision_attempts"])
    memory.clear()
    if os.path.exists("_scratch_graph_memory.json"):
        os.remove("_scratch_graph_memory.json")


def test_full_cycle_unsafe_rate_limit_falls_back_to_noop():
    installed = {"flow": None, "meter": None}

    def fake_add_flow(dpid, match, actions, priority=100, **kw):
        installed["flow"] = (dpid, match, actions, priority)

    def fake_add_meter(dpid, meter_id, rate_kbps, **kw):
        installed["meter"] = (dpid, meter_id, rate_kbps)

    # cycle 1 is called with raw_state_prev=None, so there is no prior
    # snapshot to derive this flow's current rate from yet; the safety
    # check must conservatively refuse to install a rate_limit it can't
    # verify is safe, rather than guess, and fall back to no_op.
    decision = DecisionOutput(
        action="rate_limit",
        target_dpid=1,
        target_flow_match={"in_port": 1, "ipv4_dst": "10.0.0.8"},
        rate_limit_kbps=100,
        rationale="clamp this elephant flow hard",
    )
    reflection = ReflectionOutput(reflection="The safety check correctly vetoed an overly aggressive cap.")

    llm = FakeLLM(decide_responses=[decision], reflect_responses=[reflection])
    memory = MemoryStore(path="_scratch_graph_memory2.json", enabled=False)

    deps = AgentDeps(
        llm=llm,
        memory=memory,
        get_state_fn=fake_get_state,
        add_flow_fn=fake_add_flow,
        add_meter_fn=fake_add_meter,
        latency_fn=lambda: 10.0,
        wait_fn=lambda secs: None,
        interval_sec=5.0,
    )
    app = build_graph(deps)
    result = run_cycle(app, cycle=1, raw_state_prev=None)

    assert result["installed_action"] == "no_op", result["installed_action"]
    assert installed["flow"] is None and installed["meter"] is None
    assert result["safety_result"]["allowed"] is False
    print("full cycle (rate_limit, vetoed):", result["safety_result"]["reason"])


def test_malformed_output_retries_then_falls_back():
    # first response is missing required rate_limit params -> malformed;
    # decide node should retry once, and since the retry ALSO comes back
    # malformed, it must fall back to no_op rather than crash.
    malformed_1 = DecisionOutput(action="rate_limit", rationale="oops, forgot the params")
    malformed_2 = DecisionOutput(action="rate_limit", rationale="still forgot them")
    reflection = ReflectionOutput(reflection="No action was safe to take this cycle.")

    llm = FakeLLM(decide_responses=[malformed_1, malformed_2], reflect_responses=[reflection])
    memory = MemoryStore(path="_scratch_graph_memory3.json", enabled=False)

    deps = AgentDeps(
        llm=llm,
        memory=memory,
        get_state_fn=fake_get_state,
        add_flow_fn=lambda *a, **k: None,
        add_meter_fn=lambda *a, **k: None,
        latency_fn=lambda: 10.0,
        wait_fn=lambda secs: None,
        interval_sec=5.0,
    )
    app = build_graph(deps)
    result = run_cycle(app, cycle=2, raw_state_prev=None)

    assert result["decision_attempts"] == 2, result["decision_attempts"]
    assert result["decision"]["action"] == "no_op"
    assert result["installed_action"] == "no_op"
    print("malformed-output retry-then-fallback: OK -> attempts=",
          result["decision_attempts"])


if __name__ == "__main__":
    test_full_cycle_reroute_allowed()
    test_full_cycle_unsafe_rate_limit_falls_back_to_noop()
    test_malformed_output_retries_then_falls_back()
    print("\nALL GRAPH SCRATCH TESTS PASSED")
