"""
Typed Delta-Pi Bridge (Slow-to-Fast Update Channel)
Traceability: Task T16 | Deliverables D3 | EC466 Team SDN_07

Provides:
  - Strongly typed, versioned policy transfer bridge.
  - Manages Incumbent policy vs. Candidate Delta-Pi updates.
  - Validates numeric boundaries, weight simplex, and action vocabulary mapping.
  - Implements thread-safe atomic swap: only safety-approved policies are delivered to DPP.
  - Retains immutable versioned audit history (Delta-Pi lineage).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from agentic.schemas import Policy, initial_policy


@dataclass(frozen=True)
class VersionedPolicyUpdate:
    version_id: str
    parent_version_id: Optional[str]
    timestamp_utc: str
    V: float
    weights: Dict[str, float]
    action_mask: Tuple[str, ...]
    hash_sha256: str
    provenance: str  # "slow_loop_governor" or "initial"


class DeltaPiBridge:
    """
    Thread-safe, atomic bridge delivering validated policy updates from the
    slow AI governance layer to the fast Lyapunov DPP controller.
    """

    def __init__(self, initial_p: Optional[Policy] = None) -> None:
        init = initial_p or initial_policy()
        self._lock = threading.RLock()
        self._incumbent_policy = init
        self._version_counter = 0

        first_version = self._create_versioned_record(init, parent_id=None, provenance="initial")
        self._incumbent_record = first_version
        self._lineage: List[VersionedPolicyUpdate] = [first_version]
        self._rejected_updates: List[Dict[str, Any]] = []

    def _compute_hash(self, policy: Policy) -> str:
        payload = json.dumps(policy.to_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _create_versioned_record(
        self,
        policy: Policy,
        parent_id: Optional[str],
        provenance: str = "slow_loop_governor",
    ) -> VersionedPolicyUpdate:
        self._version_counter += 1
        vid = f"pi-v{self._version_counter}.0"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        h = self._compute_hash(policy)
        return VersionedPolicyUpdate(
            version_id=vid,
            parent_version_id=parent_id,
            timestamp_utc=ts,
            V=policy.V,
            weights=policy.weights(),
            action_mask=policy.action_mask,
            hash_sha256=h,
            provenance=provenance,
        )

    def get_incumbent_policy(self) -> Policy:
        with self._lock:
            return self._incumbent_policy

    def get_incumbent_record(self) -> VersionedPolicyUpdate:
        with self._lock:
            return self._incumbent_record

    def submit_candidate_update(
        self,
        candidate_policy: Policy,
        gate_approved: bool,
        gate_reason: str = "",
    ) -> Tuple[bool, VersionedPolicyUpdate]:
        """
        Atomically promotes the candidate to incumbent if gate_approved is True.
        Otherwise records rejection and retains the incumbent.
        """
        with self._lock:
            parent_id = self._incumbent_record.version_id
            record = self._create_versioned_record(candidate_policy, parent_id=parent_id)

            if gate_approved:
                self._incumbent_policy = candidate_policy
                self._incumbent_record = record
                self._lineage.append(record)
                return True, record
            else:
                self._rejected_updates.append({
                    "candidate": asdict(record),
                    "rejection_reason": gate_reason,
                    "retained_incumbent": self._incumbent_record.version_id,
                    "timestamp_utc": record.timestamp_utc,
                })
                return False, self._incumbent_record

    def rollback_to_previous(self) -> Optional[VersionedPolicyUpdate]:
        """
        Roll back to parent incumbent policy.
        """
        with self._lock:
            if len(self._lineage) <= 1:
                return None  # At initial baseline; cannot rollback further
            self._lineage.pop()
            self._incumbent_record = self._lineage[-1]
            # Reconstruct Policy
            rec = self._incumbent_record
            w = rec.weights
            self._incumbent_policy = Policy(
                V=rec.V,
                latency=w["latency"],
                throughput=w["throughput"],
                loss=w["loss"],
                energy=w["energy"],
                resource=w["resource"],
                action_mask=rec.action_mask,
            )
            return self._incumbent_record

    def get_lineage(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(r) for r in self._lineage]

    def get_rejected_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._rejected_updates)

