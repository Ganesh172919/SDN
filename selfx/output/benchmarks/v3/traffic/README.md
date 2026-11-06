# Synthetic NetFlow Traffic Records (Revision 3 Archive)

> **Schema Specification, Provenance Boundaries, Sampling Mechanics, Python Analysis Snippets, and Cryptographic Trace Lineage**  
> *Course Project — EC466: Software Defined Networks | Team ID: SDN_07*

---

## 📌 Dataset Overview & Provenance Boundaries

This directory contains `simulated_netflow.csv` for the **Revision 3 Benchmark Archive**, comprising **9,600 generated aggregate flow records** evaluated across 8 traffic scenarios and 10 held-out random seeds (1760–1769).

> [!IMPORTANT]
> **Strict Scientific Provenance Disclaimer**:
> These records represent **synthetic, 5-second interval NetFlow-style tabular observations** computed analytically from seeded traffic generator functions. They are **NOT** physical pcap packet traces, Linux socket dumps, or RFC 7011 IPFIX wire messages. The `provenance` field in every record explicitly declares `synthetic_aggregate_not_packet_capture`.

---

## 🧠 Colourful Pipeline Mindmap

```mermaid
flowchart TD
    classDef genNode fill:#1E88E5,stroke:#0D47A1,stroke-width:2px,color:#FFFFFF;
    classDef hashNode fill:#00897B,stroke:#004D40,stroke-width:2px,color:#FFFFFF;
    classDef flowNode fill:#FB8C00,stroke:#E65100,stroke-width:2px,color:#FFFFFF;
    classDef expNode fill:#8E24AA,stroke:#4A148C,stroke-width:2px,color:#FFFFFF;

    subgraph WORKLOAD ["1. Seeded Demand Generation (v3)"]
        SEED["Random Seed (1760..1769)<br/>Scenario Function"]:::genNode
        PHASE["Phase Cycling:<br/>Recurring / Volatile / Mixed"]:::genNode
        RATES["Continuous Rates (Mbps):<br/>primary, alternate, elephant"]:::genNode
        SEED --> PHASE
        PHASE --> RATES
    end

    subgraph INTEGRITY ["2. Cryptographic Digest Binding"]
        JSON_TRACE["JSON Trace File<br/>traffic_{scenario}_{seed}.json"]:::hashNode
        SHA["SHA256 Cryptographic Hash<br/>Stored in summary.json"]:::hashNode
        RATES --> JSON_TRACE
        JSON_TRACE --> SHA
    end

    subgraph AGGREGATION ["3. 5-Second NetFlow Synthesis"]
        WINDOW["Quantize 5000 ms Window<br/>start_ms -> end_ms"]:::flowNode
        BYTES["Byte Volume Conversion:<br/>Bytes = round(Rate * 1e6 * 5 / 8)"]:::flowNode
        CSV_OUT[("simulated_netflow.csv<br/>(9,600 Total Rows)")]:::flowNode
        JSON_TRACE --> WINDOW
        WINDOW --> BYTES
        BYTES --> CSV_OUT
    end

    subgraph BENCHMARK ["4. Downstream Evaluation"]
        EVAL_ENG["Analytical Fluid Simulator<br/>(86,400 Total Windows)"]:::expNode
        CSV_OUT --> EVAL_ENG
    end
```

---

## 🎨 Detailed ASCII Sampling Flow

```
====================================================================================================
                        5-SECOND NETFLOW QUANTIZATION TIMELINE (v3)
====================================================================================================

 Virtual Time Axis (Milliseconds):
 0 ms                5000 ms               10000 ms              15000 ms              20000 ms
 +---------------------+---------------------+---------------------+---------------------+
 |  Window 0 (Cycle 0) |  Window 1 (Cycle 1) |  Window 2 (Cycle 2) |  Window 3 (Cycle 3) |
 +---------------------+---------------------+---------------------+---------------------+
   |                     |                     |                     |
   v                     v                     v                     v
 [Flow Record 0]       [Flow Record 1]       [Flow Record 2]       [Flow Record 3]
 - id: flow-1760-0     - id: flow-1760-1     - id: flow-1760-2     - id: flow-1760-3
 - start: 0 ms         - start: 5000 ms      - start: 10000 ms     - start: 15000 ms
 - end:   5000 ms      - end:   10000 ms     - end:   15000 ms     - end:   20000 ms
 - bytes: Offered B    - bytes: Offered B    - bytes: Offered B    - bytes: Offered B
 - src: 10.0.0.1       - src: 10.0.0.1       - src: 10.0.0.1       - src: 10.0.0.1
 - dst: 10.0.0.8       - dst: 10.0.0.8       - dst: 10.0.0.8       - dst: 10.0.0.8

 Mathematical Conversion Identity:
   Elephant_Bytes_Offered = round( elephant_mbps * 1,000,000 [bits/Mb] * 5.0 [s] / 8 [bits/Byte] )
====================================================================================================
```

---

## 📋 Comprehensive Dataset Schema

Every row in `simulated_netflow.csv` satisfies the following typed record specification:

| Column Name | Data Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| **`scenario`** | `str` | `recurring` | Workload profile (`recurring`, `volatile`, `mixed`, etc.) |
| **`seed`** | `int` | `1760` | Pseudo-random seed governing the deterministic trial (1760–1769) |
| **`flow_id`** | `str` | `flow-1760-0` | Globally unique identifier for the elephant flow instance |
| **`start_virtual_ms`** | `int` | `0` | Simulation start timestamp in virtual milliseconds |
| **`end_virtual_ms`** | `int` | `5000` | Simulation end timestamp in virtual milliseconds (interval = 5000 ms) |
| **`logical_src`** | `str` | `10.0.0.1` | Simulated host IPv4 source address (Host `h1`) |
| **`logical_dst`** | `str` | `10.0.0.8` | Simulated host IPv4 destination address (Host `h8`) |
| **`elephant_bytes_offered`**| `int` | `885250` | Exact byte volume offered by the elephant flow over the window |
| **`primary_background_mbps`**| `float` | `3.1105` | Background non-elephant traffic occupying the primary link |
| **`alternate_background_mbps`**| `float` | `1.2633` | Background non-elephant traffic occupying the alternate link |
| **`provenance`** | `str` | `synthetic_aggregate_not_packet_capture` | Explicit audit tag certifying simulation origin |

---

## 🔗 Cross-Reference Navigation

- **Revision 3 Benchmark Guide**: [`selfx/docs/BENCHMARKS_V3.md`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/docs/BENCHMARKS_V3.md)
- **Revision 4 Traffic Specification**: [`selfx/output/benchmarks/v4/traffic/README.md`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/output/benchmarks/v4/traffic/README.md)
- **Parent Benchmark Portal**: [`selfx/output/benchmarks/README.md`](file:///c:/Users/RAVIPRAKASH/SDN/SDN/selfx/output/benchmarks/README.md)
