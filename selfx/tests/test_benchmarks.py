from copy import deepcopy
import json
import math
from agent.guarded_memory import BalancedMemory, guarded_policy
from agent.providers import parse_json, ProviderError
from eval.run_benchmarks import scenario_trace, execute, bootstrap_interval, select, ORDER, SCENARIOS
from eval.simulator import FluidNetwork, decision_for
import pytest


def test_scenarios_are_reproducible_and_distinct():
    values=[scenario_trace(s,1740,24) for s in SCENARIOS]
    assert all(v==scenario_trace(s,1740,24) for s,v in zip(SCENARIOS,values))
    assert len({json.dumps(v) for v in values})==len(SCENARIOS)
    assert len({r['flow_id'] for r in values[0]})==24


def test_balanced_memory_retains_failures_recent_and_successes(tmp_path):
    memory=BalancedMemory(str(tmp_path/'m.json'),autosave=False)
    for i in range(100):memory.add_record(i,{'embedding_features':[1,1,1]},'no_op',{},(-1 if i%2 else 1)*i,'measured')
    records=memory.all_records()
    assert len(records)<=30 and records[-1]['cycle']==99
    assert any(r['reward']<0 for r in records) and any(r['reward']>0 for r in records)
    assert not (tmp_path/'m.json').exists()
    memory.flush();assert (tmp_path/'m.json').exists()


def test_guarded_memory_never_selects_overloaded_alternate(tmp_path):
    net=FluidNetwork();demand=scenario_trace('overload',1740,1)[0];summary=net.summary(demand)
    memory=BalancedMemory(str(tmp_path/'m.json'),autosave=False)
    memory.add_record(0,summary,'reroute',{},1,'old success under a similar state')
    decision,_=guarded_policy(net,summary,demand,memory)
    assert net.validate(demand,decision).allowed and decision.action!='reroute'


def test_benchmark_conservation_leakage_and_guard_ablations(tmp_path):
    trace=scenario_trace('mixed',1740,24)
    for condition in ORDER:
        rows=execute(condition,trace,'mixed',1740,tmp_path)
        previous=[0,0]
        for row in rows:
            assert all(i<row['cycle'] for i in json.loads(row['retrieved_cycles']))
            assert math.isclose(sum(previous)+row['offered_mbit'],row['delivered_mbit']+row['dropped_mbit']+row['queue_primary_mbit']+row['queue_alternate_mbit'],abs_tol=1e-6)
            previous=[row['queue_primary_mbit'],row['queue_alternate_mbit']]
        if condition=='A3':assert all(r['safety_allowed'] for r in rows)
    healthy=scenario_trace('light',1740,24)
    h1=execute('H1',healthy,'light',1740,tmp_path);a3=execute('A3',healthy,'light',1740,tmp_path)
    assert [r['installed_action'] for r in h1]==[r['installed_action'] for r in a3]==['no_op']*24


def test_paired_bootstrap_and_empty_provider_response():
    assert bootstrap_interval([0]*10)==[0.,0.]
    assert bootstrap_interval([1]) is None
    assert bootstrap_interval([1,2,3])==bootstrap_interval([1,2,3])
    with pytest.raises(ProviderError,match='empty_model_response'):parse_json(None)
