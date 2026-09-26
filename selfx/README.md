# sdn-self-improving-agent

A single LLM agent that watches an emulated SDN, decides between three
flow actions (`reroute`, `rate_limit`, `no_op`), and gets measurably
better over one run through in-context reflection + few-shot memory —
no fine-tuning, no formal control theory. Standalone MVP track; see
[Non-goals](#non-goals) for what this deliberately does *not* include.

## Repo structure

```
sdn-self-improving-agent/
├── config.py            # every tunable knob (topology, traffic, safety, reward, LLM)
├── topo.py               # Mininet topology (Phase 1)
├── traffic_gen.py         # iperf3 steady load + seeded bursty/elephant-flow generator (Phase 1)
├── ryu_client.py          # get_state() + flow-mod/meter wrapper over ofctl_rest (Phase 2)
├── latency_probe.py       # ping-based RTT probe (ofctl_rest has no latency counter)
├── safety.py              # the ONE hard-coded safety check (Phase 3)
├── agent/
│   ├── graph.py            # LangGraph observe->decide->act->reflect state machine (Phase 3/4)
│   ├── schemas.py           # pydantic schemas the LLM must return
│   ├── prompts.py            # prompt templates (decide + reflect)
│   ├── memory.py              # JSON (state, action, outcome, reflection) store + pruning (Phase 4)
│   ├── reward.py               # weighted Δlatency/Δthroughput/Δloss reward (Phase 4)
│   └── metrics.py               # turns two get_state() snapshots into rates/utilization
├── eval/
│   ├── run_ablation.py    # runs A0 / A1 / A2 over identical seeded traffic (Phase 5)
│   └── plot_results.py     # turns the 3 CSVs into the comparison plots
├── tests/
│   ├── test_core.py         # safety/memory/reward/metrics — no Mininet/Ryu needed
│   └── test_graph.py         # full LangGraph cycle with a fake LLM — no live API key needed
├── requirements.txt
├── .env.example
└── README.md
```

## Prerequisites

This targets a real Linux host (bare metal or VM) with root access —
**it will not run inside a rootless/sandboxed container**, because
Mininet needs to create real network namespaces and Open vSwitch
bridges.

- Ubuntu 20.04+ (or the official Mininet VM)
- Open vSwitch + Mininet:
  ```
  sudo apt update
  sudo apt install -y openvswitch-switch mininet iperf3
  ```
- Ryu (pick ONE working install path — Ryu is unmaintained upstream and
  fussy about newer `eventlet`/`setuptools`; a dedicated virtualenv on
  Python 3.9 or 3.10 is the path of least resistance):
  ```
  python3.10 -m venv ~/.venvs/ryu
  source ~/.venvs/ryu/bin/activate
  pip install ryu
  ```
- A second, separate environment (any modern Python 3.10+) for the
  agent itself:
  ```
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env   # fill in ANTHROPIC_API_KEY
  ```

## Sanity-checking the agent logic without Mininet

`tests/` has two dependency-light self-checks that run anywhere (no
Mininet/Ryu, no live Anthropic key — the LLM and the network layer are
both faked):

```bash
python3 -m tests.test_core    # safety check, memory pruning/few-shot, reward, metrics
python3 -m tests.test_graph   # the full LangGraph cycle end-to-end
```

Useful for iterating on the agent logic itself before touching a real
testbed, and for CI. They are not a substitute for the real Phase 5
ablation run.

## Phase 0 — confirm the real ofctl_rest shapes (do this first)

Before trusting `ryu_client.py`, reproduce the recon step yourself:

```bash
# terminal 1 (ryu venv)
ryu-manager ryu.app.ofctl_rest ryu.app.simple_switch_13

# terminal 2 (root)
sudo python3 topo.py     # drops you into the Mininet CLI once switches connect

# terminal 3
curl http://localhost:8080/stats/switches
curl http://localhost:8080/stats/flow/1
curl http://localhost:8080/stats/port/1
curl -X POST -d '{"dpid":1,"priority":100,"match":{"in_port":1},"actions":[{"type":"OUTPUT","port":2}]}' \
     http://localhost:8080/stats/flowentry/add
curl http://localhost:8080/stats/flow/1   # confirm the new entry shows up
```

`ryu_client.py`'s docstring records the exact response/request shapes
this project was built against
(https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html) — the curl
commands above should match it. If your Ryu/OVS version disagrees,
fix `ryu_client.py` before moving on.

## Running it by hand (one condition)

Ryu needs `ryu.app.simple_switch_13` loaded alongside `ofctl_rest` in
every condition — `simple_switch_13` supplies default L2 forwarding
(so traffic actually flows) while `ofctl_rest` exposes the stats/flow-mod
REST API the agent uses to install *higher-priority* overrides
(reroute / rate_limit) on top of that default forwarding.

```bash
# terminal 1 (ryu venv)
ryu-manager ryu.app.ofctl_rest ryu.app.simple_switch_13

# terminal 2 (root, agent venv activated so `python3` sees langgraph etc.)
sudo -E python3 topo.py
```

Then, from a third terminal (agent venv), drive one cycle manually to
sanity-check the graph:

```python
from agent.graph import AgentDeps, build_graph, run_cycle
from agent.memory import MemoryStore
from langchain_anthropic import ChatAnthropic

deps = AgentDeps(llm=ChatAnthropic(model="claude-sonnet-4-6"),
                  memory=MemoryStore(path="scratch_memory.json"))
app = build_graph(deps)
result = run_cycle(app, cycle=0, raw_state_prev=None)
print(result["installed_action"], result["reward"], result["reflection"])
```

## Running the full A0/A1/A2 ablation

```bash
sudo -E python3 -m eval.run_ablation --duration 600
python3 -m eval.plot_results
```

- `--duration` is seconds per condition; the acceptance criterion is
  an unattended run of **at least 10 minutes (600s)** per condition,
  which is also `config.RUN_DURATION_SEC`'s default.
- Each condition gets a fresh Mininet net and a `clear_flows()` sweep,
  but reuses the exact same `config.TRAFFIC_SEED`, so A0/A1/A2 all see
  byte-for-byte the same steady load + elephant-flow schedule.
- Output: `eval/logs/{A0,A1,A2}.csv`, then
  `eval/plots/{latency,throughput,loss}_comparison.png` and
  `eval/plots/reward_trend.png`.

## What "working" looks like (acceptance criteria)

- [ ] A full `run_ablation.py --duration 600` pass completes for all
      three conditions without crashing.
- [ ] `eval/plots/reward_trend.png` shows A2's rolling-mean reward
      trending up from the first few cycles to the last few — that
      rolling mean, not any single cycle, is the actual proof the
      reflection loop is working, since individual cycles are noisy.
- [ ] The three `*_comparison.png` plots show A0 vs A1 vs A2 for
      latency, throughput and loss.
- [ ] This README (you're reading it).

## Design notes / where this deviates from a literal reading of ofctl_rest

- **Latency** isn't exposed by any ofctl_rest counter, so
  `latency_probe.py` runs a small `ping` between the two steady-traffic
  endpoints each cycle and that RTT feeds the reward's Δlatency term.
  Throughput and loss come straight from `get_state()`'s cumulative
  port counters, differenced between consecutive snapshots.
- **`rate_limit`** is implemented with an OpenFlow 1.3 meter
  (`POST /stats/meterentry/add` with a `DROP` band) referenced from the
  flow's `actions` list — this is the standard ofctl_rest-native way to
  cap a flow's rate without reaching outside the OpenFlow API (e.g. no
  `ovs-vsctl`/`tc` calls).
- **A1 vs A2**: both run the identical LangGraph agent; the only
  difference is `MemoryStore(enabled=False)` for A1, which makes
  `few_shot_examples()` always return `[]` and `add_record()` a no-op.
  So A1 isolates "does having an LLM agent in the loop at all help"
  from A2's "does the reflection+memory loop specifically help".

## Non-goals

Per the spec, this track deliberately does **not** include: multi-agent
decomposition, LoRA/weight fine-tuning, a Lyapunov drift-plus-penalty
controller or any formal stability proof, or multi-topology
generalization testing. Those belong to the separate, bigger `SELF-X`
proposal for the same course project.
