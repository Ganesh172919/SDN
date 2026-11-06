"""A pinned causal language model whose constrained action tokens are LoRA-adapted.

The vocabulary projection and base transformer stay frozen. No learned policy
may construct a switch ID, route or arbitrary rate; local code and the existing
independent guard retain that responsibility.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from agent.loss_aware_memory import meter_decision
from eval.simulator import FluidNetwork, decision_for
from .common import artifact_identity, digest, read, sha256, write
from .dataset import observation

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
PROJECT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT / ".models/smollm2-135m-instruct-12fd25f7"
ACTIONS = ("no_op", "reroute", "rate_limit")
CODES = (" A", " B", " C")


def prompt(obs):
    cap = obs["capacity_mbps"]
    total = obs["primary_background_mbps"] + obs["elephant_mbps"]
    alternate = obs["alternate_background_mbps"] + obs["elephant_mbps"]
    # Exactly the same fixed representation is used for bare-base and adapters.
    return ("SDN control. A=keep primary, B=reroute, C=bounded meter. "
            "Choose the safe action for this observation.\n"
            f"Primary demand={total:.3f}; capacity={cap:.3f}; "
            f"alternate demand after reroute={alternate:.3f}; alternate ceiling={.9*cap:.3f}.\n"
            f"Primary overloaded={'yes' if total > cap else 'no'}; "
            f"reroute feasible={'yes' if alternate <= .9*cap else 'no'}.\nAction:")


PROMPT_SHA256 = digest({"template_version": 1, "example": prompt({
    "capacity_mbps": 10., "primary_background_mbps": 4., "alternate_background_mbps": 2., "elephant_mbps": 7.}),
    "actions": ACTIONS, "codes": CODES, "memory": "disabled"})


def ensure_model(folder=MODEL_DIR):
    folder = Path(folder)
    required = ("config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
                "special_tokens_map.json", "model.safetensors")
    if not all((folder / name).is_file() for name in required):
        from huggingface_hub import snapshot_download
        snapshot_download(MODEL_ID, revision=REVISION, local_dir=folder,
                          allow_patterns=list(required), token=False)
    manifest_path = folder / "download_manifest.json"
    if manifest_path.exists():
        manifest = read(manifest_path)
        if manifest["repo"] != MODEL_ID or manifest["revision"] != REVISION:
            raise ValueError("unexpected base-model revision")
        for name in required:
            if sha256(folder / name) != manifest["files"][name]["sha256"]:
                raise ValueError("base-model artifact hash mismatch")
    else:
        from .common import write
        write(manifest_path, {"repo": MODEL_ID, "revision": REVISION,
            "files": {name: {"sha256": sha256(folder / name), "bytes": (folder / name).stat().st_size}
                      for name in required}})
    return folder


def load_base(folder=MODEL_DIR, threads=4):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(threads)
    folder = ensure_model(folder)
    tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True, trust_remote_code=False)
    tokenizer.padding_side = "left"
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(folder, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="sdpa")
    model.config.use_cache = False
    tokens = [tokenizer.encode(c, add_special_tokens=False) for c in CODES]
    if any(len(t) != 1 for t in tokens) or len({t[0] for t in tokens}) != 3:
        raise ValueError("action codes must be distinct single vocabulary tokens")
    return model, tokenizer, [t[0] for t in tokens]


def encode_observations(tokenizer, observations):
    inputs = tokenizer([prompt(o) for o in observations], padding=True, return_tensors="pt", add_special_tokens=True)
    if inputs["input_ids"].shape[1] > 192:
        raise ValueError("observation exceeds the frozen input budget")
    return inputs


def pure_cache_key(adapter=None):
    return digest({"base_revision": REVISION, "prompt_sha256": PROMPT_SHA256,
        "weights": sha256(Path(adapter)/"adapter_model.safetensors") if adapter else None,
        "config": sha256(Path(adapter)/"adapter_config.json") if adapter else None})


def rollout_selected(obs, fraction):
    return int(digest(obs)[:16], 16) / float(2**64) < fraction


class LoRAPolicy:
    def __init__(self, candidate=None, incumbent=None, model_dir=MODEL_DIR, threads=4, cache_dir=None):
        self.model, self.tokenizer, self.code_ids = load_base(model_dir, threads)
        self.identities = {"base": "base:" + REVISION}
        self.fractions = {"base": 0.0}
        self.cache_keys = {"base": pure_cache_key()}
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if candidate is not None:
            from peft import PeftModel
            identity = artifact_identity(candidate)
            self.model = PeftModel.from_pretrained(self.model, candidate, adapter_name="candidate", is_trainable=False)
            self.identities["candidate"] = identity
            self.fractions["candidate"] = read(Path(candidate)/"training.json").get("deployment", {}).get("adapter_fraction", 1.0)
            self.cache_keys["candidate"] = pure_cache_key(candidate)
        if incumbent is not None:
            if candidate is None:
                from peft import PeftModel
                self.model = PeftModel.from_pretrained(self.model, incumbent, adapter_name="incumbent", is_trainable=False)
            else:
                self.model.load_adapter(incumbent, adapter_name="incumbent", is_trainable=False)
            self.identities["incumbent"] = artifact_identity(incumbent)
            self.fractions["incumbent"] = read(Path(incumbent)/"training.json").get("deployment", {}).get("adapter_fraction", 1.0)
            self.cache_keys["incumbent"] = pure_cache_key(incumbent)
        if any(not 0 < f <= 1 for k,f in self.fractions.items() if k != "base"):
            raise ValueError("adapter rollout fraction must be in (0,1]")
        self.model.eval()

    def add_adapter(self,name,folder):
        if name in self.identities or name=="base":
            raise ValueError("adapter name already loaded")
        identity=artifact_identity(folder)
        self.model.load_adapter(folder,adapter_name=name,is_trainable=False)
        self.identities[name]=identity
        self.fractions[name]=read(Path(folder)/"training.json").get("deployment",{}).get("adapter_fraction",1.)
        self.cache_keys[name]=pure_cache_key(folder)
        self.model.eval()

    def predict(self, observations, adapter="candidate", batch_size=16):
        if adapter not in self.identities:
            raise ValueError("unknown adapter")
        selected = [i for i,o in enumerate(observations) if adapter != "base" and rollout_selected(o,self.fractions[adapter])]
        selected_set = set(selected)
        remainder = [i for i in range(len(observations)) if i not in selected_set]
        answers = [None]*len(observations)
        for indices, role in ((selected,adapter),(remainder,"base")):
            if not indices:
                continue
            values = self._pure_predict([observations[i] for i in indices],role,batch_size)
            for i,value in zip(indices,values):
                answers[i] = {**value,"policy_sha256":self.identities[adapter],
                              "adapter_used":role != "base", "adapter_fraction":self.fractions[adapter]}
        return answers

    def _pure_predict(self, observations, adapter, batch_size):
        import torch
        cache_path = self.cache_dir/(self.cache_keys[adapter]+".json") if self.cache_dir else None
        cache = {"schema":"selfx.inference.cache.v1","key":self.cache_keys[adapter],"entries":{}}
        if cache_path and cache_path.exists():
            cache = read(cache_path)
            if cache["key"] != self.cache_keys[adapter] or digest(cache["entries"]) != cache["entries_sha256"]:
                raise ValueError("inference cache integrity mismatch")
        missing = {digest(o):o for o in observations if digest(o) not in cache["entries"]}
        missing_items = list(missing.items())
        if adapter != "base":
            self.model.set_adapter(adapter)
        context = self.model.disable_adapter() if adapter == "base" and hasattr(self.model, "disable_adapter") else contextlib.nullcontext()
        with context, torch.inference_mode():
            for start in range(0, len(missing_items), batch_size):
                items = missing_items[start:start+batch_size]
                batch = encode_observations(self.tokenizer, [o for _,o in items])
                scores = self.model(**batch, logits_to_keep=1).logits[:, -1, self.code_ids]
                if not torch.isfinite(scores).all():
                    raise ValueError("non-finite policy scores")
                probabilities = scores.softmax(-1).tolist()
                for (key,_),values in zip(items,probabilities):
                    index = max(range(3), key=lambda i: values[i])
                    cache["entries"][key] = {"action": ACTIONS[index], "probabilities": dict(zip(ACTIONS, values))}
                if cache_path:
                    cache["entries_sha256"] = digest(cache["entries"])
                    write(cache_path,cache)
                if len(missing_items)>32 and ((start+len(items))%96==0 or start+len(items)==len(missing_items)):
                    print(f"  {adapter}: {start+len(items)}/{len(missing_items)} uncached observations",flush=True)
        return [cache["entries"][digest(o)] for o in observations]

    def decide(self, summary, demand, adapter="candidate"):
        obs = observation(summary)
        self.last_prediction = self.predict([obs], adapter)[0]
        action = self.last_prediction["action"]
        decision = locally_bound(action, obs, demand)
        guard = FluidNetwork().validate(demand, decision)
        return decision if guard.allowed else decision_for("no_op", demand, "Independent adapter safety veto")


def locally_bound(action, obs, demand):
    if action == "rate_limit":
        return meter_decision({"simulation": obs}, demand, .1, "LoRA action; rate synthesized by local safety bounds")
    return decision_for(action, demand, "Pinned causal LM action-token policy; exact flow parameters constructed locally")
