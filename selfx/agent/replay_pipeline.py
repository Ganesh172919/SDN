"""
Trajectory Replay-to-Dataset Pipeline for LoRA Self-Fine-Tuning
Traceability: Task T20 | Deliverables D4 | EC466 Team SDN_07

Curates episodic trajectory experiences:
  - Selects approved high-reward training examples (R >= tau).
  - Retains negative/failure examples for evaluation and hard negative mining.
  - Splits into train (70%), validation (15%), and holdout (15%) partitions.
  - Generates immutable SHA-256 manifests and reproducible dataset splits.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LORA_DATA_DIR = PROJECT_ROOT / "selfx" / "output" / "lora_training"
LORA_DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TrajectoryExample:
    example_id: str
    scenario: str
    state_vector: List[float]  # [util_p, util_s, lat_ms, loss_pct, queue_mbit]
    action_taken: str
    reward: float
    reflection: str
    quality_label: str  # "high_reward" or "failure"


class ReplayDatasetPipeline:
    """
    Curates and partitions trajectory replay records into training datasets
    for policy LoRA fine-tuning.
    """

    def __init__(self, reward_threshold: float = 0.05, seed: int = 42) -> None:
        self.reward_threshold = reward_threshold
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_synthetic_curated_replay(self, num_trajectories: int = 200) -> List[TrajectoryExample]:
        """
        Generates realistic trajectory examples from diverse network scenarios.
        """
        actions = ["reroute", "rate_limit", "admit", "drop", "no_op"]
        examples: List[TrajectoryExample] = []

        for i in range(num_trajectories):
            scen = self.rng.choice(["mixed", "flash", "alternate", "volatile"])
            is_congested = self.rng.random() < 0.6
            util_p = round(self.rng.uniform(70.0, 140.0) if is_congested else self.rng.uniform(20.0, 65.0), 1)
            util_s = round(self.rng.uniform(10.0, 50.0), 1)
            lat = round(4.0 + (util_p / 10.0) * 1.5, 2)
            loss = round(max(0.0, (util_p - 100.0) * 0.15), 2)
            q = round(max(0.0, (util_p - 100.0) * 0.005), 4)

            # Assign action and compute resulting reward
            if is_congested:
                act = self.rng.choice(["reroute", "rate_limit", "admit"])
                if act == "reroute":
                    rew = 0.28 + self.rng.uniform(-0.05, 0.08)
                    refl = "Rerouting elephant flow to secondary link relieved primary bottleneck."
                elif act == "rate_limit":
                    rew = 0.15 + self.rng.uniform(-0.04, 0.05)
                    refl = "Rate limiting elephant burst stabilized queue backlog within bounds."
                else:
                    rew = -0.32 + self.rng.uniform(-0.05, 0.05)
                    refl = "Admitting offered load without action caused heavy packet loss and buffer overflow."
            else:
                act = self.rng.choice(["no_op", "admit", "reroute"])
                if act in ("no_op", "admit"):
                    rew = 0.18 + self.rng.uniform(-0.02, 0.04)
                    refl = "Network operating under nominal conditions; maintaining forwarding was optimal."
                else:
                    rew = -0.12 + self.rng.uniform(-0.03, 0.03)
                    refl = "Unnecessary reroute incurred excess delay on secondary detour link."

            label = "high_reward" if rew >= self.reward_threshold else "failure"
            examples.append(TrajectoryExample(
                example_id=f"traj_{i:04d}",
                scenario=scen,
                state_vector=[util_p, util_s, lat, loss, q],
                action_taken=act,
                reward=round(rew, 4),
                reflection=refl,
                quality_label=label,
            ))

        return examples

    def curate_and_export_splits(
        self,
        examples: Optional[List[TrajectoryExample]] = None,
    ) -> Dict[str, Any]:
        data = examples or self.generate_synthetic_curated_replay()
        self.rng.shuffle(data)

        high_reward_pool = [e for e in data if e.quality_label == "high_reward"]
        failure_pool = [e for e in data if e.quality_label == "failure"]

        n_train = int(len(high_reward_pool) * 0.70)
        n_val = int(len(high_reward_pool) * 0.15)

        train_set = high_reward_pool[:n_train]
        val_set = high_reward_pool[n_train:n_train + n_val]
        holdout_set = high_reward_pool[n_train + n_val:] + failure_pool[:15]

        splits = {
            "train": [asdict(e) for e in train_set],
            "validation": [asdict(e) for e in val_set],
            "holdout": [asdict(e) for e in holdout_set],
            "failures_retained_for_eval": [asdict(e) for e in failure_pool],
        }

        # Save files and calculate hashes
        saved_files = {}
        for split_name, records in splits.items():
            path = LORA_DATA_DIR / f"dataset_{split_name}.json"
            content = json.dumps(records, indent=2)
            path.write_text(content, encoding="utf-8")
            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
            saved_files[split_name] = {
                "path": str(path),
                "count": len(records),
                "sha256": h,
            }

        manifest = {
            "manifest_version": "selfx.lora_dataset.v1",
            "seed": self.seed,
            "reward_threshold": self.reward_threshold,
            "total_trajectories": len(data),
            "splits": saved_files,
        }

        manifest_path = LORA_DATA_DIR / "dataset_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

