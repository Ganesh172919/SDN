"""Tunable limits for the slow loop. The fast tick does not learn."""

WEIGHT_KEYS = ("latency", "throughput", "loss", "energy", "resource")
ACTIONS = ("reroute", "rate_limit", "admit", "drop")
ROLES = ("flow_sizing", "routing", "anomaly", "security", "slicing")

V_MIN = 1.0
V_MAX = 100.0
V_MAX_STEP = 20.0
WEIGHT_MAX_STEP = 0.20
WEIGHT_SUM_TOL = 1e-3

# Telemetry is "healthy" when the gate should not newly enable drop.
HEALTHY_LOSS_PCT = 1.0
HEALTHY_QUEUE_MBIT = 0.15
HEALTHY_LATENCY_MS = 25.0

# Reject a proposal when similar past outcomes got much slower and loss
# was not the problem the update was fixing.
LATENCY_REGRESSION_MS = 15.0
SLA_LOSS_PCT = 2.0
SLA_LATENCY_MS = 40.0

TICK_SEC = 0.1
WINDOW_SEC = 60.0
TICKS_PER_WINDOW = int(WINDOW_SEC / TICK_SEC)

# s2-s3 paths from the existing Mininet topology.
PATH_A_MBPS = 10.0
PATH_B_MBPS = 10.0
PATH_A_DELAY_MS = 5.0
PATH_B_DELAY_MS = 12.0
# 40 packets * 1500 bytes, the topology's max_queue_size.
MAX_QUEUE_MBIT = 40 * 1500 * 8 / 1_000_000

REPLAY_CAPACITY = 200

# Fixed evaluation weights. Controller weights are separate, so a policy
# is not graded by the objective it chose for itself.
EVAL_WEIGHTS = {
    "latency": 0.35,
    "throughput": 0.20,
    "loss": 0.25,
    "energy": 0.10,
    "resource": 0.10,
}
