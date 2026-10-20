import json
from agent.fast_control import compact_messages
from eval.run_simulation import run_condition
from eval.run_adaptive_benchmarks import scenario_trace
from eval.simulator import FluidNetwork

def test_current_totals_are_separate_from_historical_episode_context():
    trace=scenario_trace('recurring',1790,6);net=FluidNetwork();current=net.summary(trace[1]);previous=net.summary(trace[5])
    messages=compact_messages(current,[{'state_summary':previous,'action':'rate_limit','reward':.1}])
    payload=json.loads(messages[-1]['content'])
    assert payload['primary_congested'] and payload['reroute_safe']
    assert payload['alternate_if_rerouted_mbps']<=9
    assert payload['episodes'][0]['alternate_if_rerouted_mbps']>9

def test_adaptive_controller_is_available_in_normal_project_run(tmp_path):
    trace=scenario_trace('recurring',1790,30)
    rows,details,audit=run_condition('A4',trace,1790,'offline',tmp_path)
    assert len(rows)==30 and not audit
    assert all(r['safety_allowed'] and r['reflection_origin']=='deterministic' for r in rows)
    assert all(all(i<r['metrics']['cycle'] for i in r['retrieved_cycles']) for r in details)
