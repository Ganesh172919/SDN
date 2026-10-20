"""Post-hoc mechanism diagnostic, kept separate from the primary held-out suite."""
import csv,hashlib,json,random,time
from pathlib import Path
from eval.run_benchmarks import execute,aggregate,CONTROLLERS as BASE
from eval.run_adaptive_benchmarks import scenario_trace
import config

LEVELS={'excess_0001':.0001,'excess_0005':.0005,'excess_005':.005,'excess_05':.05}
CONTROLLERS={c:('Action-conditioned adaptive memory' if c=='A4' else BASE[c]) for c in ('H1','A3','A4','O1')}

def run():
    folder=config.PROJECT_ROOT/'output/benchmarks/v3/memory_sensitivity';folder.mkdir(parents=True,exist_ok=True)
    rows=[];hashes={};started=time.perf_counter();seeds=list(range(1780,1790))
    for name,excess in LEVELS.items():
        for seed in seeds:
            rng=random.Random(seed);p=round(rng.uniform(3.8,4.2),4);e=10-p+excess;a=round(rng.uniform(7.5,8.5),4)
            trace=scenario_trace('recurring',seed,120)
            for demand in trace:demand.update(primary_background_mbps=p,alternate_background_mbps=a,elephant_mbps=e,phase=name)
            data=json.dumps(trace,sort_keys=True).encode();hashes[f'{name}_{seed}']=hashlib.sha256(data).hexdigest();(folder/f'traffic_{name}_{seed}.json').write_bytes(data)
            for c in CONTROLLERS:rows.extend(execute(c,trace,name,seed,folder))
    with (folder/'metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    # Reuse the same paired seed statistics, with available comparisons only.
    groups={};paired={}
    from eval.run_benchmarks import seed_metrics,bootstrap_interval,METRICS
    from statistics import mean
    for name in LEVELS:
        groups[name]={};paired[name]={}
        for c in CONTROLLERS:
            selected=[r for r in rows if r['scenario']==name and r['condition']==c]
            per={str(seed):seed_metrics([r for r in selected if r['seed']==seed]) for seed in seeds}
            groups[name][c]={'metrics':{k:{'mean':mean(v[k] for v in per.values()),'ci95':bootstrap_interval([v[k] for v in per.values()])} for k in METRICS},'seed_metrics':per}
        for c in ('H1','A3'):
            paired[name]['A4_minus_'+c]={}
            for metric in METRICS:
                values=[groups[name]['A4']['seed_metrics'][str(s)][metric]-groups[name][c]['seed_metrics'][str(s)][metric] for s in seeds]
                paired[name]['A4_minus_'+c][metric]={'mean_difference':mean(values),'ci95':bootstrap_interval(values)}
    result={'schema':'selfx.memory.sensitivity.v3','design':'Post-hoc constructed mechanism stress test; excluded from the primary eight-scenario average',
        'hypothesis':'A tiny overload can make a fixed 20% meter cost more goodput than its delay benefit; action-local negative episodes should reject it',
        'levels_mbps':LEVELS,'controllers':CONTROLLERS,'cycles':120,'seeds':seeds,'window_count':len(rows),'traffic_sha256':hashes,
        'groups':groups,'paired_comparisons':paired,'wall_seconds':time.perf_counter()-started,'provenance':'simulation'}
    (folder/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for level,g in groups.items():print(level,{c:{m:round(g[c]['metrics'][m]['mean'],6) for m in ('latency_ms','loss_pct','reward')} for c in CONTROLLERS},flush=True)
    return result

if __name__=='__main__':run()
