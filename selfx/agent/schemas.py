"""
Structured-output schemas for the two LLM calls in the loop:
  1. decide  -> DecisionOutput   (exactly one of 3 actions + rationale)
  2. reflect -> ReflectionOutput (a single-sentence reflection)

Used with ChatAnthropic.with_structured_output() so LangChain handles
the tool-call formatting; graph.py still runs its own validation pass
on top (Phase 3: "validate and retry once on malformed output before
falling back to no_op") in case the model returns an action outside
the fixed 3-action vocabulary or omits a required parameter.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

import config


class DecisionOutput(BaseModel):
    action: Literal["reroute", "rate_limit", "no_op"] = Field(
        description="Exactly one of the three allowed actions."
    )
    target_dpid: Optional[int] = Field(
        default=None, description="Datapath ID the action applies to, if any."
    )
    target_flow_match: Optional[dict] = Field(
        default=None,
        description="OpenFlow match dict identifying the flow this action targets "
        "(e.g. {'in_port': 1, 'eth_type': 2048, 'ipv4_dst': '10.0.0.8'}).",
    )
    reroute_out_port: Optional[int] = Field(
        default=None, description="For action='reroute': the new output port."
    )
    rate_limit_kbps: Optional[int] = Field(
        default=None, description="For action='rate_limit': the proposed ceiling in kbps."
    )
    rationale: str = Field(description="One-line rationale for this decision.")

    def is_well_formed(self) -> bool:
        """Extra structural checks beyond what the schema/type system enforces."""
        if self.action not in config.ACTIONS:
            return False
        if self.action == "reroute" and (
            self.target_dpid is None
            or self.target_flow_match is None
            or self.reroute_out_port is None
        ):
            return False
        if self.action == "rate_limit" and (
            self.target_dpid is None
            or self.target_flow_match is None
            or self.rate_limit_kbps is None
        ):
            return False
        return True


class ReflectionOutput(BaseModel):
    reflection: str = Field(
        description="A single, concise sentence reflecting on whether the action helped."
    )
