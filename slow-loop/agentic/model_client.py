"""Model backends for the slow loop.

MockModel is deterministic and needs no weights. OpenAICompatibleClient
talks to a local server (Gemma or otherwise) when one is running.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from agentic.agents import merge_opinions, specialist_opinion
from agentic.config import ROLES


class ModelClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


def strip_json_fence(text: str) -> str:
    body = text.strip()
    if not body.startswith("```"):
        return body
    lines = body.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


class MockModel:
    """One logical model. Role prompts select which specialist answer is returned."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[-1]["content"])
        role = str(payload["role"])
        from agentic.schemas import Policy, TelemetryWindow

        telemetry = TelemetryWindow.from_dict(payload["telemetry"])
        policy = Policy.from_dict(payload["policy"])
        if role == "single":
            opinions = [specialist_opinion(name, telemetry, policy) for name in ROLES]
            return merge_opinions(policy, opinions).to_json()
        if role not in ROLES:
            raise ValueError(f"mock model has no role {role}")
        return specialist_opinion(role, telemetry, policy).to_json()


class OpenAICompatibleClient:
    """POST {base_url}/chat/completions. base_url should include the /v1 prefix."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8081/v1",
        model: str = "local",
        api_key: str | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    def complete(self, messages: list[dict[str, str]]) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0.2,
                "messages": messages,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"model server returned {exc.code}: {detail}") from exc
        return str(payload["choices"][0]["message"]["content"])

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
