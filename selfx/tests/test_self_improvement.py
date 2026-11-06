"""Dataset isolation, independent stress gating, registry safety and real LoRA updates."""
import json
from pathlib import Path

import pytest

from agent.self_improvement.common import artifact_identity, read, sha256, write, write_rows
from agent.self_improvement.dataset import build_dataset, normalise, verify_dataset
from agent.self_improvement.evaluation import GatePolicy, evaluate, judge
from agent.self_improvement.policy import ACTIONS, REVISION
from agent.self_improvement.registry import Registry
from agent.self_improvement.runtime import RegisteredPolicy
from agent.loss_aware_memory import capacity_policy
from agent.reward import compute_reward
from eval.simulator import FluidNetwork, decision_for


def episode(seed, cycle, action):
    p, a, e = {"no_op": (2., 1., 2.), "reroute": (6., 1., 6.), "rate_limit": (5., 8., 7.)}[action]
    demand = {"primary_background_mbps": p+seed*.001, "alternate_background_mbps": a, "elephant_mbps": e}
    net = FluidNetwork()
    state = net.summary(demand)
    chosen = capacity_policy(state, demand) if action == "rate_limit" else decision_for(action, demand, "completed test episode")
    out = net.evaluate(demand, chosen)
    before = net.evaluate(demand, decision_for("no_op", demand, "reference"))
    return {"seed": seed, "cycle": cycle, "profile": "mixed", "provenance": "simulation",
        "state_summary": state, "params": chosen.model_dump(), "outcome": out.__dict__,
        "reward": max(0., compute_reward(before.metrics(),out.metrics()).reward),
        "approved": net.validate(demand,chosen).allowed, "reflection": "Measured and completed."}


@pytest.fixture
def dataset(tmp_path):
    sources = []
    for seed in (1,2,3):
        path = tmp_path/f"replay_{seed}.jsonl"
        write_rows(path,[episode(seed,i,a) for i,a in enumerate(ACTIONS)])
        sources.append(path)
    folder = tmp_path/"dataset"
    build_dataset(sources,folder,{"train":[1],"stress":[2],"holdout":[3]})
    return folder


def test_completed_approved_only_and_failure_retention(tmp_path):
    unsafe = episode(1,4,"reroute")
    unsafe["approved"] = False
    negative = episode(1,5,"rate_limit"); negative["reward"] = -.1
    source = tmp_path/"episodes.jsonl"
    write_rows(source,[episode(seed,i,a) for seed in (1,2,3) for i,a in enumerate(ACTIONS)]+[unsafe,negative])
    folder = tmp_path/"data"
    manifest = build_dataset([source],folder,{"train":[1],"stress":[2],"holdout":[3]})
    assert manifest["splits"]["train"]["count"] == 3
    assert manifest["excluded"]["count"] == 2
    assert len((folder/"excluded.jsonl").read_text().splitlines()) == 2
    incomplete = episode(1,0,"no_op");del incomplete["outcome"]
    with pytest.raises(ValueError,match="completed"):
        normalise(incomplete)


def test_split_groups_and_observation_leakage_fail_closed(tmp_path):
    with pytest.raises(ValueError,match="overlap"):
        build_dataset([],tmp_path/"bad",{"train":[1],"stress":[1],"holdout":[3]})
    rows = [episode(seed,0,"no_op") for seed in (1,2,3)]
    import copy
    rows[1]=copy.deepcopy(rows[0]);rows[1]["seed"]=2
    path = tmp_path/"duplicate.jsonl";write_rows(path,rows)
    with pytest.raises(ValueError,match="duplicate observation"):
        build_dataset([path],tmp_path/"bad2",{"train":[1],"stress":[2],"holdout":[3]})


def test_dataset_hash_and_provenance_are_required(dataset):
    (dataset/"train.jsonl").write_text("{}\n",encoding="utf-8")
    with pytest.raises(ValueError,match="hash"):
        verify_dataset(dataset)
    raw=episode(1,0,"no_op");del raw["provenance"]
    with pytest.raises(ValueError,match="provenance"):
        normalise(raw)


