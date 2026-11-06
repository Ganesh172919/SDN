"""Reproducible frozen-base LoRA fitting using only approved train episodes."""
from __future__ import annotations

import hashlib
import importlib.metadata
import math
import random
import time
from pathlib import Path

from .common import digest, now, read_rows, sha256, write, write_rows
from .dataset import verify_dataset
from .policy import ACTIONS, MODEL_DIR, MODEL_ID, REVISION, PROMPT_SHA256, encode_observations, load_base


def parameter_hash(parameters):
    result = hashlib.sha256()
    for name, value in sorted(parameters):
        result.update(name.encode())
        result.update(value.detach().cpu().contiguous().numpy().tobytes())
    return result.hexdigest()


def train(dataset, output, steps=120, batch_size=4, learning_rate=.002, rank=8, seed=77,
          initial_adapter=None, model_dir=MODEL_DIR, threads=4):
    import torch
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    if steps < 1 or batch_size < 1 or not 0 < learning_rate < .1 or rank < 1:
        raise ValueError("invalid training configuration")
    output, dataset = Path(output), Path(dataset)
    if output.exists():
        raise FileExistsError("candidate directory must be new and immutable")
    manifest = verify_dataset(dataset)
    rows = read_rows(dataset / "train.jsonl")  # Stress/holdout labels never enter optimization.
    groups = {action: [r for r in rows if r["action"] == action] for action in ACTIONS}
    if any(not values for values in groups.values()):
        raise ValueError("training requires all three action classes")
    torch.manual_seed(seed)
    rng = random.Random(seed)
    model, tokenizer, code_ids = load_base(model_dir, threads)
    if initial_adapter:
        from .common import artifact_identity
        artifact_identity(initial_adapter)
        model = PeftModel.from_pretrained(model, initial_adapter, is_trainable=True)
    else:
        model = get_peft_model(model, LoraConfig(task_type=TaskType.CAUSAL_LM, r=rank,
            lora_alpha=rank*2, lora_dropout=0.0, target_modules=["q_proj", "v_proj"], bias="none"))
    if any(parameter.requires_grad and "lora_" not in name for name, parameter in model.named_parameters()):
        raise AssertionError("only LoRA weights may be optimized")
    frozen = [(n, v) for n, v in model.named_parameters() if not v.requires_grad]
    adapted = [(n, v) for n, v in model.named_parameters() if v.requires_grad]
    frozen_before, initial_hash = parameter_hash(frozen), parameter_hash(adapted)
    total_parameters = sum(v.numel() for v in model.parameters())
    trainable_parameters = sum(v.numel() for _, v in adapted)
    optimizer = torch.optim.AdamW([v for _, v in adapted], lr=learning_rate, weight_decay=0.0)
    output.mkdir(parents=True)
    configuration = {"schema": "selfx.lora.training.v1", "base_model": MODEL_ID, "revision": REVISION,
        "prompt_sha256": PROMPT_SHA256, "dataset_manifest_sha256": sha256(dataset/"manifest.json"),
        "train_sha256": manifest["splits"]["train"]["sha256"], "seed": seed,
        "planned_steps": steps, "batch_size": batch_size, "learning_rate": learning_rate, "rank": rank,
        "target_modules": ["q_proj", "v_proj"], "selection": "fixed steps; no stress or holdout selection",
        "objective": "conditional cross entropy over three frozen vocabulary action tokens",
        "memory": "disabled; identical frozen prompt for base and adapter",
        "initial_adapter": str(Path(initial_adapter).resolve()) if initial_adapter else None,
        "initial_adapter_parameter_sha256": initial_hash, "frozen_parameter_sha256_before": frozen_before,
        "trainable_parameters": trainable_parameters, "total_parameters": total_parameters,
        "versions": {pkg: importlib.metadata.version(pkg) for pkg in ("torch", "transformers", "peft", "safetensors")},
        "started_at_utc": now()}
    write(output / "training_plan.json", configuration)
    log, started = [], time.perf_counter()
    model.train()
    for step in range(1, steps + 1):
        sampled = [rng.choice(groups[rng.choice(ACTIONS)]) for _ in range(batch_size)]
        batch = encode_observations(tokenizer, [r["observation"] for r in sampled])
        targets = torch.tensor([ACTIONS.index(r["action"]) for r in sampled])
        optimizer.zero_grad(set_to_none=True)
        logits = model(**batch, logits_to_keep=1).logits[:, -1, code_ids]
        loss = torch.nn.functional.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise ValueError("non-finite training loss")
        loss.backward()
        gradient = torch.nn.utils.clip_grad_norm_([v for _, v in adapted], 1.0)
        if not torch.isfinite(gradient):
            raise ValueError("non-finite adapter gradient")
        optimizer.step()
        log.append({"step": step, "loss": float(loss.detach()), "gradient_norm": float(gradient),
                    "elapsed_seconds": time.perf_counter()-started,
                    "episode_ids": [r["episode_id"] for r in sampled]})
        if step == 1:
            save(model, output / "checkpoint_1", configuration, log, frozen_before, initial_hash)
        if step % 10 == 0 or step == steps:
            print(f"LoRA step {step}/{steps}; loss={loss.item():.5f}; elapsed={time.perf_counter()-started:.1f}s", flush=True)
    if parameter_hash(frozen) != frozen_before:
        raise AssertionError("base model weights changed")
    save(model, output, configuration, log, frozen_before, initial_hash)
    return output


def save(model, folder, configuration, log, frozen_hash, initial_hash):
    folder.mkdir(parents=True, exist_ok=True)
    actual_frozen_hash = parameter_hash([(n, v) for n, v in model.named_parameters() if not v.requires_grad])
    if actual_frozen_hash != frozen_hash:
        raise AssertionError("frozen base changed before checkpoint publication")
    model.save_pretrained(folder, safe_serialization=True)
    adapted = [(n, v) for n, v in model.named_parameters() if v.requires_grad]
    current_hash = parameter_hash(adapted)
    write_rows(folder / "training_log.jsonl", log)
    write(folder / "training.json", {**configuration, "steps": log[-1]["step"],
        "status": "completed", "completed_at_utc": now(),
        "base_unchanged": True, "weights_changed": current_hash != initial_hash,
        "adapter_parameter_sha256": current_hash, "frozen_parameter_sha256_after": actual_frozen_hash,
        "training_log_sha256": sha256(folder/"training_log.jsonl"),
        "artifact_sha256": {n: sha256(folder/n) for n in ("adapter_config.json", "adapter_model.safetensors")}})
