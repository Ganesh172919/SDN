"""Read-only verification of Ganesh's retained LoRA lifecycle and attribution."""
import argparse
from pathlib import Path

from agent.self_improvement.common import artifact_identity,read,read_rows,sha256,write
from agent.self_improvement.dataset import verify_dataset
from agent.self_improvement.evaluation import paired_attribution,verify_report
from agent.self_improvement.policy import LoRAPolicy,REVISION
from agent.self_improvement.registry import Registry
from agent.self_improvement.training import parameter_hash


def verify(root,verify_weights=True,fresh_inference=False,source_map=None):
    root=Path(root)
    completion=read(root/"completion.json")
    assert completion["status"]=="completed" and completion["task_ids"]==[f"T{i}" for i in range(20,26)]
    dataset=root/"dataset"
    manifest=verify_dataset(dataset)
    from agent.self_improvement.source_check import verify_sources
    source_verification=verify_sources(dataset,source_map)
    candidate=root/"candidate"
    identity=artifact_identity(candidate)
    assert identity==completion["candidate_sha256"]
    registry=Registry(root/"registry")
    assert registry.active()["id"]==identity
    original_pointer=(registry.root/"active.json").read_bytes()
    _,promoted=verify_report(root/"promotion_stress",identity,"base:"+REVISION,
        manifest["splits"]["stress"]["sha256"],registry.policy,dataset)
    assert promoted["accepted"]
    early=artifact_identity(candidate/"checkpoint_1")
    _,rejected=verify_report(root/"rejection_stress",early,identity,
        manifest["splits"]["stress"]["sha256"],registry.policy,dataset)
    assert not rejected["accepted"]
    holdout,_=verify_report(root/"heldout_attribution",identity,"base:"+REVISION,
        manifest["splits"]["holdout"]["sha256"],registry.policy,dataset,expected_split="holdout")
    attribution=paired_attribution(holdout["summary"])
    assert attribution==holdout["attribution"]==completion["weight_attribution"]
    rollback=read(root/"rollback_demo.json")
    assert rollback["controlled_fault"] and rollback["runtime"]["rollback"]=="completed"
    assert rollback["fallback"]["action"]=="no_op" and rollback["restored"]["id"].startswith("base:")
    events=registry.audit()
    assert sum(e["kind"]=="promoted" for e in events)>=2
    assert any(e["kind"]=="rejected" for e in events) and any(e["kind"]=="rolled_back" for e in events)
    episodes=read_rows(root/"on_policy_replay/train_replay.jsonl")
    assert len(episodes)==24 and all(e["behavior"]=="active_adapter_on_policy" for e in episodes)
    training=read(candidate/"training.json")
    weight_checks={"adapter_artifact_hashes":"passed","training_log_hash":"passed"}
    if verify_weights:
        actor=LoRAPolicy(candidate)
        params=list(actor.model.named_parameters())
        frozen=parameter_hash([(n,v) for n,v in params if "lora_" not in n])
        adapted=parameter_hash([(n.replace(".candidate.",".default."),v) for n,v in params if "lora_" in n])
        assert frozen==training["frozen_parameter_sha256_before"]==training["frozen_parameter_sha256_after"]
        assert adapted==training["adapter_parameter_sha256"]
        assert adapted!=training["initial_adapter_parameter_sha256"]
        weight_checks.update({"reloaded_base_parameter_hash":"passed","reloaded_adapter_parameter_hash":"passed"})
    assert (registry.root/"active.json").read_bytes()==original_pointer
    result={"status":"passed","task_ids":completion["task_ids"],"split_counts":{k:v["count"] for k,v in manifest["splits"].items()},
        "trainable_parameters":training["trainable_parameters"],"total_parameters":training["total_parameters"],
        "stress_reward_gain":promoted["mean_reward_gain"],"rejection_reasons":rejected["reasons"],
        "weight_checks":weight_checks,"holdout_attribution":attribution,"audit_events":len(events),
        "on_policy_episodes":len(episodes),"installed_safety_violations":holdout["summary"]["candidate"]["installed_safety_violations"],
        "source_verification":source_verification,
        "scope":"trained language-model adapter; bounded adoption; frozen-replay network evidence"}
    if fresh_inference:
        from agent.self_improvement.prediction_check import verify_model_predictions
        result["fresh_model_predictions"]=verify_model_predictions(root)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default="output/self_improvement/ganesh_20261106/bounded_adoption")
    parser.add_argument("--skip-reload",action="store_true")
    parser.add_argument("--fresh-inference",action="store_true")
    parser.add_argument("--source-map")
    parser.add_argument("--output")
    args=parser.parse_args()
    result=verify(args.root,not args.skip_reload,args.fresh_inference,args.source_map)
    write(Path(args.output) if args.output else Path(args.root)/"verification.json",result)
    import json
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
