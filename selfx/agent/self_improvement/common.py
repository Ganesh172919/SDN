"""Deterministic manifests, durable atomic writes and artifact verification."""
from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_invalid_constant)


def _invalid_constant(value):
    raise ValueError("non-finite JSON constant is not allowed")


def atomic_bytes(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write(path, value):
    atomic_bytes(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode("utf-8"))


def write_rows(path, rows):
    atomic_bytes(path, b"".join(encoded(row) + b"\n" for row in rows))


def read_rows(path):
    return [json.loads(line, parse_constant=_invalid_constant) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def artifact_identity(folder):
    folder = Path(folder).resolve()
    manifest = read(folder / "training.json")
    if manifest.get("status") != "completed" or manifest.get("base_unchanged") is not True:
        raise ValueError("candidate has no completed frozen-base training record")
    if manifest.get("weights_changed") is not True or type(manifest.get("steps")) is not int or manifest["steps"] < 1:
        raise ValueError("candidate has no demonstrated adapter weight update")
    hash_keys = ("frozen_parameter_sha256_before", "frozen_parameter_sha256_after",
                 "initial_adapter_parameter_sha256", "adapter_parameter_sha256")
    if any(not isinstance(manifest.get(k), str) or not re.fullmatch(r"[0-9a-f]{64}",manifest[k]) for k in hash_keys):
        raise ValueError("candidate parameter hashes are missing or invalid")
    if (manifest.get("frozen_parameter_sha256_before") != manifest.get("frozen_parameter_sha256_after")
        or manifest.get("initial_adapter_parameter_sha256") == manifest.get("adapter_parameter_sha256")):
        raise ValueError("candidate parameter-change evidence is inconsistent")
    if sha256(folder / "training_log.jsonl") != manifest.get("training_log_sha256"):
        raise ValueError("training log hash mismatch")
    expected = manifest.get("artifact_sha256", {})
    if set(expected) != {"adapter_config.json", "adapter_model.safetensors"}:
        raise ValueError("candidate artifact manifest is incomplete")
    for name, checksum in expected.items():
        if sha256(folder / name) != checksum:
            raise ValueError("candidate artifact hash mismatch")
    if "deployment" in manifest:
        deployment = manifest["deployment"]
        fraction = finite(deployment.get("adapter_fraction"), "adapter fraction")
        if (not 0 < fraction <= 1 or deployment.get("mask") != "sha256_observation_v1"
            or deployment.get("other_observations") != "pinned_bare_base"):
            raise ValueError("unsupported adapter deployment contract")
    return digest({"training_sha256": sha256(folder / "training.json"), "files": expected})
