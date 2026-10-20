"""Held-out v3 evaluation; the v2 measurements are preserved unchanged."""
import argparse,csv,hashlib,json,platform,random,sys,time
from datetime import datetime,timezone
from pathlib import Path
from eval.run_benchmarks import SCENARIOS as OLD_SCENARIOS,CONTROLLERS as OLD_CONTROLLERS,scenario_trace as original_trace,execute,aggregate
from eval.run_simulation import local_path
import config

SCENARIOS={**OLD_SCENARIOS,'recurring':'Recurring traffic contexts','volatile':'Unpredictable traffic changes'}
CONTROLLERS={**OLD_CONTROLLERS,'A4':'Action-conditioned adaptive memory'}

def scenario_trace(name,seed,cycles):
    if name in OLD_SCENARIOS:return original_trace(name,seed,cycles)
    rng=random.Random(seed);rows=original_trace('mixed',seed,cycles)
    archetypes=[(2,2,1),(5,1,7),(6,6,6),(4,1,3),(4,7,7),(7,7,9)]
    contexts=[tuple(round(v+rng.uniform(-.15,.15),4) for v in t) for t in archetypes]
    for i,row in enumerate(rows):
        rates=contexts[i%len(contexts)] if name=='recurring' else (rng.uniform(1,8.5),rng.uniform(.5,8.5),rng.uniform(1,10))
        row.update(zip(('primary_background_mbps','alternate_background_mbps','elephant_mbps'),[round(v,4) for v in rates]))
        row['phase']='recurring_'+str(i%len(contexts)) if name=='recurring' else 'volatile'
    return rows

def run(folder,cycles,seeds,scenarios):
    folder=local_path(folder);folder.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();rows=[];hashes={}
    for scenario in scenarios:
        for seed in seeds:
            trace=scenario_trace(scenario,seed,cycles);data=json.dumps(trace,sort_keys=True).encode()
            hashes[f'{scenario}_{seed}']=hashlib.sha256(data).hexdigest();(folder/f'traffic_{scenario}_{seed}.json').write_bytes(data)
            for condition in CONTROLLERS:rows.extend(execute(condition,trace,scenario,seed,folder))
        print(f'Completed {scenario}: {len(seeds)*cycles*len(CONTROLLERS)} windows',flush=True)
    with (folder/'metrics.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    groups,paired=aggregate(rows,seeds,scenarios,CONTROLLERS)
    summary={'schema':'selfx.benchmark.v3','created_at_utc':datetime.now(timezone.utc).isoformat(),'provenance':'simulation','backend':'offline',
        'seeds':seeds,'development_seeds':[1740,1741],'holdout':'Algorithm frozen before evaluation on seeds 1760..1769; no tuning on held-out outcomes',
        'scenarios':{sc:SCENARIOS[sc] for sc in scenarios},'controllers':CONTROLLERS,'cycles':cycles,'interval_seconds':5,
        'window_count':len(rows),'wall_seconds':time.perf_counter()-start,'traffic_sha256':hashes,'groups':groups,'paired_comparisons':paired,
        'environment':{'python':platform.python_version(),'virtual_environment':str(Path(sys.prefix).resolve()),'isolated':sys.prefix!=sys.base_prefix},
        'statistics':'4000-draw paired seed percentile bootstrap; RNG 4099; exploratory, no multiplicity correction',
        'limits':['Synthetic finite-buffer two-path fluid traffic; no physical packets','Only prior completed episodes train A4; no candidate outcome evaluation',
            'A4 retains up to 96 magnitude-preserving action-specific episodes; A3 retains 30','The guard-only H1 is the no-memory ablation',
            'O1 has privileged same-window simulator access; not a deployable or long-horizon upper bound','P95 is over mean-window delay, not individual packets',
            'Local computation timings exclude final memory flush; network results alone do not benchmark LLM quality']}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'windows':len(rows),'wall_seconds':summary['wall_seconds']}),flush=True);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out-dir',default=str(config.PROJECT_ROOT/'output/benchmarks/v3'))
    p.add_argument('--cycles',type=int,default=120);p.add_argument('--seeds',nargs='+',type=int,default=list(range(1760,1770)))
    p.add_argument('--scenarios',nargs='+',choices=list(SCENARIOS),default=list(SCENARIOS));a=p.parse_args()
    if not 1<=a.cycles<=1000 or len(a.seeds)!=len(set(a.seeds)) or len(a.scenarios)!=len(set(a.scenarios)):p.error('Use bounded cycles and unique seeds/scenarios')
    run(a.out_dir,a.cycles,a.seeds,a.scenarios)
