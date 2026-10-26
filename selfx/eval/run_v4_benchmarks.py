"""Fresh paired evaluation with a matched meter-parameter ablation."""
import argparse,csv,hashlib,json,sys,time
from collections import Counter
from datetime import datetime,timezone
from statistics import mean
import numpy as np
import config
from agent.loss_aware_memory import LossAwareMemory,loss_aware_policy,capacity_policy,meter_decision,HEADROOMS
from agent.reward import compute_reward
from eval.run_adaptive_benchmarks import SCENARIOS,scenario_trace
from eval.run_benchmarks import execute as old_execute,seed_metrics,bootstrap_interval,METRICS
from eval.run_simulation import local_path
from eval.simulator import FluidNetwork,decision_for

CONTROLLERS={'A0':'Static primary','B1':'Least loaded','A2':'Original embedding','H1':'Guarded fixed 20% meter','A3':'Guarded balanced memory','V3':'Previous A4 (v3)',
    'H2':'Capacity-aware meter, no memory','A4':'Loss-aware parameter memory','O2':'Privileged matched-action reference'}


def execute(condition,trace,scenario,seed,folder):
    if condition not in {'H2','A4','O2'}:
        rows=old_execute('A4' if condition=='V3' else condition,trace,scenario,seed,folder)
        for r in rows:r.update(condition=condition,rate_limit_kbps=None,parameter_mode='fixed_v3',parameter_support=0)
        return rows
    net=FluidNetwork();memory=LossAwareMemory(str(folder/f'{scenario}_{condition}_{seed}_memory.json'),enabled=condition=='A4',autosave=False);memory.clear();rows=[]
    for cycle,demand in enumerate(trace):
        started=time.perf_counter();previous=list(net.queue);state=net.summary(demand);used=[]
        decision=capacity_policy(state,demand)
        if condition=='A4':decision,used=loss_aware_policy(net,state,demand,memory,cycle)
        if condition=='O2':
            candidates=[decision_for(a,demand,'Privileged matched-action reference') for a in ('no_op','reroute')]+[meter_decision(state,demand,h,'Privileged meter reference') for h in HEADROOMS]
            before=net.evaluate(demand,decision_for('no_op',demand,'baseline'))
            decision=max((d for d in candidates if net.validate(demand,d).allowed),key=lambda d:compute_reward(before.metrics(),net.evaluate(demand,d).metrics()).reward)
        guard=net.validate(demand,decision);installed=decision if guard.allowed else decision_for('no_op',demand,'Safety veto')
        before=net.evaluate(demand,decision_for('no_op',demand,'Same-window no-op measurement'))
        after=net.evaluate(demand,installed,commit=True);reward=compute_reward(before.metrics(),after.metrics()).reward
        memory.add_record(cycle,state,installed.action,installed.model_dump(),reward,f'Measured reward {reward:.6f}; loss {after.loss_pct:.6f}%')
        rows.append(dict(scenario=scenario,condition=condition,seed=seed,cycle=cycle,phase=demand['phase'],flow_id=demand['flow_id'],
            latency_ms=after.latency_ms,throughput_kbps=after.throughput_kbps,loss_pct=after.loss_pct,reward=round(reward,8),requested_action=decision.action,
            installed_action=installed.action,safety_allowed=guard.allowed,safety_reason=guard.reason,rationale=decision.rationale,memory_examples=len(used),retrieved_cycles=json.dumps(used),
            primary_background_mbps=demand['primary_background_mbps'],alternate_background_mbps=demand['alternate_background_mbps'],elephant_mbps=demand['elephant_mbps'],
            queue_before_primary_mbit=previous[0],queue_before_alternate_mbit=previous[1],queue_primary_mbit=after.queue_mbit[0],queue_alternate_mbit=after.queue_mbit[1],
            offered_mbit=after.offered_mbit,delivered_mbit=after.delivered_mbit,dropped_mbit=after.dropped_mbit,meter_dropped_mbit=after.meter_dropped_mbit,
            control_elapsed_ms=1000*(time.perf_counter()-started),provenance='simulation',decision_backend='offline',rate_limit_kbps=installed.rate_limit_kbps,
            parameter_mode='memory' if condition=='A4' else 'matched_no_memory' if condition=='H2' else 'privileged',parameter_support=len(used)))
    memory.flush();return rows


