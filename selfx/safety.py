"""
Phase 3 — the ONE hard-coded safety check the spec calls for.

This is deliberately NOT an LLM decision. It is a small, deterministic
guard that runs on every cycle between "the LLM picked an action" and
"install the flow-mod". If the check fails, the agent silently falls
back to no_op for that cycle (the LLM's choice is logged either way, so
the eval harness can tell how often the model proposed something unsafe).

Two concrete rules, both named directly in the spec:
  1. reject a rate_limit that would drop more than
     config.SAFETY_MAX_FLOW_DROP_PCT percent of the flow's current
     measured throughput.
  2. reject a reroute that would push the destination link above
     config.SAFETY_MAX_LINK_UTIL_PCT percent of its capacity.

no_op is always safe by construction.
"""

from dataclasses import dataclass

import config


@dataclass
class SafetyContext:
    action: str                              # "reroute" | "rate_limit" | "no_op"
    target_flow_rate_kbps: float = 0.0        # current measured throughput of the flow acted on
    proposed_rate_limit_kbps: float | None = None   # only meaningful for rate_limit
    target_link_capacity_kbps: float | None = None  # only meaningful for reroute
    target_link_current_kbps: float = 0.0     # existing load already on the candidate link


@dataclass
class SafetyResult:
    allowed: bool
    reason: str
    safe_action: str   # the action to actually install: `context.action` if allowed, else "no_op"


def check(context: SafetyContext) -> SafetyResult:
    if context.action == "no_op":
        return SafetyResult(True, "no_op is always safe", "no_op")

    if context.action == "rate_limit":
        return _check_rate_limit(context)

    if context.action == "reroute":
        return _check_reroute(context)

    return SafetyResult(False, f"unknown action '{context.action}'", "no_op")


def _check_rate_limit(ctx: SafetyContext) -> SafetyResult:
    if ctx.proposed_rate_limit_kbps is None or ctx.target_flow_rate_kbps <= 0:
        return SafetyResult(False, "missing rate_limit parameters", "no_op")

    if ctx.proposed_rate_limit_kbps < config.SAFETY_MIN_RATE_LIMIT_KBPS:
        return SafetyResult(
            False,
            f"proposed rate {ctx.proposed_rate_limit_kbps:.0f} kbps is below the "
            f"{config.SAFETY_MIN_RATE_LIMIT_KBPS} kbps floor",
            "no_op",
        )

    dropped_pct = max(
        0.0,
        100.0 * (ctx.target_flow_rate_kbps - ctx.proposed_rate_limit_kbps)
        / ctx.target_flow_rate_kbps,
    )
    if dropped_pct > config.SAFETY_MAX_FLOW_DROP_PCT:
        return SafetyResult(
            False,
            f"rate_limit would drop {dropped_pct:.1f}% of the flow's traffic "
            f"(> {config.SAFETY_MAX_FLOW_DROP_PCT}% limit)",
            "no_op",
        )
    return SafetyResult(True, f"rate_limit drops only {dropped_pct:.1f}%", "rate_limit")


def _check_reroute(ctx: SafetyContext) -> SafetyResult:
    if not ctx.target_link_capacity_kbps:
        return SafetyResult(False, "missing target link capacity", "no_op")

    projected_kbps = ctx.target_link_current_kbps + ctx.target_flow_rate_kbps
    projected_util_pct = 100.0 * projected_kbps / ctx.target_link_capacity_kbps

    if projected_util_pct > config.SAFETY_MAX_LINK_UTIL_PCT:
        return SafetyResult(
            False,
            f"reroute would push the target link to {projected_util_pct:.1f}% "
            f"utilization (> {config.SAFETY_MAX_LINK_UTIL_PCT}% limit)",
            "no_op",
        )
    return SafetyResult(True, f"target link would sit at {projected_util_pct:.1f}%", "reroute")
