"""Package a bounded adapter rollout without changing trained tensor values."""
from pathlib import Path
import shutil

from .common import artifact_identity,digest,read,read_rows,sha256,write
from .policy import PROMPT_SHA256, REVISION, pure_cache_key


def canary(source,target,fraction=.25):
    source,target=Path(source),Path(target)
    identity=artifact_identity(source)
    if not 0<fraction<=1 or target.exists():
        raise ValueError("use a new candidate directory and a fraction in (0,1]")
    target.mkdir(parents=True)
    for name in ("adapter_config.json","adapter_model.safetensors","training.json","training_log.jsonl"):
        shutil.copy2(source/name,target/name)
    training=read(target/"training.json")
    training["deployment"]={"adapter_fraction":fraction,"mask":"sha256_observation_v1",
        "other_observations":"pinned_bare_base","source_candidate_sha256":identity,
        "purpose":"bounded adoption; same mask in weight-attribution comparison"}
    write(target/"training.json",training)
    if (source/"checkpoint_1").exists():
        canary(source/"checkpoint_1",target/"checkpoint_1",fraction)
    return target


def seed_cache_from_full_evaluation(report_folder,candidate,cache_folder):
    """Reuse already measured raw LM probabilities; never invent a model response."""
    report_folder,candidate,cache_folder=Path(report_folder),Path(candidate),Path(cache_folder)
    report=read(report_folder/"report.json")
    if (report["candidate_sha256"] != artifact_identity(candidate)
        or report["incumbent_sha256"] != "base:"+REVISION or report["prompt_sha256"] != PROMPT_SHA256
        or sha256(report_folder/"trace.jsonl") != report["trace_sha256"]
        or read(candidate/"training.json").get("deployment",{}).get("adapter_fraction",1.)!=1.):
        raise ValueError("only verified full-policy inference can seed a pure prediction cache")
    records=read_rows(report_folder/"trace.jsonl")
    for role,adapter in (("incumbent",None),("candidate",candidate)):
        key=pure_cache_key(adapter)
        entries={digest(r["observation"]):{"action":r["requested_action"],"probabilities":r["probabilities"]}
                 for r in records if r["role"]==role}
        write(cache_folder/(key+".json"),{"schema":"selfx.inference.cache.v1","key":key,
            "entries":entries,"entries_sha256":digest(entries),"source_trace_sha256":report["trace_sha256"]})
