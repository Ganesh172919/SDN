"""
Central configuration for the self-improving SDN flow-management agent.

Every tunable knob mentioned in the project spec lives here so the
topology, traffic generator, agent, safety check and eval harness all
agree on the same numbers.
"""

import os

# ---------------------------------------------------------------------------
# Ryu / OpenFlow
# ---------------------------------------------------------------------------
RYU_REST_HOST = os.environ.get("RYU_REST_HOST", "127.0.0.1")
RYU_REST_PORT = int(os.environ.get("RYU_REST_PORT", "8080"))
RYU_REST_BASE = f"http://{RYU_REST_HOST}:{RYU_REST_PORT}"
OF_VERSION = "OpenFlow13"

# ---------------------------------------------------------------------------
# Topology (Phase 1) — linear: h1,h2 - s1 - s2 - s3 - s4 - h7,h8
# ---------------------------------------------------------------------------
NUM_SWITCHES = 4
NUM_HOSTS = 8
HOSTS_PER_SWITCH = NUM_HOSTS // NUM_SWITCHES
LINK_BW_MBPS = 10          # Mininet link bandwidth used for every inter-switch link
LINK_DELAY_MS = "2ms"
LINK_LOSS_PCT = 0           # base loss; traffic_gen / link failures are what create loss

# ---------------------------------------------------------------------------
# Traffic generation (Phase 1)
# ---------------------------------------------------------------------------
TRAFFIC_SEED = 1729                     # fixed seed -> reproducible run across A0/A1/A2
IPERF_STEADY_MBPS = 3                   # background steady load per steady flow
IPERF_STEADY_DURATION_SEC = 600         # long-lived, spans the whole run
BURST_MIN_INTERVAL_SEC = 20
BURST_MAX_INTERVAL_SEC = 45
BURST_MIN_MBPS = 8
BURST_MAX_MBPS = 15
BURST_MIN_DURATION_SEC = 4
BURST_MAX_DURATION_SEC = 10

# ---------------------------------------------------------------------------
# Control loop (Phase 3)
# ---------------------------------------------------------------------------
CONTROL_LOOP_INTERVAL_SEC = 5    # N seconds, per spec
RUN_DURATION_SEC = 600           # >= 10 minutes unattended, per acceptance criteria
NUM_CYCLES = RUN_DURATION_SEC // CONTROL_LOOP_INTERVAL_SEC

ACTIONS = ("reroute", "rate_limit", "no_op")
MALFORMED_OUTPUT_MAX_RETRIES = 1   # "validate and retry once on malformed output"

# ---------------------------------------------------------------------------
# Safety check (hard-coded, Phase 3) — this is NOT the LLM's decision to make
# ---------------------------------------------------------------------------
SAFETY_MAX_FLOW_DROP_PCT = 20      # reject an action if it would drop >20% of a flow's traffic
SAFETY_MAX_LINK_UTIL_PCT = 90      # reject an action if it would push a link over 90% of capacity
SAFETY_MIN_RATE_LIMIT_KBPS = 512   # a rate_limit action may never throttle a link below this

# ---------------------------------------------------------------------------
# Reflection & memory (Phase 4)
# ---------------------------------------------------------------------------
MEMORY_PATH = os.environ.get("SDN_AGENT_MEMORY_PATH", "agent_memory.json")
MEMORY_MAX_ENTRIES = 30
FEWSHOT_MIN_EXAMPLES = 5
FEWSHOT_MAX_EXAMPLES = 10

# reward = weighted combination of the (normalized) per-cycle deltas
REWARD_WEIGHT_LATENCY = -0.4     # latency increase is bad
REWARD_WEIGHT_THROUGHPUT = 0.4   # throughput increase is good
REWARD_WEIGHT_LOSS = -0.2        # loss increase is bad

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL = os.environ.get("SDN_AGENT_MODEL", "claude-sonnet-4-6")
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 1024

# ---------------------------------------------------------------------------
# Evaluation harness (Phase 5)
# ---------------------------------------------------------------------------
CONDITIONS = ("A0", "A1", "A2")
# A0: static Ryu, no agent
# A1: agent runs, but memory is disabled / wiped every cycle (no few-shot, no reflection carried forward)
# A2: agent runs with full reflection + memory loop
EVAL_LOG_DIR = "eval/logs"
EVAL_PLOT_DIR = "eval/plots"