@pytest.fixture
def candidate(dataset,tmp_path,monkeypatch):
    torch=pytest.importorskip("torch")
    pytest.importorskip("peft")
    from transformers import LlamaConfig,LlamaForCausalLM
    from agent.self_improvement import training
    def tiny_base(*args,**kwargs):
        model=LlamaForCausalLM(LlamaConfig(vocab_size=16,hidden_size=16,intermediate_size=32,
            num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2,max_position_embeddings=32))
        base=tmp_path/"tiny_base";model.config.save_pretrained(base)
        model.config._name_or_path=str(base)
        model.name_or_path=str(base)
        return model,None,[1,2,3]
    def encode(tokenizer,obs):
        inputs=torch.tensor([[4,5,6,7] for _ in obs])
        return {"input_ids":inputs,"attention_mask":torch.ones_like(inputs)}
    monkeypatch.setattr(training,"load_base",tiny_base)
    monkeypatch.setattr(training,"encode_observations",encode)
    folder=training.train(dataset,tmp_path/"candidate",steps=3,batch_size=2,rank=2)
    return folder


def test_real_lora_weights_change_and_base_is_frozen(candidate):
    manifest=read(candidate/"training.json")
    assert manifest["weights_changed"] and manifest["base_unchanged"]
    assert manifest["frozen_parameter_sha256_before"] == manifest["frozen_parameter_sha256_after"]
    assert manifest["adapter_parameter_sha256"] != manifest["initial_adapter_parameter_sha256"]
    assert manifest["trainable_parameters"] < manifest["total_parameters"]
    assert artifact_identity(candidate)
    with (candidate/"adapter_model.safetensors").open("ab") as handle:handle.write(b"tamper")
    with pytest.raises(ValueError,match="hash"):
        artifact_identity(candidate)


class ReplayActor:
    def __init__(self,candidate_id,incumbent_id="base:"+REVISION):
        self.identities={"candidate":candidate_id,"base":"base:"+REVISION,"incumbent":incumbent_id}
    def predict(self,observations,adapter):
        answers=[]
        for obs in observations:
            demand={k:obs[k] for k in ("primary_background_mbps","alternate_background_mbps","elephant_mbps")}
            action=capacity_policy({"simulation":obs},demand).action if adapter=="candidate" else "no_op"
            answers.append({"action":action,"probabilities":{a:float(a==action) for a in ACTIONS},
                            "policy_sha256":self.identities[adapter]})
        return answers


def make_evaluation(candidate,dataset,folder):
    evaluate(candidate,dataset,folder,model=ReplayActor(artifact_identity(candidate)))


def test_registry_promotion_rejection_rollback_and_stale_report(candidate,dataset,tmp_path):
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate)
    evidence=tmp_path/"evaluation";make_evaluation(candidate,dataset,evidence)
    promoted=registry.consider(entry,evidence,dataset)
    assert promoted["accepted"] and registry.active()["id"]==entry["id"]
    before=(registry.root/"active.json").read_bytes()
    # Original report compares against base; it cannot overwrite a different incumbent.
    with pytest.raises(ValueError,match="stale"):
        registry.consider(entry,evidence,dataset)
    assert (registry.root/"active.json").read_bytes()==before
    restored=registry.rollback("test restoration",expected_id=entry["id"])
    assert restored["id"].startswith("base:")
    assert [e["kind"] for e in registry.audit()]==["registered","promoted","rejected","rolled_back"]


def test_gate_replays_metrics_and_refuses_holdout_or_changed_data(candidate,dataset,tmp_path):
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate)
    evidence=tmp_path/"evaluation";make_evaluation(candidate,dataset,evidence)
    trace=[json.loads(line) for line in (evidence/"trace.jsonl").read_text().splitlines()]
    trace[0]["reward"]+=100
    write_rows(evidence/"trace.jsonl",trace)
    report=read(evidence/"report.json");report["trace_sha256"]=sha256(evidence/"trace.jsonl");write(evidence/"report.json",report)
    with pytest.raises(ValueError,match="independent replay"):
        registry.consider(entry,evidence,dataset)
    assert registry.active()["id"].startswith("base:")
    report["split"]="holdout";write(evidence/"report.json",report)
    with pytest.raises(ValueError,match="holdout"):
        registry.consider(entry,evidence,dataset)


def test_runtime_fault_automatically_rolls_back(candidate,dataset,tmp_path):
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate)
    evidence=tmp_path/"eval";make_evaluation(candidate,dataset,evidence)
    registry.consider(entry,evidence,dataset)
    def unavailable(*args,**kwargs):raise RuntimeError("injected model failure")
    runtime=RegisteredPolicy(registry,policy_factory=unavailable)
    demand={"primary_background_mbps":4.,"alternate_background_mbps":2.,"elephant_mbps":7.}
    assert runtime.decide(FluidNetwork().summary(demand),demand).action=="no_op"
    assert runtime.last_event["rollback"]=="completed"
    assert registry.active()["id"].startswith("base:")


