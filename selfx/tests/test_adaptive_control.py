import json
from copy import deepcopy
import pytest
from agent.adaptive_memory import AdaptiveMemory,context,adaptive_policy
from agent.fast_control import FastController,ActionChoice
from agent.providers import ProviderError
from eval.simulator import FluidNetwork
from eval.run_adaptive_benchmarks import scenario_trace


def state(demand):return FluidNetwork().summary(demand)

def test_magnitude_and_capacity_regimes_remain_distinct(tmp_path):
    demand=scenario_trace('recurring',10,6)[2];s=state(demand)
    other=deepcopy(s);other['simulation']['primary_background_mbps']*=.5
    other['simulation']['alternate_background_mbps']*=.5;other['simulation']['elephant_mbps']*=.5
    assert context(s)!=context(other)
    memory=AdaptiveMemory(str(tmp_path/'m.json'),autosave=False)
    for i in range(4):memory.add_record(i,s,'rate_limit',{},.5,'observed')
    assert memory.estimates(other,5)[0]=={}
    assert memory.estimates(s,3)[0]['rate_limit']['support']==3
    assert 3 not in memory.estimates(s,3)[1]

def test_memory_learns_to_avoid_negative_action_and_survives_reload(tmp_path):
    demand=scenario_trace('recurring',10,6)[2];net=FluidNetwork();s=net.summary(demand)
    memory=AdaptiveMemory(str(tmp_path/'m.json'),autosave=False)
    for i in range(4):memory.add_record(i,s,'rate_limit',{},-.2,'measured harmful outcome')
    decision,used=adaptive_policy(net,s,demand,memory,4)
    assert decision.action=='no_op' and used==[0,1,2,3]
    memory.flush();restored=AdaptiveMemory(memory.path,autosave=False)
    assert restored.estimates(s,4)==memory.estimates(s,4)

def test_diverse_memory_is_bounded_and_keeps_latest(tmp_path):
    memory=AdaptiveMemory(str(tmp_path/'m.json'),autosave=False)
    for i,d in enumerate(scenario_trace('volatile',11,300)):
        memory.add_record(i,state(d),'rate_limit',{},(-1)**i*.2,'observed')
    assert len(memory.all_records())<=96
    assert memory.all_records()[-1]['cycle']==299
    assert {r['reward']>0 for r in memory.all_records()}=={True,False}

def test_fast_cache_revalidates_state_and_does_not_hide_failures(monkeypatch,tmp_path):
    controller=FastController();calls=[]
    def invoke(schema,messages):calls.append(1);return ActionChoice(action='reroute',rationale='Earlier API decision')
    monkeypatch.setattr(controller.llm,'_invoke',invoke)
    net=FluidNetwork();d=scenario_trace('recurring',12,6)[1];s=net.summary(d)
    memory=AdaptiveMemory(str(tmp_path/'m.json'),autosave=False)
    assert controller.decide(net,s,d,memory,0)[1]=='api'
    assert controller.decide(net,s,d,memory,1)[1]=='api_cache' and len(calls)==1
    assert controller.decide(net,s,d,memory,13)[1]=='api' and len(calls)==2
    s2=deepcopy(s);s2['simulation']['valid_reroute_out_port']=4
    controller.decide(net,s2,d,memory,14);assert len(calls)==3
    def fail(*args):raise ProviderError('http_429')
    monkeypatch.setattr(controller.llm,'_invoke',fail)
    controller.cache.clear();decision,origin,_,error=controller.decide(net,s,d,memory,15)
    assert origin=='fallback_heuristic' and error=='http_429' and net.validate(d,decision).allowed

def test_healthy_bypass_and_compact_mode_are_distinct(monkeypatch,tmp_path):
    c=FastController();d=scenario_trace('recurring',12,1)[0];s=state(d);m=AdaptiveMemory(str(tmp_path/'m.json'),autosave=False)
    assert c.decide(FluidNetwork(),s,d,m,0)[1]=='healthy_bypass'
    c.hybrid=False
    monkeypatch.setattr(c.llm,'_invoke',lambda *args:ActionChoice(action='no_op',rationale='healthy'))
    assert c.decide(FluidNetwork(),s,d,m,0)[1]=='api'

def test_new_traffic_is_reproducible_and_episode_actions_stay_feasible(tmp_path):
    from eval.run_benchmarks import execute
    for scenario in ('recurring','volatile'):
        trace=scenario_trace(scenario,1760,60)
        assert trace==scenario_trace(scenario,1760,60)
        rows=execute('A4',trace,scenario,1760,tmp_path)
        assert all(r['safety_allowed'] for r in rows)
        assert all(all(c<r['cycle'] for c in json.loads(r['retrieved_cycles'])) for r in rows)