def summarize(rows,seeds,scenarios):
    groups={};paired={}
    for sc in scenarios:
        groups[sc]={};paired[sc]={}
        for c,label in CONTROLLERS.items():
            selected=[r for r in rows if r['scenario']==sc and r['condition']==c]
            per_seed={str(seed):seed_metrics([r for r in selected if r['seed']==seed]) for seed in seeds}
            groups[sc][c]={'label':label,'windows':len(selected),'seed_metrics':per_seed,'metrics':{k:{'mean':mean(v[k] for v in per_seed.values()),'ci95':bootstrap_interval([v[k] for v in per_seed.values()])} for k in METRICS},
                'actions':dict(Counter(r['installed_action'] for r in selected)),'vetoes':sum(not r['safety_allowed'] for r in selected)}
        for baseline in ('H1','H2','V3','A2','O2'):
            paired[sc]['A4_minus_'+baseline]={}
            for k in METRICS:
                delta=[groups[sc]['A4']['seed_metrics'][str(seed)][k]-groups[sc][baseline]['seed_metrics'][str(seed)][k] for seed in seeds]
                paired[sc]['A4_minus_'+baseline][k]={'mean_difference':mean(delta),'ci95':bootstrap_interval(delta)}
    return groups,paired


def run(folder,cycles=120,seeds=tuple(range(1900,1910)),scenarios=tuple(SCENARIOS)):
    folder=local_path(folder);folder.mkdir(parents=True,exist_ok=True);rows=[];hashes={};started=time.perf_counter()
    for sc in scenarios:
        for seed in seeds:
            trace=scenario_trace(sc,seed,cycles);data=json.dumps(trace,sort_keys=True).encode();hashes[f'{sc}_{seed}']=hashlib.sha256(data).hexdigest();(folder/f'traffic_{sc}_{seed}.json').write_bytes(data)
            for c in CONTROLLERS:rows.extend(execute(c,trace,sc,seed,folder))
        print('Completed '+sc,flush=True)
    with (folder/'metrics.csv').open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    groups,paired=summarize(rows,seeds,scenarios)
    summary=dict(schema='selfx.benchmark.v4',created_at_utc=datetime.now(timezone.utc).isoformat(),seeds=list(seeds),cycles=cycles,scenarios={sc:SCENARIOS[sc] for sc in scenarios},controllers=CONTROLLERS,
        window_count=len(rows),wall_seconds=time.perf_counter()-started,traffic_sha256=hashes,groups=groups,paired_comparisons=paired,provenance='simulation',backend='offline',
        environment={'isolated':sys.prefix!=sys.base_prefix,'virtual_environment':sys.prefix},
        protocol={'frozen_before_primary':True,'development_seeds':[1880,1881],'headrooms_mbps':list(HEADROOMS),'support':3,'memory_limit':128,
            'implementation_repair':'A post-run audit found binary rounding at the exact 20% meter floor. Meter construction admits one extra kbps when needed by the unchanged strict guard. Pre-repair CSV/summary are preserved in pre_numeric_repair; no outcome-driven parameter tuning.',
            'statistics':'4000-draw paired seed percentile bootstrap, RNG 4099; exploratory, no multiplicity adjustment',
            'ablation':'H2 has identical capacity-aware meter candidates; fixed 0.1 Mbps headroom, no memory. A4 explores then selects headroom using prior observed reward.',
            'limits':['Fluid simulation, not packet capture or real OpenFlow deployment','Network benchmarks use local policies, not LLM calls','H1 improvements can come from new meter logic; H2 isolates the extra memory effect','O2 is a privileged immediate-reward reference, not a deployable or long-horizon bound','Final memory flush excluded from per-window local timings']} )
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps({'windows':len(rows),'wall_seconds':summary['wall_seconds']}));return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out-dir',default=str(config.PROJECT_ROOT/'output/benchmarks/v4'));p.add_argument('--seeds',type=int,nargs='+',default=list(range(1900,1910)));p.add_argument('--cycles',type=int,default=120);p.add_argument('--scenarios',nargs='+',choices=list(SCENARIOS),default=list(SCENARIOS));a=p.parse_args()
    if not 1<=a.cycles<=1000 or len(set(a.seeds))!=len(a.seeds):p.error('Use bounded cycles and unique seeds')
    run(a.out_dir,a.cycles,a.seeds,a.scenarios)
