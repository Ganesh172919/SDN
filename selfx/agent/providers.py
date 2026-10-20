"""Small REST adapter shared by simulation and LangGraph. Never logs credentials."""
from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace
from typing import Any

import requests
import config


class ProviderError(RuntimeError):
    """Only sanitized error codes leave this module."""


def parse_json(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("empty_model_response")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


class RestLLM:
    _last_request: dict[str, float] = {}
    def __init__(self, provider: str = "auto", model: str | None = None, profile: str = "legacy"):
        if provider not in {"auto", "gemini", "openrouter"}:
            raise ValueError("provider must be auto, gemini or openrouter")
        self.provider, self.model = provider, model
        if profile not in {'legacy','compact'}:raise ValueError('unknown provider profile')
        self.profile=profile
        self.session=requests.Session() if profile=='compact' else None
        self.request_stats={}
        self.audit: list[dict] = []
        self.failures: dict[str, int] = {}

    def with_structured_output(self, schema):
        return SimpleNamespace(invoke=lambda messages: self._invoke(schema, messages))

    def _invoke(self, schema, messages):
        schema_prompt = "\nReturn one JSON object matching this schema: " + json.dumps(schema.model_json_schema(),separators=(',',':') if self.profile=='compact' else None)
        augmented = [dict(m) for m in messages]
        augmented[-1]["content"] += schema_prompt
        candidates = ["gemini", "openrouter"] if self.provider == "auto" else [self.provider]
        for provider in candidates:
            if self.failures.get(provider, 0) >= 2:
                continue  # Bounded circuit breaker: quota/auth failures must not stall every cycle.
            start = time.perf_counter()
            model = self.model or (config.GEMINI_MODEL if provider == "gemini" else config.OPENROUTER_MODEL)
            record = {"provider": provider, "requested_model": model, "schema": schema.__name__}
            self.request_stats={}
            try:
                value, actual_model, usage = self._request(provider, model, augmented)
                result = schema.model_validate(parse_json(value))
                record.update(status="ok", actual_model=actual_model, usage=usage)
                self.failures[provider] = 0
                return result
            except Exception as exc:
                code = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
                record.update(status="error", error_code=code)
                self.failures[provider] = self.failures.get(provider, 0) + 1
            finally:
                record["elapsed_ms"] = round(1000 * (time.perf_counter() - start), 2)
                record.update(self.request_stats,profile=self.profile,prompt_chars=sum(len(m['content']) for m in augmented))
                self.audit.append(record)
        raise ProviderError("all_configured_providers_unavailable")

    def _request(self, provider: str, model: str, messages: list[dict]):
        gap = float(os.environ.get("GEMINI_REQUEST_GAP_SEC" if provider == "gemini" else "OPENROUTER_REQUEST_GAP_SEC", "4.2" if provider == "gemini" else "3.1"))
        delay = gap - (time.monotonic() - self._last_request.get(provider, 0))
        pace_start=time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        self.request_stats['pacing_ms']=round(1000*(time.perf_counter()-pace_start),3)
        self._last_request[provider] = time.monotonic()
        key = os.environ.get("GEMINI_API_KEY" if provider == "gemini" else "OPENROUTER_API_KEY", "")
        if not key:
            raise ProviderError("missing_credential")
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
            transport_start=time.perf_counter()
            generation={"temperature":config.LLM_TEMPERATURE,"maxOutputTokens":2048,"responseMimeType":"application/json"}
            if self.profile=='compact':
                generation.update(maxOutputTokens=384)
                if model.startswith('gemini-3'):generation['thinkingConfig']={'thinkingLevel':'minimal'}
            response = (self.session or requests).post(url, headers={"x-goog-api-key": key}, json={
                "systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                "generationConfig": generation,
            }, timeout=(8, config.LLM_TIMEOUT_SEC))
        else:
            if model != "openrouter/free" and not model.endswith(":free"):
                raise ProviderError("paid_model_blocked_use_free_suffix")
            transport_start=time.perf_counter()
            response = (self.session or requests).post("https://openrouter.ai/api/v1/chat/completions", headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            }, json={"model": model, "messages": messages, "max_tokens": 384 if self.profile=='compact' else 1200,
                     "temperature": config.LLM_TEMPERATURE, "response_format": {"type": "json_object"}},
                timeout=(8, config.LLM_TIMEOUT_SEC))
        self.request_stats['transport_ms']=round(1000*(time.perf_counter()-transport_start),3)
        if not response.ok:
            # Never include a URL, request body, credential, or response text in an exception.
            quota = ""
            if response.status_code == 429 and provider == "gemini":
                import re
                try:
                    details = response.json().get("error", {}).get("details", [])
                    ids = [v.get("quotaId", "") for d in details for v in d.get("violations", [])]
                    quota = ":" + ",".join(re.sub(r"[^A-Za-z0-9_-]", "", q)[:100] for q in ids) if ids else ""
                except Exception:
                    pass
            raise ProviderError(f"http_{response.status_code}{quota}")
        data = response.json()
        if provider == "gemini":
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts if not p.get("thought")), data.get("modelVersion", model), data.get("usageMetadata", {})
        return data["choices"][0]["message"]["content"], data.get("model", model), data.get("usage", {})


def discover() -> dict[str, Any]:
    """Public catalogs and authenticated Gemini discovery; no generation or billing."""
    result: dict[str, Any] = {}
    for provider, url, headers in [
        ("gemini", "https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")}),
        ("openrouter", "https://openrouter.ai/api/v1/models", {}),
    ]:
        try:
            response = requests.get(url, headers=headers, timeout=(8, 20))
            if not response.ok:
                result[provider] = {"status": f"http_{response.status_code}", "models": []}
                continue
            data = response.json()
            if provider == "gemini":
                models = [m["name"].removeprefix("models/") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
            else:
                models = [m["id"] for m in data.get("data", []) if m["id"].endswith(":free") and all(float(m.get("pricing", {}).get(k, 1)) == 0 for k in ("prompt", "completion"))]
            result[provider] = {"status": "ok", "models": models}
        except Exception as exc:
            result[provider] = {"status": type(exc).__name__, "models": []}
    return result
