"""Fresh real-provider comparison, with full-cycle deadlines and rule evidence."""
import argparse,csv,hashlib,json,sys,time
from collections import Counter
from datetime import datetime,timezone
from statistics import mean
import numpy as np
import config
from agent.adaptive_memory import AdaptiveMemory
from agent.fast_control import FastController
from agent.loss_aware_memory import LossAwareMemory
from agent.bounded_control import BoundedController
from agent.rule_demo import SimulatedRuleTable
from agent.reward import compute_reward
from eval.run_adaptive_benchmarks import scenario_trace
from eval.run_simulation import local_path
from eval.simulator import FluidNetwork,decision_for

MODES={'previous':'Previous v3 hybrid, fixed 20% meter','bounded':'Bounded provider wait and loss-aware memory'}

def execute(mode,trace,seed,folder,provider,hybrid=True,realtime=False):
    net=FluidNetwork();rules=SimulatedRuleTable();bounded=mode=='bounded'
    memory=(LossAwareMemory if bounded else AdaptiveMemory)(str(folder/f'{mode}_{seed}_memory.json'),autosave=False);memory.clear()
    controller=(BoundedController if bounded else FastController)(provider,hybrid=hybrid)
    rows=[];details=[];schedule=time.perf_counter()
    for cycle,demand in enumerate(trace):
        observation_wait=max(0,schedule+cycle*5-time.perf_counter()) if realtime else 0
        if observation_wait:time.sleep(observation_wait)
        start=time.perf_counter();previous=list(net.queue);state=net.summary(demand);audit_start=len(controller.llm.audit)
        d,origin,used,error=controller.decide(net,state,demand,memory,cycle)
        guard=net.validate(demand,d);installed=d if guard.allowed else decision_for('no_op',demand,'Validation veto')
        before=net.evaluate(demand,decision_for('no_op',demand,'same-window measurement'))
        outcome=net.evaluate(demand,installed,commit=True);reward=compute_reward(before.metrics(),outcome.metrics()).reward
        reflection=f'Measured reward {reward:.6f}; total loss {outcome.loss_pct:.6f}% including meter drops.'
        memory.add_record(cycle,state,installed.action,installed.model_dump(),reward,reflection)
        audit=controller.llm.audit[audit_start:]
        explanation=getattr(controller,'last_explanation',{})
        rule=rules.apply(installed,cycle,origin,explanation.get('provider_suggestion'),explanation)
        if cycle==len(trace)-1 and bounded:controller.llm.close()
        elapsed=1000*(time.perf_counter()-start)
        row=dict(provider=provider,mode=mode,seed=seed,cycle=cycle,phase=demand['phase'],origin=origin,provider_error=error,
            latency_ms=outcome.latency_ms,throughput_kbps=outcome.throughput_kbps,loss_pct=outcome.loss_pct,reward=reward,control_elapsed_ms=elapsed,deadline_miss=elapsed>5000,
            action=installed.action,rate_limit_kbps=installed.rate_limit_kbps,safety_allowed=guard.allowed,observation_wait_ms=observation_wait*1000,
            api_calls=sum(a.get('request_started',True) for a in audit),api_successes=sum(a['status']=='ok' for a in audit),
            local_timeouts=sum(a['status'] in ('deadline_timeout','startup_timeout') for a in audit),deferred=sum(a['status']=='deferred' for a in audit),
            pacing_ms=sum(a.get('pacing_ms',0) for a in audit),retrieved_cycles=json.dumps(used),offered_mbit=outcome.offered_mbit,delivered_mbit=outcome.delivered_mbit,
            dropped_mbit=outcome.dropped_mbit,meter_dropped_mbit=outcome.meter_dropped_mbit,queue_before_primary_mbit=previous[0],queue_before_alternate_mbit=previous[1],
            queue_primary_mbit=outcome.queue_mbit[0],queue_alternate_mbit=outcome.queue_mbit[1],provenance='simulation')
        rows.append(row);details.append({'metrics':row,'demand':demand,'state':state,'decision':d.model_dump(),'safety':guard.__dict__,
            'outcome':outcome.__dict__,'no_op_outcome':before.__dict__,'reflection':reflection,'provider_calls':audit,'rule_event':rule})
        print(f'{provider} {mode} seed={seed} cycle={cycle} {origin} {elapsed/1000:.3f}s loss={outcome.loss_pct:.3f}%',flush=True)
    memory.flush();return rows,details,rules.finish(len(trace))

