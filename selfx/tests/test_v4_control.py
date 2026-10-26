import json,time
from pathlib import Path
import pytest
from agent.loss_aware_memory import LossAwareMemory,capacity_policy,meter_decision,loss_aware_policy
from agent.deadline_provider import DeadlineProvider
from agent.providers import ProviderError
from agent.rule_demo import SimulatedRuleTable
from eval.simulator import FluidNetwork,decision_for

def hang_worker(connection,provider,model,messages):
    connection.send({'event':'request_started'});time.sleep(20)
    connection.send({'event':'result','choice':{'action':'reroute','rationale':'late'},'audit':[]})

def reusable_worker(connection,provider,model,messages):
    while messages is not None:
        connection.send({'event':'request_started'})
        connection.send({'event':'result','choice':{'action':'no_op','rationale':'fixture'},'audit':[{'status':'ok','provider':provider,'elapsed_ms':1}]})
        messages=connection.recv()

def test_idle_worker_reuses_connection_and_closes(monkeypatch):
    monkeypatch.setenv('GEMINI_REQUEST_GAP_SEC','0')
    client=DeadlineProvider('gemini',budget_seconds=3.8,worker=reusable_worker)
    try:
        assert client.choose([])['action']=='no_op'
        pid=client.process.pid
        assert client.choose([])['action']=='no_op' and client.process.pid==pid
        assert len(client.audit)==2 and all(a['request_started'] for a in client.audit)
    finally:client.close()
    assert client.process is None and client.connection is None

def test_hanging_provider_returns_before_control_deadline(monkeypatch):
    monkeypatch.setenv('GEMINI_REQUEST_GAP_SEC','0')
    client=DeadlineProvider('gemini',budget_seconds=3.0,worker=hang_worker)
    start=time.perf_counter()
    with pytest.raises(ProviderError,match='local_deadline'):client.choose([])
    assert time.perf_counter()-start<4.0
    assert client.last_proposal is None and client.audit[-1]['status']=='deadline_timeout'
    assert client.audit[-1]['request_started']
    import multiprocessing
    assert not multiprocessing.active_children()

def test_pacing_admission_has_no_hidden_request(monkeypatch):
    monkeypatch.setenv('GEMINI_REQUEST_GAP_SEC','10')
    client=DeadlineProvider('gemini');client.last_started['gemini']=time.monotonic()
    with pytest.raises(ProviderError,match='pacing_admission'):client.choose([])
    assert client.audit[-1]['status']=='deferred' and not client.audit[-1]['request_started']
    client.last_started.clear()

def test_capacity_aware_meter_reduces_avoidable_drops():
    net=FluidNetwork();d={'primary_background_mbps':5,'alternate_background_mbps':8,'elephant_mbps':5.2};s=net.summary(d)
    new=capacity_policy(s,d);old=decision_for('rate_limit',d,'old')
    assert net.validate(d,new).allowed and new.rate_limit_kbps==4900
    assert net.evaluate(d,new).loss_pct<net.evaluate(d,old).loss_pct
    boundary={'primary_background_mbps':8.6722,'alternate_background_mbps':7.5781,'elephant_mbps':8.06}
    for h in (0,.1,.3):
        candidate=meter_decision(net.summary(boundary),boundary,h)
        assert candidate.rate_limit_kbps==6449 and net.validate(boundary,candidate).allowed

def test_memory_preserves_parameters_and_prior_cycles(tmp_path):
    net=FluidNetwork();d={'primary_background_mbps':5,'alternate_background_mbps':8,'elephant_mbps':5.2};s=net.summary(d)
    memory=LossAwareMemory(str(tmp_path/'memory.json'),autosave=False)
    for cycle,h in enumerate((0,.1,.3)*3):
        decision=meter_decision(s,d,h);memory.add_record(cycle,s,'rate_limit',decision.model_dump(),1-h,'measured')
    scores,used=memory.meter_estimates(s,9)
    assert len(scores)==3 and all(v['support']==3 for v in scores.values()) and max(used)<9
    decision,used=loss_aware_policy(net,s,d,memory,9)
    assert decision.rate_limit_kbps==5000
    assert memory.meter_estimates(s,0)==({},[])

def test_simulated_rule_expiry_and_default_restored():
    rules=SimulatedRuleTable();d={'elephant_mbps':6}
    one=rules.apply(decision_for('reroute',d,'route'),0,'api',{'action':'reroute'})
    assert one['installed_rule']['instructions'][-1]['actions'][0]['port']==3
    two=rules.apply(decision_for('no_op',d,'healthy'),1,'healthy_bypass')
    assert len(two['expired_rules'])==1 and two['installed_rule'] is None and two['effective_output_port']==2
    assert rules.finish(2)['active_rules']==[]

def test_bounded_controller_reuses_fallback_with_honest_origin(tmp_path):
    from agent.bounded_control import BoundedController
    net=FluidNetwork();d={'primary_background_mbps':5,'alternate_background_mbps':1,'elephant_mbps':7};s=net.summary(d)
    memory=LossAwareMemory(str(tmp_path/'cache.json'),autosave=False);controller=BoundedController()
    class Failing:
        audit=[]
        def choose(self,messages):raise ProviderError('local_deadline')
    controller.llm=Failing()
    first=controller.decide(net,s,d,memory,0);second=controller.decide(net,s,d,memory,1)
    assert first[1]=='deadline_fallback' and second[1]=='local_rule_cache'
    assert second[0].action=='reroute' and net.validate(d,second[0]).allowed
    # Evidence for a different cap cannot label the current exploration as
    # supported memory. A fresh provider proposal is still required.
    d={'primary_background_mbps':5,'alternate_background_mbps':8,'elephant_mbps':5.2};s=net.summary(d)
    memory.meter_estimates=lambda state,cycle:({0.:{'support':3,'lower':.1,'mean':.11},.1:{'support':2,'lower':.1,'mean':.11},.3:{'support':2,'lower':.1,'mean':.11}},[0,1,2])
    class Answering:
        audit=[]
        def choose(self,messages):return {'action':'rate_limit','rationale':'fixture suggestion'}
    controller.llm=Answering()
    assert controller.decide(net,s,d,memory,3)[1]=='api'

def test_busy_queue_does_not_trigger_api_for_healthy_load(tmp_path):
    from agent.bounded_control import BoundedController
    net=FluidNetwork();net.queue=[.5,.5];d={'primary_background_mbps':2,'alternate_background_mbps':2,'elephant_mbps':1}
    memory=LossAwareMemory(str(tmp_path/'healthy.json'),autosave=False);controller=BoundedController()
    decision,origin,_,_=controller.decide(net,net.summary(d),d,memory,0)
    assert origin=='healthy_bypass' and decision.action=='no_op' and not controller.llm.audit
