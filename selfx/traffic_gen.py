"""
Phase 1 — Traffic generator.

Two traffic classes, both driven off the same fixed random seed
(config.TRAFFIC_SEED) so that A0 / A1 / A2 in the eval harness see
byte-for-byte the same traffic pattern:

  (a) steady load   — long-lived iperf3 UDP streams between the two
                       "end" hosts (h1 <-> h8), spanning the full
                       linear topology so every inter-switch link
                       carries background traffic.

  (b) bursty/elephant flows — a custom generator that, at randomised
                       (but seeded) intervals, spins up a short,
                       high-bandwidth iperf3 burst between a random
                       pair of hosts to simulate an elephant flow
                       landing on top of the steady load.

This module assumes it is driven from inside a running Mininet network
(see topo.build_net) — it shells out to iperf3 on the Mininet hosts via
their .popen()/.cmd() helpers, it does not run standalone.
"""

import random
import time

import config


def _host_pair_for_steady(net):
    """The two hosts furthest apart on the linear chain (h1, hN)."""
    h_first = net.get("h1")
    h_last = net.get(f"h{config.NUM_HOSTS}")
    return h_first, h_last


def start_steady_traffic(net, seed=config.TRAFFIC_SEED):
    """
    Start one long-lived iperf3 UDP stream from h1 -> h8 at a fixed
    rate. Returns the (server_proc, client_proc) popen handles so the
    caller can terminate them at the end of the run.
    """
    rng = random.Random(seed)
    h_src, h_dst = _host_pair_for_steady(net)

    server = h_dst.popen(["iperf3", "-s", "-1", "-p", "5201"])
    time.sleep(1)  # give the server a moment to bind

    # small seeded jitter on the target rate so repeated runs with the
    # same seed are identical, but the rate isn't a suspiciously round number
    jitter = rng.uniform(-0.2, 0.2)
    rate_mbps = max(0.5, config.IPERF_STEADY_MBPS + jitter)

    client = h_src.popen(
        [
            "iperf3",
            "-c", h_dst.IP(),
            "-p", "5201",
            "-u",
            "-b", f"{rate_mbps}M",
            "-t", str(config.IPERF_STEADY_DURATION_SEC),
            "-i", "1",
        ]
    )
    return server, client


def _elephant_burst(net, rng, run_start, run_duration):
    """One bursty/elephant-flow event between a random host pair."""
    all_hosts = [f"h{i}" for i in range(1, config.NUM_HOSTS + 1)]
    src_name, dst_name = rng.sample(all_hosts, 2)
    h_src, h_dst = net.get(src_name), net.get(dst_name)

    port = rng.randint(6000, 6999)
    rate_mbps = rng.uniform(config.BURST_MIN_MBPS, config.BURST_MAX_MBPS)
    duration_sec = rng.randint(
        config.BURST_MIN_DURATION_SEC, config.BURST_MAX_DURATION_SEC
    )

    server = h_dst.popen(["iperf3", "-s", "-1", "-p", str(port)])
    time.sleep(0.5)
    client = h_dst is not None and h_src.popen(
        [
            "iperf3",
            "-c", h_dst.IP(),
            "-p", str(port),
            "-u",
            "-b", f"{rate_mbps:.2f}M",
            "-t", str(duration_sec),
        ]
    )
    return {
        "t": time.time() - run_start,
        "src": src_name,
        "dst": dst_name,
        "rate_mbps": round(rate_mbps, 2),
        "duration_sec": duration_sec,
    }, server, client


def start_bursty_traffic(net, run_duration_sec=config.RUN_DURATION_SEC,
                          seed=config.TRAFFIC_SEED):
    """
    Generator-style driver: call `next(gen)` (or iterate) from the
    control loop / eval harness once per control-loop tick. Each call
    checks the seeded schedule and fires an elephant-flow burst if one
    is due, and always returns the list of live (server, client) popen
    handles so the caller can reap them at shutdown.

    Usage:
        bursts = []
        procs = []
        for fired, p in traffic_gen.tick_bursty_traffic(net, sched, now):
            ...
    """
    rng = random.Random(seed + 1)  # different stream than the steady jitter
    schedule = []
    t = rng.uniform(config.BURST_MIN_INTERVAL_SEC, config.BURST_MAX_INTERVAL_SEC)
    while t < run_duration_sec:
        schedule.append(t)
        t += rng.uniform(config.BURST_MIN_INTERVAL_SEC, config.BURST_MAX_INTERVAL_SEC)
    return schedule, rng


def tick_bursty_traffic(net, schedule, rng, elapsed_sec, fired_idx, run_start):
    """
    Call once per control-loop cycle with the elapsed seconds since the
    run started. Fires every scheduled burst whose time has come since
    the last call. `fired_idx` is the index of the next not-yet-fired
    event in `schedule` (caller keeps this across calls).

    Returns (new_fired_idx, events_fired, procs_started).
    """
    events, procs = [], []
    while fired_idx < len(schedule) and schedule[fired_idx] <= elapsed_sec:
        event, server, client = _elephant_burst(net, rng, run_start, elapsed_sec)
        events.append(event)
        procs.extend([server, client])
        fired_idx += 1
    return fired_idx, events, procs


def stop_all(procs):
    for p in procs:
        try:
            if p is not None:
                p.terminate()
        except Exception:
            pass