def test_registry_lock_and_audit_tampering_are_detected(tmp_path):
    registry=Registry(tmp_path/"registry","frozen-stress")
    with registry.lock():
        with pytest.raises(RuntimeError,match="busy"):
            with registry.lock():pass
    registry.rollback("initial base restoration")
    events=registry.audit();events[0]["reason"]="changed"
    write_rows(registry.root/"audit.jsonl",events)
    with pytest.raises(ValueError,match="chain"):
        registry.active()


def test_corrupt_active_artifact_rolls_back_but_missing_telemetry_does_not(candidate,dataset,tmp_path):
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate)
    evidence=tmp_path/"eval";make_evaluation(candidate,dataset,evidence)
    registry.consider(entry,evidence,dataset)
    runtime=RegisteredPolicy(registry)
    demand={"primary_background_mbps":4.,"alternate_background_mbps":2.,"elephant_mbps":7.}
    before=(registry.root/"active.json").read_bytes()
    assert runtime.decide({},demand).action=="no_op"
    assert (registry.root/"active.json").read_bytes()==before
    with (registry.path(entry)/"adapter_model.safetensors").open("ab") as handle:handle.write(b"corrupt")
    assert runtime.decide(FluidNetwork().summary(demand),demand).action=="no_op"
    assert runtime.last_event["rollback"]=="completed"
    assert registry.active()["id"].startswith("base:")


def test_registered_provider_uses_local_provenance_without_network(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from agent.providers import RestLLM
    from agent.schemas import DecisionOutput
    from agent.self_improvement import runtime
    class Local:
        def __init__(self,registry):
            self.policy=SimpleNamespace(last_event={"origin":"local_lora","policy_sha256":"tested"})
        def invoke(self,schema,messages):return schema(action="no_op",rationale="local test")
    def forbidden(*args,**kwargs):raise AssertionError("local policy made a network request")
    monkeypatch.setattr(runtime,"LocalAdapterLLM",Local)
    monkeypatch.setattr("requests.post",forbidden)
    provider=RestLLM("local_lora",model=str(tmp_path))
    assert provider.with_structured_output(DecisionOutput).invoke([{"role":"user","content":"state"}]).action=="no_op"
    assert provider.audit[-1]["network_request"] is False
    assert provider.audit[-1]["origin"]=="local_lora"


def test_bounded_rollout_uses_exact_base_and_adapter_predictions(candidate,tmp_path,monkeypatch):
    import torch
    from transformers import LlamaConfig,LlamaForCausalLM
    from agent.self_improvement import policy
    from agent.self_improvement.deployment import canary
    def tiny_base(*args,**kwargs):
        torch.manual_seed(77)
        model=LlamaForCausalLM(LlamaConfig(vocab_size=16,hidden_size=16,intermediate_size=32,
            num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2,max_position_embeddings=32))
        return model,None,[1,2,3]
    def encode(tokenizer,observations):
        x=torch.tensor([[4,5,6,7] for _ in observations]);return {"input_ids":x,"attention_mask":torch.ones_like(x)}
    monkeypatch.setattr(policy,"load_base",tiny_base);monkeypatch.setattr(policy,"encode_observations",encode)
    bounded=canary(candidate,tmp_path/"bounded",.25)
    assert sha256(bounded/"adapter_model.safetensors")==sha256(candidate/"adapter_model.safetensors")
    observations=[normalise(episode(i+10,0,"no_op"))["observation"] for i in range(50)]
    actor=policy.LoRAPolicy(bounded,cache_dir=tmp_path/"cache")
    mixed=actor.predict(observations)
    assert any(r["adapter_used"] for r in mixed) and any(not r["adapter_used"] for r in mixed)
    for obs,answer in zip(observations,mixed):
        role="candidate" if answer["adapter_used"] else "base"
        expected=actor._pure_predict([obs],role,1)[0]
        assert answer["action"]==expected["action"]
        assert answer["probabilities"]==expected["probabilities"]
    cached=next((tmp_path/"cache").glob("*.json"));data=read(cached)
    data["entries"][next(iter(data["entries"]))]["action"]="corrupt";write(cached,data)
    with pytest.raises(ValueError,match="cache integrity"):
        actor.predict(observations)


@pytest.mark.parametrize("content",['{broken', '[]', '{}', '{"id":"untrusted","version":999}'])
def test_malformed_active_pointer_returns_noop_and_recovers_base(tmp_path,content):
    registry=Registry(tmp_path/"registry","frozen-stress")
    (registry.root/"active.json").write_text(content,encoding="utf-8")
    runtime=RegisteredPolicy(registry)
    demand={"primary_background_mbps":4.,"alternate_background_mbps":2.,"elephant_mbps":7.}
    assert runtime.decide(FluidNetwork().summary(demand),demand).action=="no_op"
    assert runtime.last_event["rollback"]=="completed"
    assert registry.active()["id"].startswith("base:")
    assert registry.active()["version"]==1


def test_rollback_never_activates_an_unpromoted_predecessor(candidate,dataset,tmp_path):
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate)
    evidence=tmp_path/"eval";make_evaluation(candidate,dataset,evidence)
    registry.consider(entry,evidence,dataset)
    weak=registry.register(candidate/"checkpoint_1")
    forged=read(registry.root/"active.json");forged["previous"]=weak;write(registry.root/"active.json",forged)
    with pytest.raises(ValueError,match="predecessor"):
        registry.active()
    rolled=registry.rollback("invalid predecessor")
    assert rolled["id"].startswith("base:") and rolled["id"]!=weak["id"]
    assert rolled["version"]==2


