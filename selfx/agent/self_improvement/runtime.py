"""Use only a verified active adapter; fail closed and roll back on load errors."""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

from agent.schemas import DecisionOutput, ReflectionOutput
from eval.simulator import decision_for
from .common import read
from .dataset import observation
from .policy import LoRAPolicy
from .registry import Registry


class RegisteredPolicy:
    def __init__(self, registry, threads=4, policy_factory=LoRAPolicy):
        self.registry = registry if isinstance(registry, Registry) else Registry(registry)
        self.threads, self.policy_factory = threads, policy_factory
        self.actor, self.loaded_id, self.last_event = None, None, {}

    def decide(self, summary, demand):
        active = None
        observation_valid = False
        try:
            observation(summary)
            observation_valid = True
            active = self.registry.active()
            if self.loaded_id != active["id"]:
                candidate = self.registry.path(active)
                self.actor = self.policy_factory(candidate, threads=self.threads)
                self.loaded_id = active["id"]
            role = "base" if active["artifact"] is None else "candidate"
            decision = self.actor.decide(summary, demand, role)
            self.last_event = {"policy_sha256": active["id"], "version": active["version"],
                               "origin": "local_lora" if role == "candidate" else "local_base"}
            if hasattr(self.actor,"last_prediction"):
                self.last_event.update({k:self.actor.last_prediction[k] for k in ("adapter_used","adapter_fraction")})
            return decision
        except Exception as exc:
            self.actor, self.loaded_id = None, None
            self.last_event = {"origin": "local_lora_fail_closed", "error_code": type(exc).__name__}
            pointer_exists = (self.registry.root/"active.json").is_file()
            pointer_invalid = observation_valid and active is None and pointer_exists
            # Keep malformed pointers inside the no-op boundary. Never trust their rollback target.
            if observation_valid and active is None and pointer_exists:
                try:
                    raw = read(self.registry.root/"active.json")
                    active = raw if isinstance(raw,dict) else None
                except (OSError, ValueError):
                    active = None
            # Missing telemetry is an upstream data issue, not evidence of adapter regression.
            if observation_valid and pointer_exists and (pointer_invalid or active is None or active.get("artifact") is not None):
                try:
                    expected_id = active.get("id") if active and isinstance(active.get("id"),str) else None
                    self.registry.rollback("runtime_failure:" + type(exc).__name__, expected_id=expected_id)
                    self.last_event["rollback"] = "completed"
                except Exception as rollback_error:
                    self.last_event["rollback"] = type(rollback_error).__name__
            return decision_for("no_op", demand, "Local policy unavailable; explicit fail-closed no_op")


class LocalAdapterLLM:
    """Structured-output adapter for existing LangGraph decision/reflection calls.

    Decision weights are trainable. Reflection remains an explicit deterministic
    outcome summary, rather than claiming this action-token LoRA generates text.
    """
    def __init__(self, registry):
        self.policy = RegisteredPolicy(registry)

    def with_structured_output(self, schema):
        return SimpleNamespace(invoke=lambda messages: self.invoke(schema, messages))

    def invoke(self, schema, messages):
        text = str(messages[-1]["content"])
        if schema is ReflectionOutput:
            match = re.search(r"Computed reward: ([+-]?[\d.]+)", text)
            if not match:
                raise ValueError("measured reward is required for reflection")
            reward = float(match.group(1))
            verdict = "helped" if reward > 0 else "hurt" if reward < 0 else "was neutral"
            return schema(reflection=f"Measured reward {reward:.3f}: the bounded intervention {verdict}; retain this completed outcome for replay.")
        if schema is not DecisionOutput:
            raise ValueError("unsupported local structured-output schema")
        marker = "Current network state:\n"
        if marker not in text:
            raise ValueError("current-state prompt is required")
        state, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
        obs = observation(state)
        demand = {k: obs[k] for k in ("primary_background_mbps", "alternate_background_mbps", "elephant_mbps")}
        return self.policy.decide(state, demand)
