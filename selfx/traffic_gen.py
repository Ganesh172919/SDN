"""
Phase 1 & Deliverable D1 — Reproducible Multi-Profile Traffic Generator
Traceability: Tasks T03, T28 | Deliverables D1, D2, D5 | EC466 Team SDN_07

Provides 3 frozen traffic profiles:
  1. 'steady_bursty': Constant background mice traffic + Poisson elephant bursts.
  2. 'flash_crowd': Multiple concurrent elephant flows causing sudden core bottleneck spikes.
  3. 'volatile_dpp': High-frequency fluctuating arrival rates (100 ms – 1 s intervals)
     for rigorous >=1,000 interval Lyapunov DPP backlog bound stress campaigns.

Can be called inside a live Mininet network (spawning iperf3 processes) or offline
to generate identical frozen JSON traffic traces across seeds and topologies.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAFFIC_OUTPUT_DIR = PROJECT_ROOT / "selfx" / "output" / "traffic"
TRAFFIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    import config
except ImportError:
    from selfx import config


def generate_schedule(
    profile: str = "steady_bursty",
    duration_sec: int = 600,
    seed: int = 42,
    num_hosts: int = 8,
) -> Dict[str, Any]:
    """
    Generate an offline, deterministic, frozen traffic event schedule.
    Independent of controller execution time or LLM latency.
    """
    rng = random.Random(seed)
    all_hosts = [f"h{i}" for i in range(1, num_hosts + 1)]
    events: List[Dict[str, Any]] = []

    # 1. Steady Background Traffic
    steady_flow = {
        "flow_id": "steady_h1_h8",
        "type": "steady_background",
        "src": "h1",
        "dst": f"h{num_hosts}",
        "start_time_sec": 0.0,
        "duration_sec": float(duration_sec),
        "rate_mbps": 3.0 + round(rng.uniform(-0.1, 0.1), 3),
        "port": 5201,
        "protocol": "udp",
    }
    events.append(steady_flow)

    # 2. Dynamic Bursts according to profile
    t = 2.0
    if profile == "steady_bursty":
        while t < duration_sec - 5:
            # Poisson inter-arrival (mean ~15 sec)
            inter_arrival = rng.expovariate(1.0 / 15.0)
            t += inter_arrival
            if t >= duration_sec - 2:
                break
            src, dst = rng.sample(all_hosts, 2)
            burst_rate = round(rng.uniform(config.BURST_MIN_MBPS, config.BURST_MAX_MBPS), 2)
            burst_dur = round(rng.uniform(config.BURST_MIN_DURATION_SEC, config.BURST_MAX_DURATION_SEC), 1)
            port = rng.randint(6000, 6999)
            events.append({
                "flow_id": f"burst_{int(t)}_{src}_{dst}",
                "type": "elephant_burst",
                "src": src,
                "dst": dst,
                "start_time_sec": round(t, 2),
                "duration_sec": burst_dur,
                "rate_mbps": burst_rate,
                "port": port,
                "protocol": "udp",
            })

    elif profile == "flash_crowd":
        # Regular pulses + sudden 3x flash crowd in middle third
        flash_start = duration_sec * 0.3
        flash_end = duration_sec * 0.7
        while t < duration_sec - 5:
            in_flash = flash_start <= t <= flash_end
            inter_arrival = rng.expovariate(1.0 / (4.0 if in_flash else 18.0))
            t += inter_arrival
            if t >= duration_sec - 2:
                break
            src = rng.choice(["h1", "h2", "h3"])
            dst = rng.choice(["h6", "h7", "h8"])
            rate = round(rng.uniform(10.0, 15.0) if in_flash else rng.uniform(4.0, 8.0), 2)
            dur = round(rng.uniform(4.0, 8.0) if in_flash else 3.0, 1)
            events.append({
                "flow_id": f"flash_{int(t)}_{src}_{dst}",
                "type": "flash_crowd" if in_flash else "normal_burst",
                "src": src,
                "dst": dst,
                "start_time_sec": round(t, 2),
                "duration_sec": dur,
                "rate_mbps": rate,
                "port": rng.randint(7000, 7999),
                "protocol": "udp",
            })

    elif profile == "volatile_dpp":
        # High frequency interval fluctuations for DPP backlog stress
        step = 0.5  # 500 ms ticks
        curr = 0.0
        while curr < duration_sec:
            wave = 4.0 * math.sin(curr / 5.0) + 2.0 * math.cos(curr / 2.0)
            noise = rng.uniform(-1.5, 2.5)
            rate = max(1.0, round(6.0 + wave + noise, 2))
            events.append({
                "flow_id": f"dpp_slot_{int(curr * 10)}",
                "type": "volatile_stream",
                "src": "h2",
                "dst": "h8",
                "start_time_sec": round(curr, 2),
                "duration_sec": step,
                "rate_mbps": rate,
                "port": 8000,
                "protocol": "udp",
            })
            curr += step

    schedule = {
        "profile": profile,
        "seed": seed,
        "duration_sec": duration_sec,
        "num_hosts": num_hosts,
        "total_events": len(events),
        "events": events,
    }
    return schedule


def save_schedule_manifest(profile: str, duration_sec: int, seed: int) -> Path:
    schedule = generate_schedule(profile, duration_sec, seed)
    out_file = TRAFFIC_OUTPUT_DIR / f"schedule_{profile}_seed{seed}_{duration_sec}s.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)
    return out_file


# -----------------------------------------------------------------------------
# Live Mininet Traffic Helpers
# -----------------------------------------------------------------------------

def start_steady_traffic(net, seed=config.TRAFFIC_SEED):
    rng = random.Random(seed)
    h_src = net.get("h1")
    h_dst = net.get(f"h{config.NUM_HOSTS}")

    server = h_dst.popen(["iperf3", "-s", "-1", "-p", "5201"])
    time.sleep(1)

    jitter = rng.uniform(-0.1, 0.1)
    rate_mbps = max(0.5, config.IPERF_STEADY_MBPS + jitter)

    client = h_src.popen([
        "iperf3", "-c", h_dst.IP(),
        "-p", "5201",
        "-u",
        "-b", f"{rate_mbps:.2f}M",
        "-t", str(config.IPERF_STEADY_DURATION_SEC),
        "-i", "1",
    ])
    return server, client


def start_bursty_traffic(net, run_duration_sec=600, seed=config.TRAFFIC_SEED, profile="steady_bursty"):
    schedule = generate_schedule(profile, run_duration_sec, seed, config.NUM_HOSTS)
    return schedule["events"], random.Random(seed)


def tick_bursty_traffic(net, events, rng, elapsed_sec, next_idx, run_start):
    procs = []
    fired = []
    while next_idx < len(events) and events[next_idx]["start_time_sec"] <= elapsed_sec:
        ev = events[next_idx]
        if ev["type"] != "steady_background":
            src = net.get(ev["src"])
            dst = net.get(ev["dst"])
            if src and dst:
                server = dst.popen(["iperf3", "-s", "-1", "-p", str(ev["port"])])
                time.sleep(0.05)
                client = src.popen([
                    "iperf3", "-c", dst.IP(),
                    "-p", str(ev["port"]),
                    "-u",
                    "-b", f"{ev['rate_mbps']}M",
                    "-t", str(ev["duration_sec"]),
                ])
                procs.extend([server, client])
            fired.append(ev)
        next_idx += 1
    return next_idx, fired, procs


def main():
    parser = argparse.ArgumentParser(description="SELF-X Reproducible Traffic Profile Generator")
    parser.add_argument("--profile", default="steady_bursty",
                        choices=["steady_bursty", "flash_crowd", "volatile_dpp"],
                        help="Traffic profile")
    parser.add_argument("--duration", type=int, default=600, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed")
    parser.add_argument("--export-all", action="store_true", help="Export all 3 profiles")
    args = parser.parse_args()

    if args.export_all:
        for prof in ["steady_bursty", "flash_crowd", "volatile_dpp"]:
            path = save_schedule_manifest(prof, args.duration, args.seed)
            print(f"Exported {prof} schedule -> {path}")
    else:
        path = save_schedule_manifest(args.profile, args.duration, args.seed)
        print(f"Exported {args.profile} schedule -> {path}")


if __name__ == "__main__":
    main()
