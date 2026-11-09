"""
Automatic LoRA Adapter Lifecycle Manager
Traceability: Tasks T24, T22, T23 | Deliverables D4 | EC466 Team SDN_07

Orchestrates:
  1. Automated trigger on trajectory replay accumulation.
  2. Training candidate LoRA adapter weights.
  3. Strict evaluation through AdapterEvaluationGate (T23).
  4. Promotion & activation to incumbent or rejection & fail-closed rollback.
  5. Cryptographic lineage logging of all adapter updates.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.adapter_gate import AdapterEvaluationGate, AdapterGateVerdict
from agent.policy_backend import LoRAAdapterCheckpoint, LoRAPolicyBackend
from scripts.run_lora_finetune import train_lora_adapter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LORA_DATA_DIR = PROJECT_ROOT / "selfx" / "output" / "lora_training"
LORA_DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AdapterLifecycleRecord:
    timestamp_utc: str
    cycle_id: str
    action: str  # "PROMOTED_NEW_INCUMBENT", "REJECTED_RETAINED_INCUMBENT", "ROLLED_BACK"
    candidate_adapter_id: str
    active_adapter_id: str
    gate_verdict: Dict[str, Any]
    lineage_parent_id: Optional[str]
    sha256_hash: str


class AutomaticAdapterLifecycleManager:
    """
    Automated lifecycle manager maintaining active LoRA adapter weights
    and enforcing fail-closed promotion/rollback.
    """

    def __init__(self) -> None:
        self.gate = AdapterEvaluationGate()
        self.incumbent_adapter: Optional[LoRAAdapterCheckpoint] = None
        self.lifecycle_log: List[AdapterLifecycleRecord] = []
        self.history: List[LoRAAdapterCheckpoint] = []

    def run_adapter_cycle(
        self,
        epochs: int = 5,
        force_rejection_test: bool = False,
    ) -> AdapterLifecycleRecord:
        cycle_id = f"cycle_{int(time.time())}"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 1. Train candidate adapter
        manifest = train_lora_adapter(epochs=epochs)
        weights_file = Path(manifest["adapter_artifact"])

        with open(weights_file, "r", encoding="utf-8") as f:
            wdata = json.load(f)

        candidate = LoRAAdapterCheckpoint(
            adapter_id=wdata["adapter_id"],
            base_model_id=wdata["base_model_id"],
            rank=wdata["rank"],
            alpha=wdata["alpha"],
            learning_rate=wdata["learning_rate"],
            matrix_a=wdata["matrix_a"],
            matrix_b=wdata["matrix_b"],
            train_loss=wdata["final_loss"],
            created_at_epoch=epochs,
        )

        # 2. Gate evaluation
        if force_rejection_test:
            # Simulate a corrupted / regressive candidate
            verdict = AdapterGateVerdict(
                promoted=False,
                verdict="REJECTED",
                reason="Simulated regression test: candidate loss exceeded safety ceiling",
                incumbent_accuracy=0.85,
                candidate_accuracy=0.10,
                incumbent_mean_reward=0.25,
                candidate_mean_reward=-0.30,
                relative_reward_gain=-0.55,
                hard_invariants_passed=False,
            )
        else:
            verdict = self.gate.evaluate_candidate(candidate, self.incumbent_adapter)

        # 3. Promote or Reject
        parent_id = self.incumbent_adapter.adapter_id if self.incumbent_adapter else None

        if verdict.promoted:
            action_str = "PROMOTED_NEW_INCUMBENT"
            self.incumbent_adapter = candidate
            self.history.append(candidate)
            active_id = candidate.adapter_id
        else:
            action_str = "REJECTED_RETAINED_INCUMBENT"
            active_id = self.incumbent_adapter.adapter_id if self.incumbent_adapter else "base_frozen_model"

        record = AdapterLifecycleRecord(
            timestamp_utc=ts,
            cycle_id=cycle_id,
            action=action_str,
            candidate_adapter_id=candidate.adapter_id,
            active_adapter_id=active_id,
            gate_verdict=asdict(verdict),
            lineage_parent_id=parent_id,
            sha256_hash=manifest["sha256"],
        )
        self.lifecycle_log.append(record)

        # Save audit log
        log_file = LORA_DATA_DIR / "adapter_lifecycle_log.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in self.lifecycle_log], f, indent=2)

        return record

    def rollback_to_previous_adapter(self, reason: str = "runtime_failure") -> AdapterLifecycleRecord:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        prev_id = "base_frozen_model"
        if len(self.history) > 1:
            self.history.pop()
            self.incumbent_adapter = self.history[-1]
            prev_id = self.incumbent_adapter.adapter_id
        elif len(self.history) == 1:
            self.history.pop()
            self.incumbent_adapter = None
            prev_id = "base_frozen_model"

        record = AdapterLifecycleRecord(
            timestamp_utc=ts,
            cycle_id=f"rollback_{int(time.time())}",
            action="ROLLED_BACK",
            candidate_adapter_id="none",
            active_adapter_id=prev_id,
            gate_verdict={"reason": f"Atomic rollback executed: {reason}"},
            lineage_parent_id=None,
            sha256_hash=hashlib.sha256(prev_id.encode("utf-8")).hexdigest(),
        )
        self.lifecycle_log.append(record)
        return record

