import json
import math
from pathlib import Path
import pytest
from agent.embedding import embed_state, cosine
from agent.providers import RestLLM, ProviderError
from agent.schemas import DecisionOutput
from agent.memory import MemoryStore
from eval.simulator import FluidNetwork, traffic_trace, decision_for
from eval.run_simulation import run_condition, local_path


def test_seed_and_traffic_are_identical_for_every_condition(tmp_path):
    trace = traffic_trace(1729, 24)
    assert trace == traffic_trace(1729, 24)
    assert trace != traffic_trace(1730, 24)
    observed = []
    for condition in ("A0", "B1", "A1", "A2"):
        _, details, _ = run_condition(condition, trace, 1729, "offline", tmp_path)
        observed.append([r["demand"] for r in details])
    assert all(t == trace for t in observed)


def test_conservation_and_physical_bounds():
    net = FluidNetwork()
    for demand in traffic_trace(51, 120):
        initial = sum(net.queue)
        decision = decision_for("rate_limit", demand, "conservation")
        result = net.evaluate(demand, decision, commit=True)
        assert math.isclose(initial + result.offered_mbit, result.delivered_mbit + result.dropped_mbit + sum(result.queue_mbit), abs_tol=1e-7)
        assert 0 <= result.loss_pct <= 100
        assert 0 <= result.throughput_kbps <= 20000.00001
        assert all(0 <= q <= .5 for q in net.queue)


def test_invalid_targets_and_overload_are_vetoed():
    net = FluidNetwork()
    demand = {"elephant_mbps": 8, "alternate_background_mbps": 4}
    assert not net.validate(demand, decision_for("reroute", demand, "overload")).allowed
    invalid = DecisionOutput(action="reroute", target_dpid=1, target_flow_match={"ipv4_dst": "bogus"}, reroute_out_port=3, rationale="bad")
    assert not net.validate(demand, invalid).allowed
    invalid.target_flow_match = {"in_port": 1, "eth_type": 2048, "ipv4_dst": "10.0.0.8"}
    invalid.reroute_out_port = 1
    assert not net.validate(demand, invalid).allowed


def test_embedding_retrieves_similar_states_and_persists(tmp_path):
    memory = MemoryStore(str(tmp_path / "nested" / "memory.json"))
    for i, features in enumerate(([1, 0, 0], [0, 1, 0])):
        memory.add_record(i, {"embedding_features": features}, "no_op", {}, 1-i, "observed")
    retrieved = memory.few_shot_examples(k=1, query={"embedding_features": [0, 1, 0]})
    assert retrieved[0]["cycle"] == 1
    assert len(MemoryStore(memory.path).all_records()) == 2
    assert math.isclose(cosine(embed_state({}), embed_state({})), 1)


def test_provider_failure_is_visible_noop_and_not_fabricated(monkeypatch, tmp_path):
    def unavailable(*args):
        raise ProviderError("http_401")
    monkeypatch.setattr(RestLLM, "_request", unavailable)
    rows, details, _ = run_condition("A2", traffic_trace(1, 3), 1, "gemini", tmp_path)
    assert all(r["decision_origin"] == "fallback_no_op" for r in rows)
    assert all(r["installed_action"] == "no_op" for r in rows)
    assert all(r["reflection_origin"] == "deterministic" for r in rows)
    assert all(r["provider_error"] for r in rows)


def test_scope_boundary():
    with pytest.raises(ValueError):
        local_path(Path.cwd().parent / "outside")