def run(folder,provider,seeds=(1920,1921),cycles=12,stress=False,realtime=False):
    folder=local_path(folder);folder.mkdir(parents=True,exist_ok=True);rows=[];details=[];hashes={};ends=[];start=time.perf_counter()
    modes={'bounded':MODES['bounded']} if stress else MODES
    for i,seed in enumerate(seeds):
        trace=scenario_trace('recurring',seed,cycles);data=json.dumps(trace,sort_keys=True).encode();hashes[str(seed)]=hashlib.sha256(data).hexdigest();(folder/f'traffic_{seed}.json').write_bytes(data)
        for mode in (list(modes) if i%2==0 else list(reversed(modes))):
            r,d,end=execute(mode,trace,seed,folder,provider,hybrid=not stress,realtime=realtime);rows.extend(r);details.extend(d);ends.append({'seed':seed,'mode':mode,**end})
            (folder/'progress.json').write_text(json.dumps({'provider':provider,'last':[seed,mode],'windows':len(rows)}),encoding='utf-8')
    groups={}
    for mode,label in modes.items():
        r=[r for r in rows if r['mode']==mode]
        groups[mode]={'label':label,'windows':len(r),'origins':dict(Counter(x['origin'] for x in r)),
            **{k:mean(x[k] for x in r) for k in ('control_elapsed_ms','latency_ms','throughput_kbps','loss_pct','reward','pacing_ms')},
            'p95_control_ms':float(np.quantile([x['control_elapsed_ms'] for x in r],.95)),'max_control_ms':max(x['control_elapsed_ms'] for x in r),
            **{k:sum(x[k] for x in r) for k in ('api_calls','api_successes','deadline_miss','local_timeouts','deferred')},
            'per_seed':{str(seed):{k:mean(x[k] for x in r if x['seed']==seed) for k in ('control_elapsed_ms','latency_ms','loss_pct','reward')} for seed in seeds}}
    with (folder/'metrics.csv').open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (folder/'trace.jsonl').write_text('\n'.join(json.dumps(d) for d in details)+'\n',encoding='utf-8')
    (folder/'rule_expiry.json').write_text(json.dumps(ends,indent=2),encoding='utf-8')
    summary={'schema':'selfx.latency.v4','created_at_utc':datetime.now(timezone.utc).isoformat(),'provider':provider,'seeds':list(seeds),'cycles':cycles,'window_count':len(rows),'trace_sha256':hashes,
        'groups':groups,'deadline_ms':5000,'provider_wait_budget_ms':3800,'wall_seconds':time.perf_counter()-start,'isolated_virtual_environment':sys.prefix!=sys.base_prefix,'runtime':sys.executable,
        'stress':stress,'realtime_observations':realtime,'observation_schedule':'Five wall-clock seconds between observations; idle wait is reported separately from control work' if realtime else 'Accelerated replay; requests may be deferred by admission pacing','limits':['Actual authenticated provider requests; network outcomes are fluid simulation','Timeouts and deferrals are retained; zero control misses does not mean every API answered',
        'All process startup, pacing, cancellation and cleanup counted in full-cycle time','Client cancellation cannot undo generation already received by a cloud server','Small two-seed pilot; reversed mode order, time-varying service remains a confound','Rules installed only in a simulated rule table, never physical switches']}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(groups,indent=2));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--provider',choices=['gemini','openrouter'],default='gemini');p.add_argument('--cycles',type=int,default=12);p.add_argument('--seeds',type=int,nargs='+',default=[1920,1921]);p.add_argument('--out-dir');p.add_argument('--stress',action='store_true');p.add_argument('--realtime',action='store_true');a=p.parse_args()
    if not 1<=a.cycles<=120 or len(set(a.seeds))!=len(a.seeds):p.error('Bounded cycles and unique seeds required')
    run(a.out_dir or config.PROJECT_ROOT/f'output/benchmarks/v4/latency_{a.provider}',a.provider,a.seeds,a.cycles,a.stress,a.realtime)