def test_gate_configuration_rejects_nonfinite_and_unsafe_allowances():
    with pytest.raises(ValueError):GatePolicy(min_mean_reward_gain=float('nan'))
    with pytest.raises(ValueError):GatePolicy(max_loss_regression_pct=-1)
    with pytest.raises(ValueError):GatePolicy(max_installed_safety_violations=1)


def test_completed_and_curated_rewards_are_independently_replayed(dataset):
    from agent.self_improvement.common import digest,read_rows
    raw=episode(1,0,"no_op");raw["reward"]=100
    with pytest.raises(ValueError,match="reward fails"):
        normalise(raw)
    rows=read_rows(dataset/"train.jsonl");rows[0]["reward"]=100
    rows[0]["episode_id"]=digest({k:rows[0][k] for k in ("seed","cycle","profile","observation","action","reward")})
    write_rows(dataset/"train.jsonl",rows)
    manifest=read(dataset/"manifest.json");manifest["splits"]["train"]["sha256"]=sha256(dataset/"train.jsonl");write(dataset/"manifest.json",manifest)
    with pytest.raises(ValueError,match="reward fails"):
        verify_dataset(dataset)


@pytest.mark.parametrize("field",["probabilities","decision","provenance"])
def test_gate_rejects_inconsistent_action_evidence(candidate,dataset,tmp_path,field):
    from agent.self_improvement.common import read_rows
    registry=Registry(tmp_path/"registry",read(dataset/"manifest.json")["splits"]["stress"]["sha256"])
    entry=registry.register(candidate);folder=tmp_path/"eval";make_evaluation(candidate,dataset,folder)
    trace=read_rows(folder/"trace.jsonl")
    if field=="probabilities":trace[0][field]={a:0. for a in ACTIONS}
    elif field=="decision":trace[0][field]["rationale"]="different action evidence"
    else:trace[0][field]="live"
    write_rows(folder/"trace.jsonl",trace)
    report=read(folder/"report.json");report["trace_sha256"]=sha256(folder/"trace.jsonl");write(folder/"report.json",report)
    with pytest.raises(ValueError):registry.consider(entry,folder,dataset)
    assert registry.active()["id"].startswith("base:")


def test_replay_sources_rebuild_portably_and_reject_path_escape(dataset,tmp_path):
    import shutil
    from agent.self_improvement.source_check import verify_sources
    portable=tmp_path/"portable";shutil.copytree(dataset,portable/"dataset")
    manifest=read(dataset/"manifest.json");mapping={}
    for old in manifest["source_sha256"]:
        target=portable/"replay"/Path(old).name;target.parent.mkdir(exist_ok=True)
        shutil.copy2(old,target);mapping[old]="replay/"+target.name
    source_map=portable/"source_map.json";write(source_map,{"sources":mapping})
    assert verify_sources(portable/"dataset",source_map)["splits_rebuilt"]==3
    mapping[next(iter(mapping))]="../../outside.jsonl";write(source_map,{"sources":mapping})
    with pytest.raises(ValueError,match="escapes"):
        verify_sources(portable/"dataset",source_map)
