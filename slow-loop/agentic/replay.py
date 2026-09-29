"""Bounded experience buffer of (state, policy, reward, next_state, reflection)."""

from __future__ import annotations

import math

from agentic.config import REPLAY_CAPACITY
from agentic.schemas import Experience, TelemetryWindow


def kernel(left: tuple[float, ...], right: tuple[float, ...], bandwidth: float = 0.45) -> float:
    distance = sum((a - b) ** 2 for a, b in zip(left, right))
    return math.exp(-distance / (2.0 * bandwidth * bandwidth))


class ReplayBuffer:
    def __init__(self, capacity: int = REPLAY_CAPACITY) -> None:
        self.capacity = capacity
        self._records: list[Experience] = []

    def __len__(self) -> int:
        return len(self._records)

    def add(self, experience: Experience) -> None:
        self._records.append(experience)
        if len(self._records) > self.capacity:
            self._records = self._records[-self.capacity :]

    def all_records(self) -> list[Experience]:
        return list(self._records)

    def similar(self, state: TelemetryWindow, k: int = 8, min_kernel: float = 0.05) -> list[tuple[Experience, float]]:
        scored = [
            (record, kernel(state.features(), record.state.features()))
            for record in self._records
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [(record, weight) for record, weight in scored[:k] if weight >= min_kernel]
