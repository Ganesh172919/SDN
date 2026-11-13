"""
Free-tier LLM decision client for the SELF-X slow loop.

Design goals
------------
1. **Only free endpoints.** Every OpenRouter model id must end in ``:free``;
   anything else is refused before a request is built, so the study can never
   incur billing. Google AI Studio models are used on their free tier.
2. **A chain that spans providers.** Free tiers have small daily request
   ceilings (OpenRouter allows 50 free-model requests per day on an unfunded
   key). When the primary provider is exhausted the chain overflows to the next
   free endpoint rather than stalling the control loop. Which endpoint actually
   answered is recorded per decision and reported in the paper.
3. **Record and replay.** Every live call is appended to a JSONL trace keyed by
   the SHA-256 of (role, chain, prompt). A later run with ``mode="replay"``
   resolves the same keys from that trace, so a reviewer with no API key
   reproduces the exact numbers reported in the paper. ``mode="enumerate"``
   counts the prompts a live run would need without spending any quota.
4. **Bounded wait.** A deadline is enforced per call. On timeout, rate-limit or
   empty content the client walks the chain and finally returns a declared
   ``fallback`` decision, which the caller must account for as a control-plane
   miss rather than silently treat as a model answer.
5. **No credential ever leaves this module.** Errors carry sanitized codes only;
   no URL, request body or provider payload appears in an exception.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

#: Supported free providers. A chain entry is "<provider>:<model>"; a bare id
#: means OpenRouter, which is the default provider for this study.
PROVIDERS = ("openrouter", "gemini")

#: Actions the datapath can express. Mirrors ``agent.schemas.DecisionOutput``.
VALID_ACTIONS = ("no_op", "reroute", "rate_limit")


class DeciderError(RuntimeError):
    """Sanitized failure. Never carries a key, URL or raw provider payload."""


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

@dataclass
class CallRecord:
    """One slow-loop decision: live, cached, replayed, enumerated or fallen back."""

    key: str
    role: str
    model_requested: str
    model_served: str
    status: str                 # ok | fallback | cached | replayed | missing
    elapsed_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    attempts: int = 0
    #: Wall-clock of the attempt that actually succeeded, excluding the time
    #: spent walking past exhausted or rate-limited endpoints. ``elapsed_ms``
    #: is the full chain walk; this is what one healthy endpoint costs.
    served_ms: float = 0.0
    error_codes: List[str] = field(default_factory=list)
    content: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def extract_json_object(text: Optional[str]) -> Dict[str, Any]:
    """Pull the first JSON object out of a model reply.

    Free endpoints frequently wrap JSON in prose or a fenced block, and several
    spend their whole token budget on hidden reasoning and return no content at
    all, so a bare ``json.loads`` is not enough.
    """
    if not text or not text.strip():
        raise DeciderError("empty_model_content")
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(body)
        if not match:
            raise DeciderError("no_json_object_in_content")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise DeciderError("unparsable_json_object") from exc
    if not isinstance(value, dict):
        raise DeciderError("json_not_an_object")
    return value


def prompt_key(role: str, models: Sequence[str], messages: Sequence[Dict[str, str]]) -> str:
    """Stable cache key over the role and the exact prompt.

    The model chain is deliberately *not* part of the key: a decision recorded
    from one free endpoint stays valid when a later run finds a different
    endpoint available, which is what makes the trace usable across days.
    """
    blob = json.dumps({"role": role, "messages": list(messages)},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class FreeModelDecider:
    """Calls free-tier models, or replays a recorded trace."""

    def __init__(
        self,
        trace_path: Path,
        primary_model: Optional[str] = None,
        fallback_models: Optional[Sequence[str]] = None,
        mode: str = "live",
        deadline_sec: float = 25.0,
        request_gap_sec: Optional[float] = None,
        max_tokens: int = 700,
        temperature: float = 0.0,
    ) -> None:
        if mode not in {"live", "replay", "enumerate"}:
            raise ValueError("mode must be 'live', 'replay' or 'enumerate'")
        self.mode = mode
        self.trace_path = Path(trace_path)
        self.deadline_sec = deadline_sec
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_gap_sec = (
            request_gap_sec
            if request_gap_sec is not None
            else float(os.environ.get("OPENROUTER_REQUEST_GAP_SEC", "1.5"))
        )

        primary = primary_model or os.environ.get(
            "OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
        if fallback_models is None:
            raw = os.environ.get("OPENROUTER_FALLBACK_MODELS", "")
            overflow = os.environ.get("OVERFLOW_FREE_MODELS", "")
            fallback_models = [m.strip() for m in (raw + "," + overflow).split(",") if m.strip()]

        chain: List[Tuple[str, str]] = []
        for entry in [primary] + list(fallback_models):
            head, sep, tail = entry.partition(":")
            if sep and head in PROVIDERS:
                provider, model = head, tail
            else:
                provider, model = "openrouter", entry
            if provider == "openrouter" and not model.endswith(":free"):
                raise DeciderError("paid_openrouter_model_blocked_use_free_suffix")
            if (provider, model) not in chain:
                chain.append((provider, model))
        self._chain = chain
        self.model_chain: List[str] = [f"{p}:{m}" for p, m in chain]

        self._session = requests.Session()
        #: Per-provider pacing. Free tiers meter per minute as well as per day,
        #: so a single global gap either starves the fast provider or trips the
        #: slow one.
        self._last_request_at: Dict[str, float] = {}
        self._provider_gap = {
            "openrouter": self.request_gap_sec,
            "gemini": float(os.environ.get("GEMINI_REQUEST_GAP_SEC", "4.5")),
        }
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_trace()

        self.records: List[CallRecord] = []
        self.missing: Dict[str, Dict[str, Any]] = {}
        #: Consecutive failures per chain entry. A free tier that has hit its
        #: daily ceiling fails every request for the rest of the day, so retrying
        #: it on every decision would add seconds of dead wait to each one. After
        #: `breaker_threshold` consecutive failures an entry is skipped for the
        #: rest of the run and the skip is reported in the statistics.
        self._consecutive_failures: Dict[str, int] = {}
        self._tripped_at: Dict[str, float] = {}
        self.breaker_threshold = int(os.environ.get("SELFX_CIRCUIT_BREAKER", "3"))
        #: A tripped endpoint is retried after this cooldown (half-open breaker),
        #: because a per-minute rate limit clears while a daily ceiling does not.
        self.breaker_cooldown_sec = float(os.environ.get("SELFX_BREAKER_COOLDOWN", "600"))
        #: A 429 is ambiguous: it can be per-minute throttling (clears in
        #: seconds) or a daily ceiling (does not clear at all). We pay the
        #: backoff ONCE per endpoint to find out which it is; after that a 429
        #: from the same endpoint trips it immediately, so an exhausted free tier
        #: costs the control loop one probe rather than a wait on every decision.
        self.rate_limit_retries = int(os.environ.get("SELFX_RATE_LIMIT_RETRIES", "2"))
        self._backoff_spent: set = set()
        self.tripped: List[str] = []
        self.rate_limit_waits = 0
        self.transport_ms = 0.0
        self.live_calls = 0
        self.cache_hits = 0
        self.fallback_calls = 0

    # -- trace -------------------------------------------------------------- #

    def _load_trace(self) -> None:
        if not self.trace_path.exists():
            if self.mode == "replay":
                raise DeciderError("replay_trace_missing")
            return
        with self.trace_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("key") and rec.get("status") == "ok" and rec.get("parsed"):
                    self._cache[rec["key"]] = rec

    def _append_trace(self, record: CallRecord) -> None:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_json(), separators=(",", ":")) + "\n")

    # -- transport ---------------------------------------------------------- #

    def _pace(self, provider: str) -> None:
        gap = self._provider_gap.get(provider, self.request_gap_sec)
        wait = gap - (time.monotonic() - self._last_request_at.get(provider, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request_at[provider] = time.monotonic()

    def _post(self, provider: str, model: str, messages: Sequence[Dict[str, str]],
              disable_reasoning: bool) -> Tuple[bool, Optional[str], str, Dict[str, int], str]:
        """Issue one request. Returns (ok, content, served_model, usage, error_code).

        ``self.transport_ms`` is set to the time the HTTP exchange itself took.
        The inter-request gap we impose to stay inside a free tier's per-minute
        limit is deliberately excluded: it is our politeness, not the endpoint's
        latency, and charging it to the model would overstate the very number
        this study is built around.
        """
        self._pace(provider)
        exchange_started = time.perf_counter()
        if provider == "gemini":
            key = os.environ.get("GEMINI_API_KEY", "")
            if not key:
                raise DeciderError("missing_credential_gemini")
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            contents = [
                {"role": "model" if m["role"] == "assistant" else "user",
                 "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] != "system"
            ]
            response = self._session.post(
                GEMINI_URL.format(model=model),
                headers={"x-goog-api-key": key},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": self.temperature,
                        "maxOutputTokens": self.max_tokens,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=(8, self.deadline_sec),
            )
            self.transport_ms = round(1000 * (time.perf_counter() - exchange_started), 2)
            if not response.ok:
                return False, None, model, {}, f"http_{response.status_code}"
            body = response.json()
            parts = (body.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            usage = body.get("usageMetadata", {}) or {}
            return True, content, body.get("modelVersion", model), {
                "prompt_tokens": int(usage.get("promptTokenCount", 0) or 0),
                "completion_tokens": int(usage.get("candidatesTokenCount", 0) or 0),
            }, ""

        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise DeciderError("missing_credential_openrouter")
        payload: Dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        if disable_reasoning:
            payload["reasoning"] = {"enabled": False}
        response = self._session.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(8, self.deadline_sec),
        )
        self.transport_ms = round(1000 * (time.perf_counter() - exchange_started), 2)
        if not response.ok:
            return False, None, model, {}, f"http_{response.status_code}"
        body = response.json()
        choices = body.get("choices") or []
        content = choices[0]["message"].get("content") if choices else None
        usage = body.get("usage") or {}
        return True, content, body.get("model", model), {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        }, ""

    # -- public ------------------------------------------------------------- #

    def decide(
        self,
        role: str,
        messages: Sequence[Dict[str, str]],
        validate: Callable[[Dict[str, Any]], Dict[str, Any]],
        fallback: Dict[str, Any],
    ) -> CallRecord:
        """Return one validated decision for ``role``.

        ``validate`` normalises and range-checks the parsed object and raises
        ``DeciderError`` for an unusable reply. ``fallback`` is the declared local
        decision installed when no endpoint produced a usable answer.
        """
        key = prompt_key(role, self.model_chain, messages)

        cached = self._cache.get(key)
        if cached is not None and cached.get("parsed") is not None:
            self.cache_hits += 1
            record = CallRecord(
                key=key, role=role,
                model_requested=cached.get("model_requested", self.model_chain[0]),
                model_served=cached.get("model_served", ""),
                status="replayed" if self.mode == "replay" else "cached",
                elapsed_ms=float(cached.get("elapsed_ms", 0.0)),
                # A record written before served_ms existed reports 0.0 rather
                # than borrowing its chain latency, so it is excluded from the
                # endpoint-latency statistic instead of inflating it.
                served_ms=float(cached.get("served_ms", 0.0) or 0.0),
                prompt_tokens=int(cached.get("prompt_tokens", 0)),
                completion_tokens=int(cached.get("completion_tokens", 0)),
                attempts=int(cached.get("attempts", 0)),
                content=cached.get("content"), parsed=cached["parsed"],
            )
            self.records.append(record)
            return record

        if self.mode == "enumerate":
            # Budget-planning pass: count the prompts a live run needs without
            # spending any of the free-tier daily allowance.
            self.missing.setdefault(key, {"role": role, "messages": list(messages)})
            record = CallRecord(key=key, role=role, model_requested=self.model_chain[0],
                                model_served="", status="missing", elapsed_ms=0.0,
                                parsed=dict(fallback))
            self.records.append(record)
            return record

        if self.mode == "replay":
            raise DeciderError(f"replay_cache_miss:{role}:{key[:12]}")

        errors: List[str] = []
        started = time.perf_counter()
        attempts = 0
        for provider, model in self._chain:
            entry = f"{provider}:{model}"
            if self._consecutive_failures.get(entry, 0) >= self.breaker_threshold:
                if time.monotonic() - self._tripped_at.get(entry, 0.0) < self.breaker_cooldown_sec:
                    continue
                self._consecutive_failures[entry] = 0  # half-open: give it one go
            for disable_reasoning in (True, False):
                attempts += 1
                attempt_started = time.perf_counter()
                try:
                    ok, content, served, usage, code = self._post(
                        provider, model, messages, disable_reasoning)
                except requests.RequestException as exc:
                    errors.append(f"{provider}:transport:{type(exc).__name__}")
                    self._trip(entry)
                    break
                except DeciderError as exc:
                    errors.append(f"{provider}:{exc}")
                    self._trip(entry)
                    break
                if code == "http_429" and entry in self._backoff_spent:
                    # Already probed this endpoint with a backoff earlier in the
                    # run and it is still refusing: treat it as exhausted.
                    errors.append(f"{provider}:http_429_exhausted")
                    self._trip(entry)
                    break
                if code == "http_429":
                    self._backoff_spent.add(entry)
                    retried = False
                    for attempt_index in range(self.rate_limit_retries):
                        self.rate_limit_waits += 1
                        time.sleep(2.0 * (attempt_index + 1))
                        attempts += 1
                        try:
                            ok, content, served, usage, code = self._post(
                                provider, model, messages, disable_reasoning)
                        except (requests.RequestException, DeciderError):
                            break
                        if ok or code != "http_429":
                            retried = True
                            break
                    if not retried and not ok:
                        errors.append(f"{provider}:http_429_after_backoff")
                        self._trip(entry)
                        break
                if not ok:
                    errors.append(f"{provider}:{code}")
                    self._trip(entry)
                    # "reasoning is mandatory" is the only case worth an instant retry
                    if code == "http_400" and disable_reasoning and provider == "openrouter":
                        continue
                    break
                try:
                    parsed = validate(extract_json_object(content))
                except DeciderError as exc:
                    errors.append(f"{provider}:{exc}")
                    continue

                record = CallRecord(
                    key=key, role=role, model_requested=f"{provider}:{model}",
                    model_served=f"{provider}:{served}", status="ok",
                    elapsed_ms=round(1000 * (time.perf_counter() - started), 2),
                    served_ms=self.transport_ms,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    attempts=attempts, error_codes=errors, content=content, parsed=parsed,
                )
                self._consecutive_failures[entry] = 0
                self.live_calls += 1
                self._cache[key] = record.to_json()
                self._append_trace(record)
                self.records.append(record)
                return record

        record = CallRecord(
            key=key, role=role, model_requested=self.model_chain[0], model_served="",
            status="fallback", elapsed_ms=round(1000 * (time.perf_counter() - started), 2),
            attempts=attempts, error_codes=errors, content=None, parsed=dict(fallback),
        )
        self.fallback_calls += 1
        self.records.append(record)
        self._append_trace(record)
        return record

    def _trip(self, entry: str) -> None:
        count = self._consecutive_failures.get(entry, 0) + 1
        self._consecutive_failures[entry] = count
        if count >= self.breaker_threshold:
            self._tripped_at[entry] = time.monotonic()
            if entry not in self.tripped:
                self.tripped.append(entry)

    # -- stats -------------------------------------------------------------- #

    def stats(self) -> Dict[str, Any]:
        served = [r for r in self.records if r.status in ("ok", "cached", "replayed")]
        chain = [r.elapsed_ms for r in self.records if r.status in ("ok", "cached", "replayed")]
        latencies = [r.served_ms for r in self.records
                     if r.status in ("ok", "cached", "replayed") and r.served_ms > 0]
        models: Dict[str, int] = {}
        for rec in self.records:
            if rec.model_served:
                models[rec.model_served] = models.get(rec.model_served, 0) + 1
        return {
            "mode": self.mode,
            "model_chain": self.model_chain,
            "total_decisions": len(self.records),
            "live_requests": self.live_calls,
            "cache_or_replay_hits": self.cache_hits,
            "declared_fallbacks": self.fallback_calls,
            "served_fraction": round(len(served) / len(self.records), 4) if self.records else 0.0,
            # Endpoint latency: one healthy free-tier request.
            "mean_served_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_served_latency_ms": (
                round(sorted(latencies)[min(len(latencies) - 1, int(0.95 * len(latencies)))], 2)
                if latencies else 0.0),
            # Chain latency: the same request including the walk past exhausted or
            # rate-limited endpoints, which is what the control loop actually waits.
            "mean_chain_latency_ms": round(sum(chain) / len(chain), 2) if chain else 0.0,
            "p95_chain_latency_ms": (
                round(sorted(chain)[min(len(chain) - 1, int(0.95 * len(chain)))], 2)
                if chain else 0.0),
            "prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "completion_tokens": sum(r.completion_tokens for r in self.records),
            "models_served": models,
            "uncovered_prompts": len(self.missing),
            "circuit_breaker_threshold": self.breaker_threshold,
            "endpoints_tripped": list(self.tripped),
            "breaker_cooldown_sec": self.breaker_cooldown_sec,
            "rate_limit_backoffs": self.rate_limit_waits,
        }


# --------------------------------------------------------------------------- #
# Validators for the three prompt roles used by the study
# --------------------------------------------------------------------------- #

def validate_action(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a datapath action proposal."""
    action = str(obj.get("action", "")).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "admit": "no_op", "allow": "no_op", "none": "no_op", "keep": "no_op",
        "noop": "no_op", "hold": "no_op",
        "ratelimit": "rate_limit", "throttle": "rate_limit", "meter": "rate_limit",
        "drop": "rate_limit", "shape": "rate_limit",
        "re_route": "reroute", "route": "reroute", "switch_path": "reroute",
        "redirect": "reroute",
    }
    action = aliases.get(action, action)
    if action not in VALID_ACTIONS:
        raise DeciderError(f"unknown_action:{action[:24]}")

    rate = obj.get("rate_limit_kbps")
    if action == "rate_limit":
        try:
            rate = int(float(rate))
        except (TypeError, ValueError):
            raise DeciderError("rate_limit_without_numeric_kbps")
        if not (0 < rate <= 100_000):
            raise DeciderError("rate_limit_out_of_range")
    else:
        rate = None

    reason = str(obj.get("reason") or obj.get("rationale") or "model proposal")[:240]
    return {"action": action, "rate_limit_kbps": rate, "reason": reason}


