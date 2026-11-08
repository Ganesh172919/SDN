# ONOS Methodology Cross-Check & Architectural Equivalence Mapping

**Course:** EC466 Software Defined Networks (IIIT Dharwad)  
**Project:** SELF-X: Autonomous Flow-Management Agent  
**Team:** SDN_07 | Author: Harsh Raj (23BDS076)  
**Target Controllers:** Ryu SDN Controller v4.34 vs. ONOS (Open Network Operating System) v2.7+  
**Southbound Standard:** OpenFlow v1.3 (RFC 7344 / ONF TS-025)

---

## 1. Executive Summary & Controller Neutrality

The EC466 Software Defined Networks project specification permits implementing network control planes with either Ryu or ONOS. The **SELF-X** architecture is intentionally decoupled into two operational timescales:
1. **Fast-Loop DPP Controller (100 ms):** Solves polynomial-time Lyapunov drift-plus-penalty queue optimizations.
2. **Slow-Loop Multi-Agent Governor (30–120 s):** Performs semantic root-cause analysis, intent decomposition, and weight/policy updates.

Crucially, **neither timescale directly binds to controller internal internals**. Instead, all network state inquiries and control mutations flow through the **`ActionGateway`** abstraction layer (`selfx/agent/action_gateway.py`). Because both Ryu and ONOS communicate with OpenFlow switches using the identical OpenFlow 1.3 wire protocol (ONF TS-025), SELF-X achieves full protocol portability.

This document establishes the precise architectural and operational equivalence between our reference Ryu testbed implementation and an enterprise ONOS deployment.

```
                      +-----------------------------------+
                      |       SELF-X Multi-Agent Core     |
                      |   (6-Agent Governor & Lyapunov)   |
                      +-----------------+-----------------+
                                        |
                             ActionGateway Abstraction
                                        |
               +------------------------+------------------------+
               |                                                 |
      [ Ryu Controller v4.34 ]                         [ ONOS Controller v2.7+ ]
   - Python 3 Async Framework                       - Java OSGi Distributed Core
   - ofctl_rest REST API                             - FlowObjective / Meter Subsystem
   - Port 8080 (REST) / 6653 (OF)                    - Port 8181 (REST) / 6653 (OF)
               |                                                 |
               +------------------------+------------------------+
                                        |
                           OpenFlow 1.3 Wire Protocol
                           (TCP:6653, Match / Actions)
                                        |
                          +-------------+-------------+
                          |   Open vSwitch (OVS 2.13) |
                          +---------------------------+
```

---

## 2. Architectural Subsystem Mapping

| Functional Layer | Ryu Reference Implementation (`selfx`) | ONOS Equivalent Subsystem |
| :--- | :--- | :--- |
| **Control Core** | `ryu.base.app_manager.RyuApp` (Python event loop) | OSGi Bundles running on Apache Karaf / Atomix cluster |
| **Southbound Protocol** | `ryu.ofproto.ofproto_v1_3` & `ofproto_v1_3_parser` | `org.onosproject.openflow` Southbound Provider |
| **Northbound REST API** | `ryu.app.ofctl_rest` (JSON over HTTP, default port 8080) | `org.onosproject.rest` Northbound API (Swagger/REST, port 8181) |
| **Flow Management** | `/stats/flowentry/add`, `/stats/flowentry/delete` | `/onos/v1/flows/{deviceId}` (FlowRuleManager / FlowObjective) |
| **Meter Management** | `/stats/meterentry/add`, `/stats/meterentry/delete` | `/onos/v1/meters/{deviceId}` (MeterManager / MeterProvider) |
| **Topology Discovery** | `ryu.topology.switches` (LLDP / BDDP packet injection) | ONOS Topology Subsystem (`DeviceManager`, `LinkManager`) |
| **Port & Queue Telemetry**| `/stats/port/{dpid}`, `/stats/queue/{dpid}` | `/onos/v1/devices/{deviceId}/portStats`, Device Service |
| **Rule Recovery / Audit** | Readback via `/stats/flow/{dpid}` | Readback via `/onos/v1/flows/{deviceId}?state=ADDED` |

---

## 3. Southbound OpenFlow 1.3 Wire Equivalence

Both Ryu and ONOS compile high-level flow and meter intents into byte-identical OpenFlow 1.3 message frames across TCP port 6653.

```
OpenFlow 1.3 Frame Structure (Wire Level):
+----------------+----------------+----------------+----------------+
|  version (0x04)|   type (0x0E)  |          length (16 bits)       |
+----------------+----------------+----------------+----------------+
|                          xid (32 bits)                            |
+----------------+----------------+----------------+----------------+
|                      cookie (64-bit identifier)                   |
+----------------+----------------+----------------+----------------+
|  table_id (0)  |  command (ADD) |   idle_timeout |   hard_timeout |
+----------------+----------------+----------------+----------------+
|    priority    | buffer_id (NO) |    out_port    |    out_group   |
+----------------+----------------+----------------+----------------+
|              flags              |            pad (16 bits)        |
+----------------+----------------+----------------+----------------+
|                     Match Structure (OXM TLVs)                    |
+-------------------------------------------------------------------+
|                     Instructions / Action List                    |
+-------------------------------------------------------------------+
```

Because Open vSwitch (OVS 2.13.0) executes identical TCAM lookups and hardware flow tables regardless of whether the `OFPT_FLOW_MOD` frame originated from Ryu's Python socket or ONOS's Netty Java pipeline, **datapath execution dynamics, queue latencies, and packet drops remain mathematically invariant across controllers**.

---

## 4. Exact Side-by-Side Payload Translation

