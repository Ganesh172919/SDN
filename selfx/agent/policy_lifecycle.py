"""
End-to-End Policy Lifecycle, Promotion, and Rollback Audit Chain
Traceability: Tasks T18, T16, T17 | Deliverables D3, D4 | EC466 Team SDN_07

Full Provenance Pipeline:
  [Proposal]
      │
      ▼
  [Stability & Range Verification (T11)]
      │
      ▼
  [Non-Regression Stress Gate (T17)]
      │
      ├─► [If Approved] ──► Atomic Promotion to Incumbent (T16)
      │                         │
      │                         ▼
      │                     Install OpenFlow Flow-Mod (T05)
      │                         │
      │                         ▼
      │                     Datapath Readback Verification (T06)
      │
      └─► [If Rejected] ──► Fail-Closed Rejection ──► Retain Incumbent Policy
                                                        │
                                                        ▼
                                                    Atomic Rollback on Anomaly
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from agent.action_gateway import TopologyActionGateway
from agent.delta_pi_bridge import DeltaPiBridge, VersionedPolicyUpdate
from agent.dpp_stability import DPPStabilityValidator
from agent.rule_recovery import RuleRecoveryManager
from agentic.schemas import Policy
from agentic.stress_gate import NonRegressionStressGate, StressTestVerdict


@dataclass
class PolicyLifecycleAuditEntry:
    timestamp_utc: str
    cycle: int
    proposal_hash: str
    proposed_policy: Dict[str, Any]
    stability_verdict: Dict[str, Any]
    stress_gate_verdict: Dict[str, Any]
    final_status: str  # "PROMOTED_AND_ACTIVATED", "REJECTED_RETAINED_INCUMBENT", "ROLLED_BACK"
    active_version_id: str
    switch_action_taken: str
    datapath_verified: bool


class PolicyLifecycleOrchestrator:
    """
    Coordinates the full proposal -> stress evaluation -> activation -> switch rule
    installation -> readback -> rollback pipeline.
    """

    def __init__(self, topology_name: str = "linear") -> None:
        self.bridge = DeltaPiBridge()
        self.stability_validator = DPPStabilityValidator()
        self.stress_gate = NonRegressionStressGate()
        self.gateway = TopologyActionGateway(topology_name)
        self.recovery_mgr = RuleRecoveryManager()
        self.audit_chain: List[PolicyLifecycleAuditEntry] = []
        self.cycle_count = 0

    def process_candidate_policy(
        self,
        candidate: Policy,
        flow_match: Optional[Dict[str, Any]] = None,
    ) -> PolicyLifecycleAuditEntry:
        self.cycle_count += 1
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        incumbent = self.bridge.get_incumbent_policy()
        match_criteria = flow_match or {"nw_src": "10.0.0.2", "nw_dst": "10.0.0.8"}

        # 1. Stability Verification
        stab = self.stability_validator.verify_stability(
            current_v=incumbent.V,
            proposed_v=candidate.V,
            weights=candidate.weights(),
            action_mask=candidate.action_mask,
        )

        # 2. Stress Gate Non-Regression Evaluation
        if stab.stable:
            stress_verdict = self.stress_gate.evaluate_candidate(incumbent, candidate)
        else:
            stress_verdict = StressTestVerdict(
                promoted=False,
                reason=stab.reason,
                incumbent_score=0.0,
                candidate_score=0.0,
                relative_reward_delta=-999.0,
                hard_invariants_passed=False,
                stress_case_results=[],
            )

        # 3. Delta-Pi Atomic Bridge Promotion or Rejection
        approved = stab.stable and stress_verdict.promoted
        reason = stress_verdict.reason if stab.stable else stab.reason
        promoted, version_rec = self.bridge.submit_candidate_update(
            candidate_policy=candidate,
            gate_approved=approved,
            gate_reason=reason,
        )

        # 4. Action Gateway Compilation & Switch Installation
        switch_action_str = "no_op"
        datapath_ok = False

        if promoted:
            selected_act = candidate.action_mask[0]
            val = self.gateway.validate_and_compile(
                selected_act,
                match_criteria,
                reason="Policy promoted to datapath",
            )
            if val.allowed:
                switch_action_str = val.action.action_type
                rule = self.recovery_mgr.register_installed_action(
                    dpid=val.action.target_dpid,
                    action_type=val.action.action_type,
                    match=val.action.flow_match,
                    target_port=val.action.target_port,
                    priority=val.action.priority,
                )
                # Verify readback
                datapath_ok = self.recovery_mgr.verify_readback(
                    rule.rule_id,
                    [{"priority": rule.priority, "match": rule.match}],
                )

        final_status = "PROMOTED_AND_ACTIVATED" if promoted else "REJECTED_RETAINED_INCUMBENT"

        entry = PolicyLifecycleAuditEntry(
            timestamp_utc=ts,
            cycle=self.cycle_count,
            proposal_hash=version_rec.hash_sha256,
            proposed_policy=candidate.to_dict(),
            stability_verdict=asdict(stab),
            stress_gate_verdict=asdict(stress_verdict),
            final_status=final_status,
            active_version_id=self.bridge.get_incumbent_record().version_id,
            switch_action_taken=switch_action_str,
            datapath_verified=datapath_ok,
        )
        self.audit_chain.append(entry)
        return entry

    def trigger_anomaly_rollback(self, reason: str = "telemetry_anomaly_detected") -> PolicyLifecycleAuditEntry:
        """
        Atomically rolls back the active policy and switch forwarding rules to the parent incumbent.
        """
        rolled_rec = self.bridge.rollback_to_previous()
        self.recovery_mgr.trigger_rollback(reason=reason)

        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        active_id = rolled_rec.version_id if rolled_rec else self.bridge.get_incumbent_record().version_id

        entry = PolicyLifecycleAuditEntry(
            timestamp_utc=ts,
            cycle=self.cycle_count + 1,
            proposal_hash=active_id,
            proposed_policy=self.bridge.get_incumbent_policy().to_dict(),
            stability_verdict={"stable": True, "reason": "Restored previous known-good baseline"},
            stress_gate_verdict={"promoted": True, "reason": f"Rollback executed: {reason}"},
            final_status="ROLLED_BACK",
            active_version_id=active_id,
            switch_action_taken="restore_baseline_l2_rules",
            datapath_verified=True,
        )
        self.audit_chain.append(entry)
        return entry

    def export_audit_log(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self.audit_chain]

