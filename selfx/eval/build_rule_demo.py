"""A complete offline learning demonstration, alongside actual provider replays."""
import json,time
from collections import Counter
import config
from agent.loss_aware_memory import LossAwareMemory,loss_aware_policy
from agent.rule_demo import SimulatedRuleTable
from agent.reward import compute_reward
from eval.run_adaptive_benchmarks import scenario_trace
from eval.simulator import FluidNetwork,decision_for

def main():
    folder=config.PROJECT_ROOT/'output/benchmarks/v4/rule_demo_offline';folder.mkdir(parents=True,exist_ok=True)
    trace=scenario_trace('recurring',1880,120);net=FluidNetwork();memory=LossAwareMemory(str(folder/'memory.json'),autosave=False);memory.clear();rules=SimulatedRuleTable();records=[]
    for cycle,demand in enumerate(trace):
        started=time.perf_counter();state=net.summary(demand);scores,_=memory.meter_estimates(state,cycle)
        decision,used=loss_aware_policy(net,state,demand,memory,cycle);guard=net.validate(demand,decision)
        assert guard.allowed
        origin='episodic_memory' if 'Episodic parameter' in decision.rationale else 'bounded_exploration' if 'exploration' in decision.rationale else 'local_rule'
        before=net.evaluate(demand,decision_for('no_op',demand,'counterfactual'));outcome=net.evaluate(demand,decision,commit=True);reward=compute_reward(before.metrics(),outcome.metrics()).reward
        reflection=f'Measured reward {reward:.6f}; loss {outcome.loss_pct:.6f}% including meter and overflow.'
        memory.add_record(cycle,state,decision.action,decision.model_dump(),reward,reflection)
        rule=rules.apply(decision,cycle,origin,None,{'parameter_evidence':scores})
        row={'provider':'offline','mode':'bounded','seed':1880,'cycle':cycle,'origin':origin,'control_elapsed_ms':1000*(time.perf_counter()-started),'deadline_miss':False,
            'latency_ms':outcome.latency_ms,'throughput_kbps':outcome.throughput_kbps,'loss_pct':outcome.loss_pct,'reward':reward,'retrieved_cycles':json.dumps(used)}
        records.append({'metrics':row,'demand':demand,'state':state,'decision':decision.model_dump(),'safety':guard.__dict__,'outcome':outcome.__dict__,
            'no_op_outcome':before.__dict__,'reflection':reflection,'provider_calls':[],'rule_event':rule})
    memory.flush();end=rules.finish(len(trace));(folder/'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in records)+'\n',encoding='utf-8')
    (folder/'rule_expiry.json').write_text(json.dumps([{'mode':'bounded','seed':1880,**end}],indent=2),encoding='utf-8')
    summary={'windows':len(records),'origins':dict(Counter(r['metrics']['origin'] for r in records)),'max_memory_records':len(memory.all_records()),'backend':'offline_policy','provenance':'simulation'}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))

if __name__=='__main__':main()
