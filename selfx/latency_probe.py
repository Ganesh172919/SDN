"""
ofctl_rest gives cumulative packet/byte counters, but no notion of
latency. To feed the Δlatency term of the reward we need an actual
round-trip measurement, so this module runs a tiny ping probe between
the two steady-traffic endpoints (h1 <-> h8) directly on the Mininet
hosts.

Kept deliberately separate from ryu_client.py (which is REST-only) so
the "confirm the real ofctl_rest shapes first" Phase 0 step stays about
exactly what it says it's about.
"""

from __future__ import annotations

import re

_PING_RTT_RE = re.compile(r"time[=<]([\d.]+)\s*ms")


def probe_latency_ms(net, src_name: str = "h1", dst_name: str = "h8",
                      count: int = 3) -> float:
    """
    Run `ping -c {count}` from src to dst inside the live Mininet net and
    return the mean RTT in ms. Returns 0.0 if the hosts can't be reached
    (e.g. the network is currently partitioned by a fault-injection test).
    """
    try:
        h_src = net.get(src_name)
        h_dst = net.get(dst_name)
        output = h_src.cmd(f"ping -c {count} -W 1 {h_dst.IP()}")
    except Exception:
        return 0.0

    samples = [float(m) for m in _PING_RTT_RE.findall(output)]
    if not samples:
        return 0.0
    return sum(samples) / len(samples)