def validate_policy(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a slow-loop policy update (V, w, action mask)."""
    try:
        d_v = float(obj.get("d_v", obj.get("delta_v", 0.0)))
    except (TypeError, ValueError):
        raise DeciderError("non_numeric_d_v")
    d_v = max(-4.0, min(4.0, d_v))

    raw_weights = obj.get("weight_deltas") or obj.get("weights") or {}
    if not isinstance(raw_weights, dict):
        raise DeciderError("weight_deltas_not_an_object")
    deltas: Dict[str, float] = {}
    for name in ("latency", "throughput", "loss", "energy", "resource"):
        try:
            deltas[name] = max(-0.15, min(0.15, float(raw_weights.get(name, 0.0))))
        except (TypeError, ValueError):
            deltas[name] = 0.0

    raw_mask = obj.get("enable_actions") or obj.get("allowed_actions") or []
    if isinstance(raw_mask, str):
        raw_mask = [raw_mask]
    mask = tuple(dict.fromkeys(
        a for a in (str(x).strip().lower() for x in raw_mask) if a in VALID_ACTIONS))
    specialists = obj.get("specialists") if isinstance(obj.get("specialists"), dict) else {}
    reason = str(obj.get("reason") or obj.get("rationale") or "policy proposal")[:240]
    return {"d_v": d_v, "weight_deltas": deltas, "enable_actions": mask,
            "specialists": {k: str(v)[:160] for k, v in list(specialists.items())[:5]},
            "reason": reason}


def validate_critique(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a self-critique verdict over the agent's own previous proposal."""
    verdict = str(obj.get("verdict", "keep")).strip().lower()
    if verdict not in ("keep", "revise"):
        verdict = "revise" if "rev" in verdict else "keep"
    revised: Optional[Dict[str, Any]] = None
    if verdict == "revise":
        candidate = obj.get("revised_action") or obj.get("action")
        payload = candidate if isinstance(candidate, dict) else {
            "action": candidate,
            "rate_limit_kbps": obj.get("rate_limit_kbps"),
            "reason": obj.get("reason"),
        }
        try:
            revised = validate_action(payload)
        except DeciderError:
            verdict, revised = "keep", None
    lesson = str(obj.get("lesson") or obj.get("reason") or "")[:240]
    return {"verdict": verdict, "revised_action": revised, "lesson": lesson}
