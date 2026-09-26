"""
Lightweight, dependency-free sanity checks for every piece that does NOT
need a live Mininet/Ryu pair: the hard-coded safety check, the JSON
memory store (pruning + few-shot retrieval), the reward formula, and the
counter-delta metrics derivation. No pytest required — run directly:

    python3 -m tests.test_core

The Mininet/Ryu-dependent pieces (topo.py, traffic_gen.py, ryu_client.py's
actual HTTP calls) can only be exercised on a real Linux host per the
README; tests/test_graph.py covers the LangGraph state machine itself
with a fake LLM and fake get_state()/add_flow()/add_meter(), so that one
DOES run anywhere.
"""

import json
import os

import config
import safety
from agent.memory import MemoryStore
from agent import reward, metrics


def test_safety_rate_limit():
    ctx = safety.SafetyContext(action="rate_limit", target_flow_rate_kbps=1000,
                                proposed_rate_limit_kbps=900)
    r = safety.check(ctx)
    assert r.allowed and r.safe_action == "rate_limit", r

    ctx2 = safety.SafetyContext(action="rate_limit", target_flow_rate_kbps=1000,
                                 proposed_rate_limit_kbps=200)  # drops 80%
    r2 = safety.check(ctx2)
    assert not r2.allowed and r2.safe_action == "no_op", r2
    print("safety rate_limit: OK ->", r.reason, "|", r2.reason)


def test_safety_reroute():
    ctx = safety.SafetyContext(action="reroute", target_flow_rate_kbps=500,
                                target_link_capacity_kbps=10000,
                                target_link_current_kbps=1000)
    r = safety.check(ctx)
    assert r.allowed, r

    ctx2 = safety.SafetyContext(action="reroute", target_flow_rate_kbps=8000,
                                 target_link_capacity_kbps=10000,
                                 target_link_current_kbps=5000)  # would be 130%
    r2 = safety.check(ctx2)
    assert not r2.allowed and r2.safe_action == "no_op", r2
    print("safety reroute: OK ->", r.reason, "|", r2.reason)


def test_memory_prune_and_fewshot():
    path = "_scratch_memory.json"
    if os.path.exists(path):
        os.remove(path)
    store = MemoryStore(path=path, enabled=True)
    for i in range(40):
        store.add_record(
            cycle=i,
            state_summary={"i": i},
            action="no_op",
            params={},
            reward=(i % 10) - 5,  # varies so pruning has something to chew on
            reflection=f"cycle {i}",
        )
    all_records = store.all_records()
    assert len(all_records) == config.MEMORY_MAX_ENTRIES, len(all_records)
    fewshot = store.few_shot_examples(k=5)
    assert len(fewshot) == 5
    assert fewshot[0]["reward"] >= fewshot[-1]["reward"]
    print("memory prune+fewshot: OK -> kept", len(all_records),
          "top reward", fewshot[0]["reward"])
    store.clear()
    os.remove(path) if os.path.exists(path) else None


def test_memory_disabled():
    store = MemoryStore(path="_scratch_memory_disabled.json", enabled=False)
    store.add_record(cycle=0, state_summary={}, action="no_op", params={},
                      reward=1.0, reflection="x")
    assert store.all_records() == []
    assert store.few_shot_examples() == []
    assert not os.path.exists("_scratch_memory_disabled.json")
    print("memory disabled: OK -> stays empty, no file written")


def test_reward():
    before = reward.CycleMetrics(latency_ms=20, throughput_kbps=2000, loss_pct=1.0)
    after_good = reward.CycleMetrics(latency_ms=15, throughput_kbps=2500, loss_pct=0.5)
    after_bad = reward.CycleMetrics(latency_ms=40, throughput_kbps=1500, loss_pct=3.0)
    good = reward.compute_reward(before, after_good)
    bad = reward.compute_reward(before, after_bad)
    assert good.reward > 0 > bad.reward, (good, bad)
    print("reward: OK -> good", round(good.reward, 3), "bad", round(bad.reward, 3))


def _fake_state(byte_counts, tx_bytes_by_port):
    """Build a get_state()-shaped dict for two switches with one flow + one port each."""
    switches = {}
    for dpid, bc in byte_counts.items():
        switches[dpid] = {
            "flows": [
                {
                    "table_id": 0,
                    "priority": 100,
                    "match": {"in_port": 1, "ipv4_dst": "10.0.0.8"},
                    "byte_count": bc,
                    "packet_count": bc // 500,
                }
            ],
            "aggregate": {"byte_count": bc, "packet_count": bc // 500, "flow_count": 1},
            "ports": [
                {
                    "port_no": 1,
                    "tx_bytes": tx_bytes_by_port[dpid],
                    "rx_bytes": tx_bytes_by_port[dpid],
                    "tx_packets": tx_bytes_by_port[dpid] // 500,
                    "rx_packets": tx_bytes_by_port[dpid] // 500,
                    "tx_dropped": 0,
                    "rx_dropped": 0,
                    "tx_errors": 0,
                    "rx_errors": 0,
                }
            ],
        }
    return {"switches": switches}


def test_metrics():
    before = _fake_state({"1": 100_000}, {"1": 100_000})
    after = _fake_state({"1": 100_000 + 500_000}, {"1": 100_000 + 500_000})
    interval = 5.0

    flows = metrics.flow_rates_kbps(before, after, interval)
    assert len(flows) == 1
    expected_kbps = (500_000 * 8 / 1000.0) / interval
    assert abs(flows[0]["rate_kbps"] - expected_kbps) < 0.01, flows

    tp_kbps, loss_pct = metrics.network_throughput_and_loss(before, after, interval)
    assert abs(tp_kbps - expected_kbps) < 0.01, tp_kbps
    assert loss_pct == 0.0

    summary = metrics.build_state_summary(after, before, interval, latency_ms=12.3)
    assert summary["throughput_kbps"] == tp_kbps
    assert summary["top_flows"][0]["match"] == {"in_port": 1, "ipv4_dst": "10.0.0.8"}
    print("metrics: OK -> flow rate", flows[0]["rate_kbps"], "kbps, net tp", tp_kbps, "kbps")


if __name__ == "__main__":
    test_safety_rate_limit()
    test_safety_reroute()
    test_memory_prune_and_fewshot()
    test_memory_disabled()
    test_reward()
    test_metrics()
    print("\nALL SCRATCH TESTS PASSED")
