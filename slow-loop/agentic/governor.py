"""One slow-loop cycle: propose ΔΠ, gate it, then let RL take a clipped step."""

from __future__ import annotations

import json
import time

from agentic.agents import merge_opinions, parse_opinion, parse_policy_text
from agentic.config import ROLES
from agentic.model_client import ModelClient, strip_json_fence
from agentic.prompts import build_role_messages
from agentic.replay import ReplayBuffer
from agentic.rl import blend, estimate_latency_delta, propose_baseline
from agentic.safety import check
from agentic.schemas import CycleResult, Policy, TelemetryWindow


class Governor:
    def __init__(self, client: ModelClient, buffer: ReplayBuffer) -> None:
        self.client = client
        self.buffer = buffer

    def step(self, telemetry: TelemetryWindow, policy: Policy, mode: str = "multi") -> CycleResult:
        if mode not in {"single", "multi"}:
            raise ValueError("mode must be 'single' or 'multi'")
        started = time.perf_counter()
        proposal, valid_json = self._propose(telemetry, policy, mode)
        estimate = estimate_latency_delta(self.buffer, telemetry)
        decision = check(policy, proposal, telemetry, estimate)

        if decision.accepted and proposal is not None:
            blended = blend(policy, proposal, telemetry, self.buffer)
            blended_decision = check(policy, blended, telemetry, estimate)
            if blended_decision.accepted:
                chosen = blended_decision.policy
                reason = decision.reason
                accepted = True
            else:
                chosen = proposal
                reason = decision.reason
                accepted = True
        else:
            baseline = propose_baseline(policy, telemetry, self.buffer)
            baseline_decision = check(policy, baseline, telemetry, estimate)
            changed = baseline_decision.policy.to_dict() != policy.to_dict()
            if baseline_decision.accepted and changed:
                chosen = baseline_decision.policy
                reason = f"llm proposal rejected ({decision.reason}); applied rl baseline"
                accepted = True
            else:
                chosen = policy
                reason = decision.reason
                accepted = False

        elapsed = time.perf_counter() - started
        return CycleResult(
            accepted=accepted,
            reason=reason,
            policy_before=policy,
            policy_after=chosen,
            proposal=proposal,
            governor_seconds=elapsed,
            valid_json=valid_json,
            mode=mode,
        )

    def _propose(
        self,
        telemetry: TelemetryWindow,
        policy: Policy,
        mode: str,
    ) -> tuple[Policy | None, bool]:
        if mode == "single":
            raw = self.client.complete(build_role_messages("single", telemetry, policy))
            try:
                return parse_policy_text(strip_json_fence(raw)), True
            except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                return None, False

        opinions = []
        for role in ROLES:
            raw = self.client.complete(build_role_messages(role, telemetry, policy))
            try:
                opinions.append(parse_opinion(strip_json_fence(raw)))
            except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                return None, False
        return merge_opinions(policy, opinions), True
