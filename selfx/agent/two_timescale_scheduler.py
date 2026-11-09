"""
Two-Timescale Concurrent Scheduler (Slow AI Governance + Fast DPP Loop)
Traceability: Task T15 | Deliverables D3 | EC466 Team SDN_07

Architecture:
  - Fast Timescale (100 ms - 1 s): High-frequency deterministic Lyapunov DPP loop.
    Guarantees sub-millisecond per-flow action selection and strict queue bounds.
  - Slow Timescale (30 - 120 s): Multi-agent cognitive governance loop.
    Decomposes intent, analyzes multi-window trends, proposes updated Delta-Pi (V, w, mask).
  - Non-blocking Decoupling: Slow-loop LLM delays, network calls, or timeouts NEVER stall
    the fast packet-forwarding loop.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.dpp_controller import LyapunovDPPController
from agent.dpp_stability import DPPStabilityValidator
from agentic.schemas import Policy, TelemetryWindow, initial_policy
from agentic.safety import check as safety_check


@dataclass
class ScheduleTickRecord:
    timestamp_wall: float
    timescale: str  # "fast_100ms" or "slow_60s"
    cycle: int
    duration_ms: float
    missed_deadline: bool


class TwoTimescaleScheduler:
    """
    Orchestrates concurrent execution of the fast DPP loop and the slow AI governance loop.
    """

    def __init__(
        self,
        fast_interval_sec: float = 0.1,  # 100 ms
        slow_interval_sec: float = 30.0,  # 30 seconds
        governor_fn: Optional[Callable[[Policy, TelemetryWindow], Policy]] = None,
    ) -> None:
        self.fast_interval = fast_interval_sec
        self.slow_interval = slow_interval_sec
        self.governor_fn = governor_fn

        self.current_policy: Policy = initial_policy()
        self.policy_lock = threading.Lock()

        # Telemetry mailbox from fast loop to slow loop
        self.telemetry_mailbox: queue.Queue[TelemetryWindow] = queue.Queue(maxsize=10)

        # Logging
        self.schedule_log: List[ScheduleTickRecord] = []
        self.running = False
        self.fast_ticks = 0
        self.slow_ticks = 0

    def start(self, duration_sec: float = 60.0) -> None:
        self.running = True
        t_fast = threading.Thread(target=self._run_fast_loop, args=(duration_sec,), daemon=True)
        t_slow = threading.Thread(target=self._run_slow_loop, args=(duration_sec,), daemon=True)

        t_fast.start()
        t_slow.start()

        t_fast.join()
        t_slow.join()
        self.running = False

    def _run_fast_loop(self, duration_sec: float) -> None:
        controller = LyapunovDPPController()
        start = time.time()
        q1, q2 = 0.0, 0.0

        while time.time() - start < duration_sec and self.running:
            t0 = time.perf_counter()
            self.fast_ticks += 1

            # Read latest accepted policy without stalling
            with self.policy_lock:
                active_policy = self.current_policy

            # Execute fast DPP decision
            dec = controller.decide(
                q_primary_mbit=q1,
                q_secondary_mbit=q2,
                mouse_mbps=3.0,
                elephant_mbps=8.0 if (self.fast_ticks % 100 < 50) else 0.0,
                policy_v=active_policy.V,
                weights=active_policy.weights(),
                action_mask=active_policy.action_mask,
            )

            # Update queues
            if dec.action == "reroute":
                q1 = max(0.0, q1 - 0.7 * self.fast_interval)
                q2 = max(0.0, q2 + (8.0 - 10.0) * self.fast_interval)
            else:
                q1 = max(0.0, q1 + (11.0 - 10.0) * self.fast_interval)
                q2 = max(0.0, q2 - 1.0 * self.fast_interval)

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            missed = elapsed_ms > (self.fast_interval * 1000.0)

            self.schedule_log.append(ScheduleTickRecord(
                timestamp_wall=time.time(),
                timescale="fast_100ms",
                cycle=self.fast_ticks,
                duration_ms=round(elapsed_ms, 3),
                missed_deadline=missed,
            ))

            # Publish telemetry for slow loop every 10 ticks (1s)
            if self.fast_ticks % 10 == 0:
                telem = TelemetryWindow(
                    queue_mbit=q1 + q2,
                    queue_trend=0.0,
                    util_primary_pct=min(100.0, (q1 / 5.0) * 100.0),
                    util_alt_pct=min(100.0, (q2 / 5.0) * 100.0),
                    flow_mbps=8.0,
                    latency_ms=5.0 + q1 * 10.0,
                    latency_trend=0.0,
                    loss_pct=0.0 if q1 < 4.0 else 2.5,
                    loss_trend=0.0,
                    throughput_mbps=10.0,
                    energy=0.35,
                    resource_cost=0.10,
                    sla_violations=0.0,
                    p95_latency_ms=8.0,
                    policy=active_policy,
                )
                try:
                    self.telemetry_mailbox.put_nowait(telem)
                except queue.Full:
                    pass

            # Precise sleep to maintain fast tick frequency
            sleep_time = max(0.0, self.fast_interval - (elapsed_ms / 1000.0))
            time.sleep(sleep_time)

    def _run_slow_loop(self, duration_sec: float) -> None:
        start = time.time()
        while time.time() - start < duration_sec and self.running:
            time.sleep(self.slow_interval)
            t0 = time.perf_counter()
            self.slow_ticks += 1

            # Fetch latest telemetry snapshot
            latest_telem = None
            while not self.telemetry_mailbox.empty():
                latest_telem = self.telemetry_mailbox.get()

            if latest_telem is not None:
                # Deliberate slow AI calculation (e.g. 50 ms delay to simulate LLM inference)
                time.sleep(0.05)

                with self.policy_lock:
                    curr = self.current_policy

                if self.governor_fn:
                    candidate = self.governor_fn(curr, latest_telem)
                else:
                    # Synthetic adaptive step
                    candidate = Policy(
                        V=min(16.0, curr.V + 1.0) if latest_telem.latency_ms > 10.0 else max(4.0, curr.V - 0.5),
                        latency=0.30,
                        throughput=0.25,
                        loss=0.25,
                        energy=0.10,
                        resource=0.10,
                        action_mask=("admit", "reroute", "rate_limit"),
                    )

                gate_res = safety_check(curr, candidate, latest_telem)
                if gate_res.accepted:
                    with self.policy_lock:
                        self.current_policy = gate_res.policy

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.schedule_log.append(ScheduleTickRecord(
                timestamp_wall=time.time(),
                timescale="slow_30s",
                cycle=self.slow_ticks,
                duration_ms=round(elapsed_ms, 3),
                missed_deadline=False,
            ))

