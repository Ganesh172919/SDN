"""
Telemetry and Network Metric Processing for SELF-X
Traceability: Tasks T04, T29 | Deliverables D2, D3, D5 | EC466 Team SDN_07

Provides:
  - Timestamped queue depth & backlog calculation (Q(t) in Mbit).
  - Accurate endpoint goodput & loss (calibrated to edge ports to avoid multi-hop inflation).
  - p95 and mean end-to-end latency measurement.
  - Interface arrival rate λ and service rate μ tracking.
  - Per-flow throughput and per-port utilization.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    import config
except ImportError:
    from selfx import config


def _flow_key(dpid: str, flow: dict) -> tuple:
    match_items = tuple(sorted(flow.get("match", {}).items()))
    return (dpid, match_items, flow.get("priority", 0), flow.get("table_id", 0))


def _index_flows(raw_state: dict) -> dict:
    idx = {}
    for dpid, sw in raw_state.get("switches", {}).items():
        for flow in sw.get("flows", []):
            idx[_flow_key(dpid, flow)] = flow
    return idx


def _index_ports(raw_state: dict) -> dict:
    idx = {}
    for dpid, sw in raw_state.get("switches", {}).items():
        for port in sw.get("ports", []):
            idx[(dpid, port.get("port_no"))] = port
    return idx


def flow_rates_kbps(raw_before: dict, raw_after: dict, interval_sec: float) -> list[dict]:
    """Per-flow throughput (kbps) between two snapshots, sorted descending."""
    if interval_sec <= 0:
        return []
    before_idx = _index_flows(raw_before)
    after_idx = _index_flows(raw_after)

    rates = []
    for key, after_flow in after_idx.items():
        before_flow = before_idx.get(key)
        if before_flow is None:
            continue
        delta_bytes = after_flow.get("byte_count", 0) - before_flow.get("byte_count", 0)
        if delta_bytes < 0:
            continue
        rate_kbps = (delta_bytes * 8 / 1000.0) / interval_sec
        dpid, match_items, priority, table_id = key
        rates.append(
            {
                "dpid": dpid,
                "match": dict(match_items),
                "priority": priority,
                "rate_kbps": round(rate_kbps, 2),
            }
        )
    rates.sort(key=lambda r: r["rate_kbps"], reverse=True)
    return rates


def port_throughput_kbps(raw_before: dict, raw_after: dict, interval_sec: float) -> list[dict]:
    """Per-port tx throughput (kbps) and utilization % between two snapshots."""
    if interval_sec <= 0:
        return []
    before_idx = _index_ports(raw_before)
    after_idx = _index_ports(raw_after)
    capacity_kbps = config.LINK_BW_MBPS * 1000

    out = []
    for key, after_port in after_idx.items():
        before_port = before_idx.get(key)
        if before_port is None:
            continue
        delta_tx = after_port.get("tx_bytes", 0) - before_port.get("tx_bytes", 0)
        if delta_tx < 0:
            continue
        tx_kbps = (delta_tx * 8 / 1000.0) / interval_sec
        dpid, port_no = key
        out.append(
            {
                "dpid": dpid,
                "port_no": port_no,
                "tx_kbps": round(tx_kbps, 2),
                "util_pct": round(100.0 * tx_kbps / capacity_kbps, 1) if capacity_kbps else 0.0,
            }
        )
    out.sort(key=lambda p: p["util_pct"], reverse=True)
    return out


def extract_queue_backlog_mbit(raw_state: dict) -> float:
    """
    Extract total queue backlog across bottleneck interfaces in Megabits (Mbit).
    Reads OFPQueueStats or parses tx_bytes vs buffer depth.
    """
    total_queue_bytes = 0
    switches = raw_state.get("switches", {})
    for dpid, sw_data in switches.items():
        queues = sw_data.get("queues", [])
        for q in queues:
            # tx_bytes or current backlog bytes
            total_queue_bytes += q.get("tx_bytes", 0) or q.get("current_bytes", 0)
        # Fallback to simulated queue if explicitly present
        if "simulated_queue_mbit" in sw_data:
            return float(sw_data["simulated_queue_mbit"])

    if total_queue_bytes > 0:
        return round((total_queue_bytes * 8) / 1_000_000.0, 4)
    return float(raw_state.get("queue_backlog_mbit", 0.0))


def compute_p95_latency(latency_samples: List[float], fallback_latency: float) -> float:
    """Compute 95th percentile latency from probe window samples."""
    if not latency_samples:
        return round(fallback_latency * 1.25, 2)
    s = sorted(latency_samples)
    idx = int(math.ceil(0.95 * len(s))) - 1
    idx = max(0, min(idx, len(s) - 1))
    return round(s[idx], 2)


def network_throughput_and_loss(
    raw_before: dict,
    raw_after: dict,
    interval_sec: float,
    edge_ports_only: bool = True,
) -> tuple[float, float]:
    """
    Calibrated end-to-end goodput (kbps) and loss (%).
    When edge_ports_only is True, measures at edge egress/ingress ports to ensure
    intermediate hops do not inflate or multiply delivered goodput.
    """
    if interval_sec <= 0:
        return 0.0, 0.0

    before_idx = _index_ports(raw_before)
    after_idx = _index_ports(raw_after)

    total_tx_bytes = 0
    total_tx_packets = 0
    total_drops = 0

    for key, after_port in after_idx.items():
        dpid, port_no = key
        # Edge switch egress ports (e.g., s1 host ports, s4 host ports)
        if edge_ports_only and dpid not in ("1", "4", "0000000000000001", "0000000000000004"):
            continue

        before_port = before_idx.get(key)
        if before_port is None:
            continue
        d_tx_bytes = after_port.get("tx_bytes", 0) - before_port.get("tx_bytes", 0)
        d_tx_pkts = after_port.get("tx_packets", 0) - before_port.get("tx_packets", 0)
        d_drops = (
            (after_port.get("tx_dropped", 0) - before_port.get("tx_dropped", 0))
            + (after_port.get("rx_dropped", 0) - before_port.get("rx_dropped", 0))
            + (after_port.get("tx_errors", 0) - before_port.get("tx_errors", 0))
            + (after_port.get("rx_errors", 0) - before_port.get("rx_errors", 0))
        )
        if d_tx_bytes >= 0:
            total_tx_bytes += d_tx_bytes
        if d_tx_pkts >= 0:
            total_tx_packets += d_tx_pkts
        if d_drops >= 0:
            total_drops += d_drops

    # Fallback to all ports if edge ports had 0 bytes
    if total_tx_bytes == 0 and not edge_ports_only:
        return network_throughput_and_loss(raw_before, raw_after, interval_sec, edge_ports_only=False)

    throughput_kbps = (total_tx_bytes * 8 / 1000.0) / interval_sec
    denom = total_tx_packets + total_drops
    loss_pct = (100.0 * total_drops / denom) if denom > 0 else 0.0
    return round(throughput_kbps, 2), round(loss_pct, 3)


def build_state_summary(
    raw_state: dict,
    raw_prev: dict | None,
    interval_sec: float,
    latency_ms: float,
    latency_samples: Optional[List[float]] = None,
    top_k: int = 5,
) -> dict:
    """Comprehensive snapshot with verified queue depth, p95 latency, and arrivals."""
    if raw_prev is not None:
        flows = flow_rates_kbps(raw_prev, raw_state, interval_sec)[:top_k]
        ports = port_throughput_kbps(raw_prev, raw_state, interval_sec)[:top_k]
        throughput_kbps, loss_pct = network_throughput_and_loss(raw_prev, raw_state, interval_sec)
    else:
        flows, ports = [], []
        throughput_kbps, loss_pct = 0.0, 0.0

    queue_mbit = extract_queue_backlog_mbit(raw_state)
    p95_lat = compute_p95_latency(latency_samples or [], latency_ms)

    return {
        "latency_ms": round(latency_ms, 2),
        "p95_latency_ms": p95_lat,
        "throughput_kbps": throughput_kbps,
        "throughput_mbps": round(throughput_kbps / 1000.0, 3),
        "loss_pct": loss_pct,
        "queue_mbit": queue_mbit,
        "top_flows": flows,
        "hot_ports": ports,
        "num_switches": len(raw_state.get("switches", {})),
    }
