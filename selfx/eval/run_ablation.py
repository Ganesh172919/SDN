"""
Phase 5 — evaluation harness.

Runs three conditions, in order, over the IDENTICAL traffic seed and
topology:

    A0 — static Ryu (ryu.app.simple_switch_13 only), no agent at all.
    A1 — agent runs every cycle, but memory is disabled (empty every
         cycle: no few-shot examples in the decide prompt, no
         reflection persisted).
    A2 — agent runs every cycle with the full reflection + memory loop.

For each condition this logs (cycle, latency_ms, throughput_kbps,
loss_pct, reward, installed_action) to eval/logs/<condition>.csv, then
plot_results.py turns those three CSVs into the comparison plots the
spec's acceptance criteria ask for.

MUST be run on a real Linux host with Open vSwitch + Mininet installed,
as root (`sudo python3 -m eval.run_ablation`), with a Ryu instance
already listening — see README.md for the exact two ryu-manager
invocations (one for A0, one for A1/A2).

This will NOT run inside a rootless/sandboxed container: Mininet needs
to create real network namespaces and OVS bridges.
"""

from __future__ import annotations

import argparse
import csv
import os
import time

import config
import ryu_client
import topo
import traffic_gen
import latency_probe
from agent import metrics
from agent.graph import AgentDeps, build_graph, run_cycle
from agent.memory import MemoryStore


def _make_llm():
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=config.ANTHROPIC_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )


def _clear_all_flows(dpids):
    for dpid in dpids:
        try:
            ryu_client.clear_flows(dpid)
        except Exception:
            pass


def _run_condition(condition: str, run_duration_sec: int, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{condition}.csv")

    net = topo.build_net()
    try:
        time.sleep(2)  # let OVS<->Ryu handshake settle
        dpids = ryu_client.get_switches()
        _clear_all_flows(dpids)

        traffic_gen.start_steady_traffic(net, seed=config.TRAFFIC_SEED)
        schedule, rng = traffic_gen.start_bursty_traffic(
            net, run_duration_sec=run_duration_sec, seed=config.TRAFFIC_SEED
        )
        fired_idx = 0
        run_start = time.time()

        agent_app, memory = None, None
        if condition in ("A1", "A2"):
            memory = MemoryStore(
                path=os.path.join(out_dir, f"{condition}_memory.json"),
                enabled=(condition == "A2"),
            )
            memory.clear()
            deps = AgentDeps(
                llm=_make_llm(),
                memory=memory,
                latency_fn=lambda: latency_probe.probe_latency_ms(net),
            )
            agent_app = build_graph(deps)

        rows = []
        raw_prev = None
        num_cycles = run_duration_sec // config.CONTROL_LOOP_INTERVAL_SEC

        for cycle in range(num_cycles):
            elapsed = time.time() - run_start
            fired_idx, events, procs = traffic_gen.tick_bursty_traffic(
                net, schedule, rng, elapsed, fired_idx, run_start
            )

            if condition == "A0":
                raw_before = ryu_client.get_state()
                lat_before = latency_probe.probe_latency_ms(net)
                summary = metrics.build_state_summary(
                    raw_before, raw_prev, config.CONTROL_LOOP_INTERVAL_SEC, lat_before
                )
                time.sleep(config.CONTROL_LOOP_INTERVAL_SEC)
                raw_after = ryu_client.get_state()
                lat_after = latency_probe.probe_latency_ms(net)
                tp_after, loss_after = metrics.network_throughput_and_loss(
                    raw_before, raw_after, config.CONTROL_LOOP_INTERVAL_SEC
                )
                rows.append(
                    {
                        "cycle": cycle,
                        "latency_ms": lat_after,
                        "throughput_kbps": tp_after,
                        "loss_pct": loss_after,
                        "reward": "",
                        "installed_action": "",
                    }
                )
                raw_prev = raw_before
            else:
                result = run_cycle(agent_app, cycle, raw_prev)
                rows.append(
                    {
                        "cycle": cycle,
                        "latency_ms": result["metrics_after"]["latency_ms"],
                        "throughput_kbps": result["metrics_after"]["throughput_kbps"],
                        "loss_pct": result["metrics_after"]["loss_pct"],
                        "reward": result["reward"],
                        "installed_action": result["installed_action"],
                    }
                )
                raw_prev = result["raw_state_before"]

            print(f"[{condition}] cycle {cycle}/{num_cycles} -> {rows[-1]}")

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["cycle", "latency_ms", "throughput_kbps", "loss_pct",
                               "reward", "installed_action"]
            )
            writer.writeheader()
            writer.writerows(rows)

    finally:
        net.stop()

    return csv_path


def main():
    parser = argparse.ArgumentParser(description="Run the A0/A1/A2 ablation")
    parser.add_argument("--duration", type=int, default=config.RUN_DURATION_SEC,
                         help="seconds per condition (default: %(default)s)")
    parser.add_argument("--out-dir", default=config.EVAL_LOG_DIR)
    parser.add_argument("--conditions", nargs="+", default=list(config.CONDITIONS))
    args = parser.parse_args()

    for condition in args.conditions:
        print(f"=== Running condition {condition} for {args.duration}s ===")
        path = _run_condition(condition, args.duration, args.out_dir)
        print(f"=== {condition} done -> {path} ===")


if __name__ == "__main__":
    main()
