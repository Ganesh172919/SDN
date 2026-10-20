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

No vector database or embedding API is required. Calls without a query
retain the original reward ranking; a query ranks retained episodes by
cosine similarity over the transparent numeric state representation.

Pruning: once len(records) > config.MEMORY_MAX_ENTRIES, drop the
lowest-reward entries first, per spec.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

import config
from pathlib import Path
from agent.embedding import embed_state, cosine


class MemoryStore:
    def __init__(self, path: str = config.MEMORY_PATH, enabled: bool = True, autosave: bool = True):
        self.path = path
        self.enabled = enabled
        self.autosave = autosave
        self._records: list[dict] = []
        if self.enabled:
            self._load()

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    value = json.load(f)
                    self._records = [r for r in value if isinstance(r, dict) and
                                     all(k in r for k in ("cycle", "reward", "state_summary", "action", "params", "reflection"))] if isinstance(value, list) else []
                except json.JSONDecodeError:
                    self._records = []
        else:
            self._records = []

    def _save(self) -> None:
        if not self.enabled:
            return
        tmp_path = f"{self.path}.tmp"
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
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
        if self.autosave:
            self._save()

    def flush(self) -> None:
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

    def few_shot_examples(self, k: Optional[int] = None, query: Optional[dict] = None) -> list[dict]:
        """The K highest-reward (state, action, outcome, reflection) records."""
        if not self.enabled or not self._records:
            return []
        k = k or min(config.FEWSHOT_MAX_EXAMPLES, max(config.FEWSHOT_MIN_EXAMPLES, 1))
        ranked = sorted(self._records, key=lambda r: r["reward"], reverse=True)
        if query is not None:
            vector = embed_state(query)
            ranked = sorted(ranked, key=lambda r: cosine(vector, embed_state(r["state_summary"])), reverse=True)
        return ranked[:k]

    def clear(self) -> None:
        self._records = []
        if self.enabled and os.path.exists(self.path):
            os.remove(self.path)
