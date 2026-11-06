"""Single-writer adapter registry with atomic activation and hash-linked audit."""
from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from .common import artifact_identity, digest, encoded, now, read, read_rows, sha256, write
from .evaluation import GatePolicy, verify_report
from .policy import REVISION

BASE = {"id": "base:" + REVISION, "artifact": None}


class Registry:
    def __init__(self, root, stress_sha256=None, policy=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.policy = policy or GatePolicy()
        contract = self.root / "contract.json"
        if not contract.exists():
            if not stress_sha256:
                raise ValueError("a frozen stress-set digest is required")
            with self.lock():
                if not contract.exists():
                    write(contract, {"schema": "selfx.lora.registry.v1", "stress_sha256": stress_sha256,
                                     "gate_policy": asdict(self.policy), "base": BASE})
        self.contract = read(contract)
        if self.contract.get("schema") != "selfx.lora.registry.v1" or self.contract.get("base") != BASE:
            raise ValueError("invalid registry contract")
        if policy is None:
            self.policy = GatePolicy(**self.contract["gate_policy"])
        if self.contract["gate_policy"] != asdict(self.policy):
            raise ValueError("registry thresholds are frozen")
        if stress_sha256 and self.contract["stress_sha256"] != stress_sha256:
            raise ValueError("registry stress campaign is frozen")

    @contextlib.contextmanager
    def lock(self):
        path = self.root / "writer.lock"
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("registry writer is busy; no policy change applied") from exc
        try:
            os.write(descriptor, encoded({"pid": os.getpid(), "created": now()}))
            os.fsync(descriptor)
            yield
        finally:
            os.close(descriptor)
            path.unlink()

    def audit(self):
        path = self.root / "audit.jsonl"
        events = read_rows(path) if path.exists() else []
        previous = None
        for event in events:
            core = {k: v for k, v in event.items() if k != "event_sha256"}
            if event["previous_event_sha256"] != previous or digest(core) != event["event_sha256"]:
                raise ValueError("registry audit chain mismatch")
            previous = event["event_sha256"]
        return events

    def _append(self, kind, **values):
        events = self.audit()
        event = {"sequence": len(events), "at_utc": now(), "kind": kind,
                 "previous_event_sha256": events[-1]["event_sha256"] if events else None, **values}
        event["event_sha256"] = digest(event)
        with (self.root / "audit.jsonl").open("ab") as handle:
            handle.write(encoded(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def path(self, entry):
        if entry.get("artifact") is None:
            if entry["id"] != BASE["id"]:
                raise ValueError("unknown base policy identity")
            return None
        if entry["artifact"] != "artifacts/"+entry["id"]:
            raise ValueError("non-canonical registry artifact path")
        result = (self.root / entry["artifact"]).resolve()
        if not result.is_relative_to(self.root / "artifacts") or artifact_identity(result) != entry["id"]:
            raise ValueError("registry artifact verification failed")
        return result

    def active(self):
        pointer = self.root / "active.json"
        if not pointer.exists():
            return {**BASE, "version": 0}
        entry = read(pointer)
        self._validate_pointer(entry)
        self.path(entry)
        return entry

    def _validate_pointer(self,entry):
        if (not isinstance(entry,dict) or set(entry) != {"id","artifact","version","previous","activation_event_sha256"}
            or type(entry["version"]) is not int or entry["version"] < 1):
            raise ValueError("invalid activation pointer")
        events = self.audit()
        linked = [event for event in events if event["event_sha256"] == entry["activation_event_sha256"]]
        if (len(linked) != 1 or linked[0]["kind"] not in {"promoted", "rolled_back"}
            or linked[0]["target"] != {k:entry[k] for k in ("id","artifact")}):
            raise ValueError("activation has no matching audit event")
        event = linked[0]
        prior = entry["previous"]
        expected_previous = event["incumbent"] if event["kind"]=="promoted" else BASE["id"]
        if not isinstance(prior,dict) or set(prior)!={"id","artifact"} or prior["id"] != expected_previous:
            raise ValueError("rollback predecessor differs from authorized activation")
        if prior["id"]==BASE["id"]:
            if prior != BASE:
                raise ValueError("invalid base predecessor")
        elif (prior["artifact"]!="artifacts/"+prior["id"] or not any(
            e["kind"]=="promoted" and e["target"]==prior and e["sequence"] < event["sequence"] for e in events)):
            raise ValueError("rollback predecessor was never promoted")
        if "version" in event and event["version"]!=entry["version"]:
            raise ValueError("activation version differs from audit")
        return event

    def register(self, candidate):
        candidate = Path(candidate).resolve()
        identity = artifact_identity(candidate)
        with self.lock():
            target = self.root / "artifacts" / identity
            if not target.resolve().is_relative_to(self.root):
                raise ValueError("registry artifact target escapes registry")
            target.mkdir(parents=True, exist_ok=True)
            for name in ("adapter_config.json", "adapter_model.safetensors", "training.json", "training_log.jsonl"):
                if not (target/name).exists():
                    shutil.copy2(candidate/name, target/name)
            if artifact_identity(target) != identity:
                raise ValueError("registered artifact differs from candidate")
            entry = {"id": identity, "artifact": target.relative_to(self.root).as_posix()}
            self._append("registered", target=entry)
        return entry

    def consider(self, candidate_entry, evaluation_folder, dataset):
        if not isinstance(candidate_entry,dict) or set(candidate_entry)!={"id","artifact"} or candidate_entry["artifact"] is None:
            raise ValueError("promotion requires a canonical registered adapter entry")
        with self.lock():
            candidate_path = self.path(candidate_entry)
            before = self.active()
            try:
                from .dataset import verify_dataset
                from .common import read_rows
                data = verify_dataset(dataset)
                training = read(candidate_path/"training.json")
                if (training["dataset_manifest_sha256"] != sha256(Path(dataset)/"manifest.json")
                    or training["train_sha256"] != data["splits"]["train"]["sha256"]):
                    raise ValueError("candidate training lineage differs from evaluated dataset")
                allowed_ids = {row["episode_id"] for row in read_rows(Path(dataset)/"train.jsonl")}
                optimization = read_rows(candidate_path/"training_log.jsonl")
                if len(optimization) != training["steps"] or any(
                    episode not in allowed_ids for step in optimization for episode in step["episode_ids"]):
                    raise ValueError("optimization log contains non-training episodes")
                report, decision = verify_report(evaluation_folder, candidate_entry["id"], before["id"],
                    self.contract["stress_sha256"], self.policy, dataset)
            except (ValueError, KeyError, OSError) as exc:
                self._append("rejected", target=candidate_entry, incumbent=before["id"],
                             reasons=["invalid_evidence:" + type(exc).__name__])
                raise
            if not decision["accepted"]:
                self._append("rejected", target=candidate_entry, incumbent=before["id"],
                    reasons=decision["reasons"], evaluation_sha256=sha256(Path(evaluation_folder)/"report.json"))
                return {**decision, "active": before}
            event = self._append("promoted", target=candidate_entry, incumbent=before["id"],
                version=before["version"]+1,
                delta_pi={"policy_adapter_from": before["id"], "policy_adapter_to": candidate_entry["id"],
                          "V_weights_action_mask": "unchanged; owned by the separate slow-loop bridge"},
                evaluation_sha256=sha256(Path(evaluation_folder)/"report.json"),
                dataset_manifest_sha256=report["dataset_manifest_sha256"], reasons=decision["reasons"])
            entry = {**candidate_entry, "version": before["version"]+1,
                     "previous": {k: before[k] for k in ("id", "artifact")},
                     "activation_event_sha256": event["event_sha256"]}
            write(self.root/"active.json", entry)
            return {**decision, "active": entry}

    def rollback(self, reason, expected_id=None):
        with self.lock():
            pointer = self.root/"active.json"
            try:
                before = read(pointer) if pointer.exists() else {**BASE,"version":0}
            except (ValueError,OSError):
                before = {**BASE,"version":0}
            if not isinstance(before,dict):
                before={**BASE,"version":0}
            if expected_id and before.get("id") != expected_id:
                raise ValueError("stale rollback request")
            target=BASE
            trusted_pointer=False
            try:
                self._validate_pointer(before)
                trusted_pointer=True
                target=before["previous"]
                self.path(target)
            except (ValueError, OSError, KeyError, TypeError):
                target = BASE
            version = before.get("version",0)
            if not trusted_pointer:
                events=self.audit()
                version=max([e.get("version",0) for e in events if type(e.get("version",0)) is int]+
                            [sum(e["kind"] in {"promoted","rolled_back"} for e in events)])
            incumbent=before.get("id") if isinstance(before.get("id"),str) else None
            event = self._append("rolled_back", target=target, incumbent=incumbent,
                                 version=version+1,reason=str(reason)[:300])
            entry = {**target, "version": version+1,
                     "previous": BASE, "activation_event_sha256": event["event_sha256"]}
            write(pointer, entry)
            return entry
