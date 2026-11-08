"""
Neural Policy Backend with Low-Rank Adaptation (LoRA) Support
Traceability: Tasks T21, T22 | Deliverables D4 | EC466 Team SDN_07

Formulation:
  Given base frozen policy weight matrix W_0 in R^{d x k}, LoRA adapts parameters via:
      W = W_0 + (alpha / r) * (B * A)
  where:
      B in R^{d x r} (initialized to zeros)
      A in R^{r x k} (initialized with Gaussian noise)
      r = 8 (low-rank bottleneck)
      alpha = 16 (scaling factor, alpha / r = 2.0)

Enables:
  1. Base model forward pass without fine-tuning (A1/A2 stages).
  2. Active LoRA adapter inference after parameter training (A3/A4/A5 stages).
  3. Seamless adapter swapping and hot rollback without restarting the controller.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LoRAAdapterCheckpoint:
    adapter_id: str
    base_model_id: str
    rank: int
    alpha: float
    learning_rate: float
    matrix_a: List[List[float]]  # r x k
    matrix_b: List[List[float]]  # d x r
    train_loss: float
    created_at_epoch: int


class LoRAPolicyBackend:
    """
    Trainable and adaptable neural policy engine for SELF-X flow management.
    """

    def __init__(
        self,
        input_dim: int = 5,   # [util_p, util_s, lat_ms, loss_pct, queue_mbit]
        output_dim: int = 5,  # actions: [reroute, rate_limit, admit, drop, no_op]
        rank: int = 8,
        alpha: float = 16.0,
        base_model_id: str = "selfx-base-v1",
        seed: int = 42,
    ) -> None:
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.rank = rank
        self.alpha = alpha
        self.scaling = alpha / rank
        self.base_model_id = base_model_id
        self.seed = seed
        self.rng = random.Random(seed)

        # Frozen base weights W_0 (d x k)
        self.w0: List[List[float]] = [
            [round(self.rng.uniform(-0.3, 0.3), 4) for _ in range(output_dim)]
            for _ in range(input_dim)
        ]
        self.bias0: List[float] = [0.0] * output_dim

        # Active LoRA Adapter (None if running unadapted base model)
        self.active_adapter: Optional[LoRAAdapterCheckpoint] = None

    def initialize_new_adapter(self, adapter_id: str = "adapter_candidate") -> LoRAAdapterCheckpoint:
        """
        Standard LoRA initialization: A ~ N(0, sigma^2), B = 0.
        Ensures Delta W = B * A = 0 at step 0!
        """
        a = [
            [round(self.rng.gauss(0.0, 0.02), 4) for _ in range(self.output_dim)]
            for _ in range(self.rank)
        ]
        b = [
            [0.0 for _ in range(self.rank)]
            for _ in range(self.input_dim)
        ]
        return LoRAAdapterCheckpoint(
            adapter_id=adapter_id,
            base_model_id=self.base_model_id,
            rank=self.rank,
            alpha=self.alpha,
            learning_rate=1e-3,
            matrix_a=a,
            matrix_b=b,
            train_loss=1.0,
            created_at_epoch=0,
        )

    def attach_adapter(self, adapter: LoRAAdapterCheckpoint) -> None:
        if adapter.base_model_id != self.base_model_id:
            raise ValueError(f"Adapter base model mismatch: {adapter.base_model_id} != {self.base_model_id}")
        self.active_adapter = adapter

    def detach_adapter(self) -> None:
        self.active_adapter = None

    def _matmul(self, vec: List[float], mat: List[List[float]]) -> List[float]:
        # vec (1 x d) * mat (d x k) -> (1 x k)
        k = len(mat[0])
        res = [0.0] * k
        for j in range(k):
            s = 0.0
            for i in range(len(vec)):
                s += vec[i] * mat[i][j]
            res[j] = s
        return res

    def forward(self, state_features: List[float]) -> Tuple[List[float], str]:
        """
        Computes output action logits: h = x * (W_0 + (alpha / r) * B * A) + bias.
        Returns normalized action probabilities and selected action name.
        """
        actions = ["reroute", "rate_limit", "admit", "drop", "no_op"]
        # Base forward
        base_logits = self._matmul(state_features, self.w0)

        # LoRA forward: Delta W = (alpha/r) * (x * B) * A
        if self.active_adapter is not None:
            # Step 1: x_B = x * B (1 x r)
            x_b = self._matmul(state_features, self.active_adapter.matrix_b)
            # Step 2: delta = x_B * A (1 x k)
            delta = self._matmul(x_b, self.active_adapter.matrix_a)
            logits = [
                base_logits[i] + self.scaling * delta[i] + self.bias0[i]
                for i in range(self.output_dim)
            ]
        else:
            logits = [base_logits[i] + self.bias0[i] for i in range(self.output_dim)]

        # Softmax
        max_l = max(logits)
        exp_l = [math.exp(v - max_l) for v in logits]
        sum_exp = sum(exp_l)
        probs = [round(v / sum_exp, 4) for v in exp_l]

        best_idx = int(max(range(len(probs)), key=lambda idx: probs[idx]))
        return probs, actions[best_idx]

