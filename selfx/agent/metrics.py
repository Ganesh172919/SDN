"""
Turns two consecutive ryu_client.get_state() snapshots into the compact,
numeric metrics the rest of the agent needs:

  - network-wide throughput (kbps) and loss (%) for reward.compute_reward
  - a per-flow rate table so the LLM can be shown concrete `match` dicts
    with real measured rates to reroute/rate_limit
  - a per-port utilization table so the safety check can tell whether a
    candidate reroute target link has headroom

ofctl_rest only exposes cumulative counters, so every quantity here is a
counter delta between two snapshots divided by the elapsed interval.
"""

from __future__ import annotations

import json

import config


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
    """Per-flow throughput (kbps) between two snapshots, newest flows first."""
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
            continue  # counter reset / flow re-installed
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


def port_utilization_pct(raw_state: dict,
                          link_capacity_kbps: float = config.LINK_BW_MBPS * 1000) -> list[dict]:
    """
    Instantaneous-ish per-port utilization estimate. Since we only have
    cumulative counters here (single snapshot), this reports raw
    tx/rx byte counters normalized by capacity as a coarse proxy; the
    rate-based version (two-snapshot) is `port_throughput_kbps` below,
    which is what utilization decisions should actually use.
    """
    out = []
    for dpid, sw in raw_state.get("switches", {}).items():
        for port in sw.get("ports", []):
            out.append(
                {
                    "dpid": dpid,
                    "port_no": port.get("port_no"),
                    "tx_bytes": port.get("tx_bytes", 0),
                    "rx_bytes": port.get("rx_bytes", 0),
                }
            )
    return out


def port_throughput_kbps(raw_before: dict, raw_after: dict, interval_sec: float) -> list[dict]:
    """Per-port tx throughput (kbps) and utilization % of LINK_BW_MBPS between two snapshots."""
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


def network_throughput_and_loss(raw_before: dict, raw_after: dict,
                                 interval_sec: float) -> tuple[float, float]:
    """
    Network-wide aggregate throughput (kbps) and loss (%) between two
    snapshots, summed across every port on every switch.
    """
    if interval_sec <= 0:
        return 0.0, 0.0

    before_idx = _index_ports(raw_before)
    after_idx = _index_ports(raw_after)

    total_tx_bytes = 0
    total_tx_packets = 0
    total_drops = 0

    for key, after_port in after_idx.items():
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

    throughput_kbps = (total_tx_bytes * 8 / 1000.0) / interval_sec
    denom = total_tx_packets + total_drops
    loss_pct = (100.0 * total_drops / denom) if denom > 0 else 0.0
    return round(throughput_kbps, 2), round(loss_pct, 3)


def build_state_summary(raw_state: dict, raw_prev: dict | None, interval_sec: float,
                         latency_ms: float, top_k: int = 5) -> dict:
    """Compact, LLM-friendly snapshot: aggregate health + top-K hot flows/ports."""
    if raw_prev is not None:
        flows = flow_rates_kbps(raw_prev, raw_state, interval_sec)[:top_k]
        ports = port_throughput_kbps(raw_prev, raw_state, interval_sec)[:top_k]
        throughput_kbps, loss_pct = network_throughput_and_loss(raw_prev, raw_state, interval_sec)
    else:
        flows, ports = [], []
        throughput_kbps, loss_pct = 0.0, 0.0

    return {
        "latency_ms": round(latency_ms, 2),
        "throughput_kbps": throughput_kbps,
        "loss_pct": loss_pct,
        "top_flows": flows,
        "hot_ports": ports,
        "num_switches": len(raw_state.get("switches", {})),
    }
