"""
Phase 4 — reflection & memory store.

A single JSON file holding a flat list of records:

    {
      "cycle": 17,
      "timestamp": "...",
      "state_summary": {...},      # compact snapshot of get_state() at decide time
      "action": "rate_limit",
      "params": {...},
      "reward": 0.42,
      "reflection": "Throttling the elephant flow recovered latency without ..."
    }

No vector DB, no embeddings, by design (see spec's explicit non-goals
for this track) — few-shot retrieval is simply "the K highest-reward
records seen so far", which is enough signal for an in-context
reflection loop at this scale.

Pruning: once len(records) > config.MEMORY_MAX_ENTRIES, drop the
lowest-reward entries first, per spec.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

import config


class MemoryStore:
    def __init__(self, path: str = config.MEMORY_PATH, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self._records: list[dict] = []
        if self.enabled:
            self._load()

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    self._records = json.load(f)
                except json.JSONDecodeError:
                    self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        if not self.enabled:
            return
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._records, f, indent=2)
        os.replace(tmp_path, self.path)

    # -- writes ----------------------------------------------------------

    def add_record(self, cycle: int, state_summary: dict, action: str, params: dict,
                    reward: float, reflection: str) -> None:
        if not self.enabled:
            return
        self._records.append(
            {
                "cycle": cycle,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state_summary": state_summary,
                "action": action,
                "params": params,
                "reward": reward,
                "reflection": reflection,
            }
        )
        self._prune()
        self._save()

    def _prune(self) -> None:
        if len(self._records) <= config.MEMORY_MAX_ENTRIES:
            return
        # drop the lowest-reward entries first
        self._records.sort(key=lambda r: r["reward"], reverse=True)
        self._records = self._records[: config.MEMORY_MAX_ENTRIES]
        # restore chronological order for readability
        self._records.sort(key=lambda r: r["cycle"])

    # -- reads -------------------------------------------------------------

    def all_records(self) -> list[dict]:
        return list(self._records) if self.enabled else []

    def few_shot_examples(self, k: Optional[int] = None) -> list[dict]:
        """The K highest-reward (state, action, outcome, reflection) records."""
        if not self.enabled or not self._records:
            return []
        k = k or min(config.FEWSHOT_MAX_EXAMPLES, max(config.FEWSHOT_MIN_EXAMPLES, 1))
        ranked = sorted(self._records, key=lambda r: r["reward"], reverse=True)
        return ranked[:k]

    def clear(self) -> None:
        self._records = []
        if self.enabled and os.path.exists(self.path):
            os.remove(self.path)