### 4.1 Reroute Flow Rule (Match IP & Forward to Port)

#### Scenario
Redirect IPv4 traffic matching destination `10.0.0.2/32` entering Switch 1 to egress Port 2 with priority 500.

#### Ryu REST API (`ofctl_rest`)
- **Endpoint:** `POST http://127.0.0.1:8080/stats/flowentry/add`
- **Payload:**
```json
{
  "dpid": 1,
  "cookie": 11223344,
  "table_id": 0,
  "priority": 500,
  "idle_timeout": 60,
  "hard_timeout": 120,
  "match": {
    "eth_type": 2048,
    "ipv4_dst": "10.0.0.2"
  },
  "actions": [
    {
      "type": "OUTPUT",
      "port": 2
    }
  ]
}
```

#### ONOS REST API (`onos/v1/flows`)
- **Endpoint:** `POST http://127.0.0.1:8181/onos/v1/flows/of:0000000000000001?appId=org.selfx.sdn`
- **Payload:**
```json
{
  "priority": 500,
  "timeout": 60,
  "isPermanent": false,
  "deviceId": "of:0000000000000001",
  "treatment": {
    "instructions": [
      {
        "type": "OUTPUT",
        "port": "2"
      }
    ]
  },
  "selector": {
    "criteria": [
      {
        "type": "ETH_TYPE",
        "ethType": "0x0800"
      },
      {
        "type": "IPV4_DST",
        "ip": "10.0.0.2/32"
      }
    ]
  }
}
```

---

### 4.2 Meter Rate-Limiting Entry

#### Scenario
Install an OpenFlow 1.3 Meter on Switch 1 (Meter ID 1) to drop traffic exceeding 12,000 kbps (12 Mbps) with a 1,024 kb burst.

#### Ryu REST API (`ofctl_rest`)
- **Endpoint:** `POST http://127.0.0.1:8080/stats/meterentry/add`
- **Payload:**
```json
{
  "dpid": 1,
  "meter_id": 1,
  "flags": ["KBPS", "BURST"],
  "bands": [
    {
      "type": "DROP",
      "rate": 12000,
      "burst_size": 1024
    }
  ]
}
```

#### ONOS REST API (`onos/v1/meters`)
- **Endpoint:** `POST http://127.0.0.1:8181/onos/v1/meters/of:0000000000000001`
- **Payload:**
```json
{
  "deviceId": "of:0000000000000001",
  "unit": "KB_PER_SEC",
  "burst": true,
  "bands": [
    {
      "type": "DROP",
      "rate": 1500,
      "burstSize": 128,
      "prec": 0
    }
  ]
}
```
*(Note: ONOS specifies `KB_PER_SEC` [kilobytes per second], requiring a $1/8$ factor translation from Ryu's `KBPS` [kilobits per second]).*

---

## 5. Gateway Driver Translation Implementation

In `selfx/agent/action_gateway.py`, the driver can toggle between Ryu and ONOS with zero modifications to the core agent logic:

```python
class ONOSActionDriver:
    """Translates high-level ActionGateway actions to ONOS REST endpoints."""
    def __init__(self, base_url="http://127.0.0.1:8181", app_id="org.selfx.sdn"):
        self.base_url = base_url
        self.app_id = app_id

    def install_reroute(self, dpid: int, match_ip: str, out_port: int, priority: int = 500):
        device_id = f"of:{dpid:016x}"
        url = f"{self.base_url}/onos/v1/flows/{device_id}?appId={self.app_id}"
        payload = {
            "priority": priority,
            "timeout": 60,
            "isPermanent": False,
            "deviceId": device_id,
            "treatment": {"instructions": [{"type": "OUTPUT", "port": str(out_port)}]},
            "selector": {
                "criteria": [
                    {"type": "ETH_TYPE", "ethType": "0x0800"},
                    {"type": "IPV4_DST", "ip": f"{match_ip}/32"}
                ]
            }
        }
        return self._post_json(url, payload)
```

---

## 6. Practical Rationale for Ryu in EC466

While ONOS is standard for carrier-grade multi-cluster topologies, **Ryu was chosen as the primary testbed controller for SELF-X** for four decisive engineering reasons:

1. **Lightweight Python Co-Location:**
   Ryu runs natively within Python 3.9+, enabling the multi-agent framework to interface via low-latency local sockets without JVM inter-process memory overhead (ONOS JVM typically consumes 3–4 GB RAM vs. Ryu's 65 MB).
2. **Deterministic Startup & Reset:**
   Mininet automated regression tests (`run_acceptance_suite.py`) require tearing down and restarting the control plane within <2 seconds. Ryu boots in 450 ms; ONOS Karaf container initialization requires 25–45 seconds per run.
3. **Exact OpenFlow 1.3 Transparency:**
   Ryu provides direct 1:1 exposure of the OpenFlow 1.3 protocol structs without ONOS's intermediate compiler abstractions (Intent Framework / Pipeliner), ensuring that mathematically derived Lyapunov control rules are mapped directly to physical switch flow tables.
4. **Reproducibility on Standard Evaluation Workstations:**
   Examiners, students, and peer reviewers can execute the entire SELF-X pipeline on standard consumer laptops or Linux VMs without Docker daemon or Java SDK dependencies.

---

## 7. Conclusion

The mathematical proofs, Lyapunov drift bounds, two-timescale convergence guarantees, and LoRA weight adaptations demonstrated in SELF-X are **controller-agnostic**. Transitioning from Ryu to ONOS requires solely switching the REST endpoint formatting in `selfx/agent/action_gateway.py` with zero alterations to the underlying decision or optimization engines.

