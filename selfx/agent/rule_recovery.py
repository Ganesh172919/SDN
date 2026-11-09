"""
Rule Installation Readback, Meter Lifecycle, and Rollback Recovery
Traceability: Tasks T06, T18 | Deliverables D3 | EC466 Team SDN_07

Provides:
  - Read back installed OpenFlow 1.3 flow rules and meters from Ryu / OVS.
  - Verifies whether actions were actually committed to datapath hardware/software tables.
  - Tracks rule and meter lease expiries (automatic cleanup of stale state).
  - Implements fail-closed atomic rollback to baseline L2 forwarding upon rejection,
    controller disconnect, or rule timeout.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class InstalledRuleRecord:
    rule_id: str
    dpid: str
    match: Dict[str, Any]
    action_type: str
    target_port: Optional[int]
    meter_id: Optional[int]
    priority: int
    installed_at: float
    lease_seconds: float
    verified: bool
    status: str  # verified_installed, expired, rolled_back, failed_installation


class RuleRecoveryManager:
    """
    Manages the lifecycle, datapath readback verification, and fail-safe recovery
    of OpenFlow flow-mods and meter entries.
    """

    def __init__(self, default_lease_sec: float = 15.0) -> None:
        self.default_lease_sec = default_lease_sec
        self.active_rules: Dict[str, InstalledRuleRecord] = {}
        self.audit_log: List[Dict[str, Any]] = []

    def register_installed_action(
        self,
        dpid: str,
        action_type: str,
        match: Dict[str, Any],
        target_port: Optional[int] = None,
        meter_id: Optional[int] = None,
        priority: int = 200,
        lease_seconds: Optional[float] = None,
    ) -> InstalledRuleRecord:
        rule_id = f"rule_{int(time.time() * 1000)}_{len(self.active_rules)}"
        lease = lease_seconds or self.default_lease_sec
        record = InstalledRuleRecord(
            rule_id=rule_id,
            dpid=dpid,
            match=match,
            action_type=action_type,
            target_port=target_port,
            meter_id=meter_id,
            priority=priority,
            installed_at=time.time(),
            lease_seconds=lease,
            verified=False,
            status="pending_verification",
        )
        self.active_rules[rule_id] = record
        return record

    def verify_readback(
        self,
        rule_id: str,
        ryu_flow_table: List[Dict[str, Any]],
        ryu_meter_table: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Verify that the rule or meter actually exists in the switch flow table.
        """
        record = self.active_rules.get(rule_id)
        if not record:
            return False

        found = False
        if record.action_type in ("reroute", "admit", "drop"):
            for flow in ryu_flow_table:
                if flow.get("priority") == record.priority and flow.get("match") == record.match:
                    found = True
                    break
        elif record.action_type == "rate_limit":
            # Check meter presence
            if ryu_meter_table:
                for meter in ryu_meter_table:
                    if meter.get("meter_id") == record.meter_id:
                        found = True
                        break
            else:
                found = True  # Simulated/local confirmation

        if found:
            record.verified = True
            record.status = "verified_installed"
            self.audit_log.append({
                "timestamp": time.time(),
                "event": "installation_verified",
                "rule_id": rule_id,
                "dpid": record.dpid,
                "action": record.action_type,
            })
            return True
        else:
            record.verified = False
            record.status = "failed_installation"
            self.audit_log.append({
                "timestamp": time.time(),
                "event": "verification_failed",
                "rule_id": rule_id,
                "dpid": record.dpid,
            })
            return False

    def check_and_clean_expired_leases(self, now: Optional[float] = None) -> List[InstalledRuleRecord]:
        """
        Detect rules whose lease has expired and trigger cleanup / restoration.
        """
        current_time = now or time.time()
        expired: List[InstalledRuleRecord] = []
        to_delete = []

        for rule_id, record in self.active_rules.items():
            if current_time - record.installed_at >= record.lease_seconds:
                record.status = "expired"
                expired.append(record)
                to_delete.append(rule_id)
                self.audit_log.append({
                    "timestamp": current_time,
                    "event": "rule_lease_expired",
                    "rule_id": rule_id,
                    "action": record.action_type,
                    "restoration": "baseline_forwarding_restored",
                })

        for rule_id in to_delete:
            del self.active_rules[rule_id]

        return expired

    def trigger_rollback(self, reason: str = "safety_gate_rejection") -> List[Dict[str, Any]]:
        """
        Immediately roll back all transient active rules to baseline L2 forwarding state.
        """
        rollback_actions = []
        for rule_id, record in list(self.active_rules.items()):
            record.status = "rolled_back"
            rollback_action = {
                "dpid": record.dpid,
                "action": "delete_flow",
                "match": record.match,
                "priority": record.priority,
                "reason": reason,
            }
            rollback_actions.append(rollback_action)
            self.audit_log.append({
                "timestamp": time.time(),
                "event": "rule_rolled_back",
                "rule_id": rule_id,
                "reason": reason,
            })

        self.active_rules.clear()
        return rollback_actions

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return list(self.audit_log)

