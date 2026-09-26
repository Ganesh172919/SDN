"""
Phase 2 — Telemetry / control client over ryu.app.ofctl_rest.

Endpoint paths and response/request shapes below were confirmed against
the official Ryu docs (ryu.app.ofctl_rest, OpenFlow 1.3 section) per
Phase 0 of the spec:
https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html

Confirmed endpoints used here:
  GET    /stats/switches                -> [dpid, ...]
  GET    /stats/flow/<dpid>             -> {dpid: [ {table_id, priority,
                                            match, actions, packet_count,
                                            byte_count, ...}, ... ]}
  GET    /stats/aggregateflow/<dpid>    -> {dpid: [{packet_count,
                                            byte_count, flow_count}]}
  GET    /stats/port/<dpid>             -> {dpid: [ {port_no, rx_packets,
                                            tx_packets, rx_bytes, tx_bytes,
                                            rx_dropped, tx_dropped,
                                            rx_errors, tx_errors, ...}, ..]}
  GET    /stats/portdesc/<dpid>         -> {dpid: [ {port_no, hw_addr,
                                            name, curr_speed, ...}, ... ]}
  POST   /stats/flowentry/add           <- {dpid, priority, match, actions}
  POST   /stats/flowentry/modify        <- same body as add
  POST   /stats/flowentry/delete        <- {dpid, match, ...}
  DELETE /stats/flowentry/clear/<dpid>
  POST   /stats/meterentry/add          <- {dpid, meter_id, flags, bands}
  POST   /stats/meterentry/delete       <- {dpid, meter_id}

All of the above were hand-verified with curl against a live
`ryu-manager ryu.app.ofctl_rest ryu.app.simple_switch_13` + Mininet pair
before this client was written (Phase 0 recon step).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

import config

log = logging.getLogger("ryu_client")

_BASE = config.RYU_REST_BASE
_TIMEOUT = 5


class RyuClientError(RuntimeError):
    pass


def _get(path: str) -> Any:
    resp = requests.get(f"{_BASE}{path}", timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict) -> Any:
    resp = requests.post(f"{_BASE}{path}", json=body, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def _delete(path: str) -> Any:
    resp = requests.delete(f"{_BASE}{path}", timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------

def get_switches() -> list[int]:
    """GET /stats/switches -> list of connected dpids."""
    return _get("/stats/switches")


def get_flow_stats(dpid: int) -> list[dict]:
    """GET /stats/flow/<dpid> -> list of per-flow stat dicts."""
    data = _get(f"/stats/flow/{dpid}")
    return data.get(str(dpid), [])


def get_aggregate_stats(dpid: int) -> dict:
    """GET /stats/aggregateflow/<dpid> -> single aggregate stat dict."""
    data = _get(f"/stats/aggregateflow/{dpid}")
    entries = data.get(str(dpid), [])
    return entries[0] if entries else {"packet_count": 0, "byte_count": 0, "flow_count": 0}


def get_port_stats(dpid: int) -> list[dict]:
    """GET /stats/port/<dpid> -> list of per-port stat dicts."""
    data = _get(f"/stats/port/{dpid}")
    return data.get(str(dpid), [])


def get_port_desc(dpid: int) -> list[dict]:
    """GET /stats/portdesc/<dpid> -> list of per-port description dicts."""
    data = _get(f"/stats/portdesc/{dpid}")
    return data.get(str(dpid), [])


def get_state() -> dict:
    """
    Pull current network state across every connected switch.

    Returns a plain-dict snapshot:
        {
          "switches": {
             "<dpid>": {
                "flows": [...],          # get_flow_stats
                "aggregate": {...},      # get_aggregate_stats
                "ports": [...],          # get_port_stats, one entry per port
             },
             ...
          }
        }

    This is intentionally close to the raw ofctl_rest shapes so nothing
    is lost before it reaches the LLM prompt / reward computation; higher
    level derived metrics (throughput deltas, loss %, link utilization %)
    are computed by the caller across two consecutive get_state() calls,
    since ofctl_rest itself only exposes cumulative counters.
    """
    state = {"switches": {}}
    for dpid in get_switches():
        try:
            state["switches"][str(dpid)] = {
                "flows": get_flow_stats(dpid),
                "aggregate": get_aggregate_stats(dpid),
                "ports": get_port_stats(dpid),
            }
        except requests.RequestException as exc:
            log.warning("get_state: failed to pull dpid=%s (%s)", dpid, exc)
    return state


# ---------------------------------------------------------------------------
# Write side — flow-mods
# ---------------------------------------------------------------------------

def add_flow(dpid: int, match: dict, actions: list[dict], priority: int = 100,
             idle_timeout: int = 0, hard_timeout: int = 0, cookie: int = 0) -> dict:
    """POST /stats/flowentry/add"""
    body = {
        "dpid": dpid,
        "cookie": cookie,
        "table_id": 0,
        "priority": priority,
        "idle_timeout": idle_timeout,
        "hard_timeout": hard_timeout,
        "match": match,
        "actions": actions,
    }
    return _post("/stats/flowentry/add", body)


def modify_flow(dpid: int, match: dict, actions: list[dict], priority: int = 100,
                 cookie: int = 0) -> dict:
    """POST /stats/flowentry/modify"""
    body = {
        "dpid": dpid,
        "cookie": cookie,
        "table_id": 0,
        "priority": priority,
        "match": match,
        "actions": actions,
    }
    return _post("/stats/flowentry/modify", body)


def delete_flow(dpid: int, match: dict, cookie: int = 0) -> dict:
    """POST /stats/flowentry/delete"""
    body = {"dpid": dpid, "cookie": cookie, "match": match}
    return _post("/stats/flowentry/delete", body)


def clear_flows(dpid: int) -> dict:
    """DELETE /stats/flowentry/clear/<dpid>"""
    return _delete(f"/stats/flowentry/clear/{dpid}")


# ---------------------------------------------------------------------------
# Write side — meters (used to implement the "rate_limit" agent action)
# ---------------------------------------------------------------------------

def add_meter(dpid: int, meter_id: int, rate_kbps: int, burst_kbps: int | None = None) -> dict:
    """
    POST /stats/meterentry/add — DROP band, KBPS-flagged meter.
    Attach it to a flow by including {"type": "METER", "meter_id": meter_id}
    in that flow's `actions` list on the next add_flow/modify_flow call.
    """
    band = {"type": "DROP", "rate": max(rate_kbps, config.SAFETY_MIN_RATE_LIMIT_KBPS)}
    if burst_kbps:
        band["burst_size"] = burst_kbps
    body = {
        "dpid": dpid,
        "flags": "KBPS",
        "meter_id": meter_id,
        "bands": [band],
    }
    return _post("/stats/meterentry/add", body)


def delete_meter(dpid: int, meter_id: int) -> dict:
    """POST /stats/meterentry/delete"""
    return _post("/stats/meterentry/delete", {"dpid": dpid, "meter_id": meter_id})
