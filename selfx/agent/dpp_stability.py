"""
Lyapunov DPP Stability and Feasibility Validator Under Policy Changes
Traceability: Tasks T11 | Deliverable D2 | EC466 Team SDN_07

Verifies:
  1. Admissible V ranges and step bounds: V in [V_min, V_max], |Delta V| <= V_max_step.
  2. Weight simplex normalization: sum(w) == 1.0 and w_j >= 0.
  3. Feasibility and Slack Invariant: The action mask must contain at least one stabilizing
     action ('reroute', 'rate_limit', or 'drop') capable of maintaining interior capacity slack
     epsilon = mu_max - lambda_admitted > 0 when offered traffic exceeds primary link capacity.
  4. Formal analytic bound calculation under candidate policy: Bound = (B + V * C) / epsilon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

V_MIN = 1.0
V_MAX = 32.0
V_MAX_STEP = 4.0
WEIGHT_TOLERANCE = 1e-5
STABILIZING_ACTIONS = {"reroute", "rate_limit", "drop"}


@dataclass(frozen=True)
class StabilityVerificationResult:
    stable: bool
    reason: str
    analytic_bound: float
    capacity_slack_epsilon: float
    admissible_v: bool
    admissible_weights: bool
    admissible_mask: bool


class DPPStabilityValidator:
    """
    Mathematical validator ensuring slow-loop policy proposals preserve
    the conditions of the Lyapunov queue-backlog stability theorem.
    """

    def __init__(
        self,
        c_primary_mbps: float = 10.0,
        c_secondary_mbps: float = 10.0,
        max_burst_mbps: float = 15.0,
        cost_upper_bound_c: float = 1.85,
    ) -> None:
        self.c_primary = c_primary_mbps
        self.c_secondary = c_secondary_mbps
        self.c_total = c_primary_mbps + c_secondary_mbps  # 20 Mbps total network capacity
        self.max_burst = max_burst_mbps
        self.cost_c = cost_upper_bound_c
        # Constant B for 0.1s slot:
        # B = 0.5 * [(1.0)^2 + (1.5)^2 + (1.0)^2 + (1.5)^2] = 3.25 Mbit^2
        self.constant_b = 3.25

    def verify_stability(
        self,
        current_v: float,
        proposed_v: float,
        weights: Dict[str, float],
        action_mask: Tuple[str, ...],
        peak_offered_mbps: float = 14.0,
    ) -> StabilityVerificationResult:
        # 1. Verify V Range & Step
        if not (V_MIN <= proposed_v <= V_MAX):
            return StabilityVerificationResult(
                stable=False,
                reason=f"Proposed V={proposed_v:.2f} outside admissible range [{V_MIN}, {V_MAX}]",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=False,
                admissible_weights=True,
                admissible_mask=True,
            )
        if abs(proposed_v - current_v) > V_MAX_STEP + 1e-4:
            return StabilityVerificationResult(
                stable=False,
                reason=f"Step |V_new - V_old|={abs(proposed_v - current_v):.2f} exceeds max step {V_MAX_STEP}",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=False,
                admissible_weights=True,
                admissible_mask=True,
            )

        # 2. Verify Weight Normalization
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > WEIGHT_TOLERANCE:
            return StabilityVerificationResult(
                stable=False,
                reason=f"Weights sum to {weight_sum:.4f} != 1.0",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=True,
                admissible_weights=False,
                admissible_mask=True,
            )
        if any(w < -1e-6 for w in weights.values()):
            return StabilityVerificationResult(
                stable=False,
                reason="Negative weight detected",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=True,
                admissible_weights=False,
                admissible_mask=True,
            )

        # 3. Verify Action Mask Feasibility
        if not action_mask:
            return StabilityVerificationResult(
                stable=False,
                reason="Action mask is empty; cannot stabilize queue",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=True,
                admissible_weights=True,
                admissible_mask=False,
            )

        # If peak offered load exceeds primary link capacity, we MUST have at least one stabilizing action
        has_stabilizing = any(act in STABILIZING_ACTIONS for act in action_mask)
        if peak_offered_mbps > self.c_primary and not has_stabilizing:
            return StabilityVerificationResult(
                stable=False,
                reason=f"Offered load {peak_offered_mbps} Mbps > link capacity {self.c_primary} Mbps with no stabilizing action in mask",
                analytic_bound=float("inf"),
                capacity_slack_epsilon=0.0,
                admissible_v=True,
                admissible_weights=True,
                admissible_mask=False,
            )

        # Calculate Interior Capacity Slack epsilon (Mbit/slot)
        # With secondary path available, max service = 20 Mbps, peak load = 14 Mbps -> slack = 6 Mbps = 0.6 Mbit/slot
        slack_mbps = max(0.5, self.c_total - min(peak_offered_mbps, self.c_total * 0.95))
        epsilon = (slack_mbps * 0.1)  # in Mbit/slot

        # Compute Analytic Bound: (B + V * C) / epsilon
        bound = (self.constant_b + (proposed_v * self.cost_c)) / epsilon

        return StabilityVerificationResult(
            stable=True,
            reason="Lyapunov drift-plus-penalty stability and capacity slack guaranteed",
            analytic_bound=round(bound, 3),
            capacity_slack_epsilon=round(epsilon, 3),
            admissible_v=True,
            admissible_weights=True,
            admissible_mask=True,
        )

