"""
LoRA Fine-Tuning Execution Script
Traceability: Task T22 | Deliverables D4 | EC466 Team SDN_07

Trains low-rank parameter matrices (rank r=8, alpha=16) on curated replay dataset.
Saves:
  - Base model ID, hyperparameters, and training loss curve.
  - Adapter weights checkpoint (adapter_weights.json).
  - Reproducible training manifest with SHA-256 hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "selfx") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "selfx"))

from agent.policy_backend import LoRAAdapterCheckpoint, LoRAPolicyBackend
from agent.replay_pipeline import ReplayDatasetPipeline

LORA_OUT_DIR = PROJECT_ROOT / "selfx" / "output" / "lora_training"
LORA_OUT_DIR.mkdir(parents=True, exist_ok=True)


def train_lora_adapter(
    epochs: int = 10,
    lr: float = 0.005,
    rank: int = 8,
    alpha: float = 16.0,
    seed: int = 42,
) -> Dict[str, Any]:
    print("==================================================================")
    print("SELF-X LoRA Policy Fine-Tuning Job (T22)")
    print(f"Hyperparameters: Rank r={rank}, Alpha={alpha}, LR={lr}, Epochs={epochs}")
    print("==================================================================")

    # 1. Prepare Dataset
    pipeline = ReplayDatasetPipeline(seed=seed)
    train_data_file = LORA_OUT_DIR / "dataset_train.json"
    if not train_data_file.exists():
        manifest = pipeline.curate_and_export_splits()
    with open(train_data_file, "r", encoding="utf-8") as f:
        train_examples = json.load(f)

    # 2. Initialize Model & Adapter
    backend = LoRAPolicyBackend(rank=rank, alpha=alpha, seed=seed)
    adapter = backend.initialize_new_adapter(adapter_id=f"lora_v1_seed{seed}")
    backend.attach_adapter(adapter)

    action_to_idx = {"reroute": 0, "rate_limit": 1, "admit": 2, "drop": 3, "no_op": 4}

    loss_history: List[float] = []

    # 3. Training Loop (SGD with policy gradient on high-reward targets)
    scaling = alpha / rank
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0

        for ex in train_examples:
            x = ex["state_vector"]
            target_idx = action_to_idx.get(ex["action_taken"], 4)
            reward_weight = max(0.1, ex["reward"])

            probs, _ = backend.forward(x)
            prob_target = max(1e-6, probs[target_idx])
            loss = -math.log(prob_target) * reward_weight
            epoch_loss += loss

            # Gradient step on LoRA matrices B and A
            # Grad w.r.t logits: p - y
            d_logits = [probs[j] - (1.0 if j == target_idx else 0.0) for j in range(5)]

            # Compute update for B (d x r) and A (r x k)
            x_b = backend._matmul(x, adapter.matrix_b)  # 1 x r

            # Update A: dL/dA = x_b^T * d_logits * scaling
            for r_idx in range(rank):
                for k_idx in range(5):
                    grad_a = x_b[r_idx] * d_logits[k_idx] * scaling * reward_weight
                    adapter.matrix_a[r_idx][k_idx] -= lr * grad_a

            # Update B: dL/dB = x^T * (d_logits * A^T) * scaling
            d_xb = [sum(d_logits[k] * adapter.matrix_a[r_idx][k] for k in range(5)) for r_idx in range(rank)]
            for d_idx in range(5):
                for r_idx in range(rank):
                    grad_b = x[d_idx] * d_xb[r_idx] * scaling * reward_weight
                    adapter.matrix_b[d_idx][r_idx] -= lr * grad_b

        avg_epoch_loss = round(epoch_loss / len(train_examples), 4)
        loss_history.append(avg_epoch_loss)
        print(f"Epoch {epoch:2d}/{epochs} | Policy Cross-Entropy Loss: {avg_epoch_loss:.4f}")

    adapter.train_loss = loss_history[-1]
    adapter.created_at_epoch = epochs

    # 4. Save Adapter Weights & Manifest
    adapter_dict = {
        "adapter_id": adapter.adapter_id,
        "base_model_id": adapter.base_model_id,
        "rank": adapter.rank,
        "alpha": adapter.alpha,
        "learning_rate": adapter.learning_rate,
        "final_loss": adapter.train_loss,
        "matrix_a": adapter.matrix_a,
        "matrix_b": adapter.matrix_b,
    }
    weights_path = LORA_OUT_DIR / "adapter_weights.json"
    weights_json = json.dumps(adapter_dict, indent=2)
    weights_path.write_text(weights_json, encoding="utf-8")
    adapter_sha256 = hashlib.sha256(weights_json.encode("utf-8")).hexdigest()

    training_manifest = {
        "job_id": f"lora_train_{adapter.adapter_id}",
        "base_model_id": adapter.base_model_id,
        "hyperparameters": {
            "rank": rank,
            "alpha": alpha,
            "learning_rate": lr,
            "epochs": epochs,
            "scaling": scaling,
        },
        "training_samples": len(train_examples),
        "loss_curve": loss_history,
        "final_loss": adapter.train_loss,
        "adapter_artifact": str(weights_path),
        "sha256": adapter_sha256,
        "training_status": "COMPLETED_SUCCESSFULLY",
    }
    manifest_path = LORA_OUT_DIR / "training_manifest.json"
    manifest_path.write_text(json.dumps(training_manifest, indent=2), encoding="utf-8")

    print("\nLoRA Fine-Tuning Finished Successfully!")
    print(f"Saved Checkpoint: {weights_path} (SHA-256: {adapter_sha256[:16]}...)")
    print(f"Saved Manifest:   {manifest_path}\n")

    return training_manifest


def main():
    parser = argparse.ArgumentParser(description="SELF-X LoRA Policy Training")
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs")
    parser.add_argument("--lr", type=float, default=0.005, help="Learning rate")
    args = parser.parse_args()

    train_lora_adapter(epochs=args.epochs, lr=args.lr)


if __name__ == "__main__":
    main()

