"""Multi-scenario, paired-seed benchmark. Network values are analytical simulation."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import platform
import random
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import numpy as np
import config
from agent.memory import MemoryStore
from agent.guarded_memory import BalancedMemory, guarded_base, guarded_policy
from agent.adaptive_memory import AdaptiveMemory, adaptive_policy
from agent.reward import compute_reward
from eval.run_simulation import local_path
from eval.simulator import FluidNetwork, traffic_trace, decision_for, reactive_policy, least_loaded

SCENARIOS = {"mixed":"Repeated mixed load", "flash":"Primary flash crowd", "alternate":"Busy alternate path",
             "shift":"Traffic distribution shift", "overload":"Persistent dual overload", "light":"Light-load control"}
CONTROLLERS = {"A0":"Static primary", "B1":"Least loaded", "B2":"Guarded ECMP-style hash", "A1":"Original no memory",
               "A2":"Original embedding memory", "H1":"Guarded no memory", "A3":"Guarded balanced memory", "O1":"Myopic model reference"}
ORDER = list(CONTROLLERS)
METRICS = ["latency_ms","throughput_kbps","loss_pct","reward","window_latency_p95_ms","safety_veto_pct","control_elapsed_ms"]


def scenario_trace(name,seed,cycles):
    if name not in SCENARIOS or cycles < 1:
        raise ValueError("invalid scenario or window count")
    rng=random.Random(seed)
    trace=traffic_trace(seed,cycles)
    for i,row in enumerate(trace):
        if name=="mixed":pass
        elif name=="flash":
            burst=(i//6)%2==1
            row.update(primary_background_mbps=rng.uniform(3.5,5.8),alternate_background_mbps=rng.uniform(.5,2.0),elephant_mbps=rng.uniform(5,8) if burst else rng.uniform(1,2.5),phase="flash" if burst else "recovery")
        elif name=="alternate":
            row.update(primary_background_mbps=rng.uniform(4,6),alternate_background_mbps=rng.uniform(7,9),elephant_mbps=rng.uniform(3,7),phase="alternate_busy")
        elif name=="shift":
            shifted=i>=cycles//2
            row.update(primary_background_mbps=rng.uniform(3,5),alternate_background_mbps=rng.uniform(6.5,8.5) if shifted else rng.uniform(.5,2),elephant_mbps=rng.uniform(5,7),phase="after_shift" if shifted else "before_shift")
        elif name=="overload":
            row.update(primary_background_mbps=rng.uniform(7,9),alternate_background_mbps=rng.uniform(7,9),elephant_mbps=rng.uniform(7,11),phase="both_overloaded")
        elif name=="light":
            row.update(primary_background_mbps=rng.uniform(1,3),alternate_background_mbps=rng.uniform(1,3),elephant_mbps=rng.uniform(.5,2),phase="light")
        for key in ("primary_background_mbps","alternate_background_mbps","elephant_mbps"):
            row[key]=round(row[key],4)
        row["flow_id"]=f"flow-{seed}-{i}"
    return trace


def ec_candidates(demand):
    return [decision_for(a,demand,"Myopic model reference candidate") for a in ("no_op","reroute","rate_limit")]


def select(condition,net,summary,demand,memory):
    examples=[]
    if condition=="A0":return decision_for("no_op",demand,"Static primary"),examples
    if condition=="B1":return least_loaded(summary),examples
    if condition=="B2":
        alternate=int(hashlib.sha256(demand["flow_id"].encode()).hexdigest()[:8],16) >= 2**31
        return decision_for("reroute" if alternate else "no_op",demand,"Stable flow hash over equal key-space regions; common safety gate applies"),examples
    if condition in ("A1","A2"):
        examples=memory.few_shot_examples(k=4,query=summary)
        return reactive_policy(summary,examples,condition=="A2"),[r["cycle"] for r in examples]
    if condition=="H1":return guarded_base(summary,demand),examples
    if condition=="A3":return guarded_policy(net,summary,demand,memory)
    if condition=="A4":return adaptive_policy(net,summary,demand,memory,demand['cycle'])
    if condition=="O1":
        before=net.evaluate(demand,decision_for("no_op",demand,"reference counterfactual"))
        candidates=[c for c in ec_candidates(demand) if net.validate(demand,c).allowed]
        return max(candidates,key=lambda c:compute_reward(before.metrics(),net.evaluate(demand,c).metrics()).reward),examples
    raise ValueError("unknown controller")


def execute(condition,trace,scenario,seed,folder):
    net=FluidNetwork()
    cls=AdaptiveMemory if condition=='A4' else BalancedMemory if condition=="A3" else MemoryStore
    memory=cls(str(folder/f"{scenario}_{condition}_{seed}_memory.json"),enabled=condition in {"A2","A3","A4"},autosave=False)
    memory.clear()
    rows=[]
    for cycle,demand in enumerate(trace):
        start=time.perf_counter()
        previous_queue=list(net.queue)
        summary=net.summary(demand)
        decision,retrieved=select(condition,net,summary,demand,memory)
        guard=net.validate(demand,decision)
        installed=decision if guard.allowed else decision_for("no_op",demand,"Safety veto: "+guard.reason)
        before=net.evaluate(demand,decision_for("no_op",demand,"same-window baseline"))
        outcome=net.evaluate(demand,installed,commit=True)
        reward=compute_reward(before.metrics(),outcome.metrics()).reward
        memory.add_record(cycle,summary,installed.action,installed.model_dump(),reward,f"Measured reward {reward:.6f}; total loss {outcome.loss_pct:.4f}%.")
        elapsed=1000*(time.perf_counter()-start)
        rows.append({"scenario":scenario,"condition":condition,"seed":seed,"cycle":cycle,"phase":demand["phase"],
            "flow_id":demand["flow_id"],"latency_ms":outcome.latency_ms,"throughput_kbps":outcome.throughput_kbps,
            "loss_pct":outcome.loss_pct,"reward":round(reward,8),"requested_action":decision.action,"installed_action":installed.action,
            "safety_allowed":guard.allowed,"safety_reason":guard.reason,"rationale":decision.rationale,"memory_examples":len(retrieved),
            "retrieved_cycles":json.dumps(retrieved),"primary_background_mbps":demand["primary_background_mbps"],
            "alternate_background_mbps":demand["alternate_background_mbps"],"elephant_mbps":demand["elephant_mbps"],
            "queue_before_primary_mbit":previous_queue[0],"queue_before_alternate_mbit":previous_queue[1],
            "queue_primary_mbit":outcome.queue_mbit[0],"queue_alternate_mbit":outcome.queue_mbit[1],
            "offered_mbit":outcome.offered_mbit,"delivered_mbit":outcome.delivered_mbit,"dropped_mbit":outcome.dropped_mbit,
            "meter_dropped_mbit":outcome.meter_dropped_mbit,"control_elapsed_ms":round(elapsed,6),"provenance":"simulation","decision_backend":"offline"})
    memory.flush()
    return rows


def seed_metrics(rows):
    return {**{k:mean(r[k] for r in rows) for k in ("latency_ms","throughput_kbps","loss_pct","reward","control_elapsed_ms")},
            "window_latency_p95_ms":float(np.quantile([r["latency_ms"] for r in rows],.95)),
            "safety_veto_pct":100*sum(not r["safety_allowed"] for r in rows)/len(rows),
            "pooled_loss_pct":100*sum(r["dropped_mbit"] for r in rows)/sum(r["offered_mbit"] for r in rows)}


def bootstrap_interval(values,seed=4099):
    values=np.asarray(values,dtype=float)
    if len(values)<2:return None
    rng=np.random.default_rng(seed)
    samples=rng.choice(values,size=(4000,len(values)),replace=True).mean(axis=1)
    return [float(x) for x in np.quantile(samples,[.025,.975])]


def aggregate(rows,seeds,scenarios,controllers=None):
    controllers=controllers or CONTROLLERS
    groups={}
    for scenario in scenarios:
        groups[scenario]={}
        for condition in controllers:
            selected=[r for r in rows if r["scenario"]==scenario and r["condition"]==condition]
            per_seed={str(seed):seed_metrics([r for r in selected if r["seed"]==seed]) for seed in seeds}
            statistics={k:{"mean":mean(v[k] for v in per_seed.values()),"ci95":bootstrap_interval([v[k] for v in per_seed.values()])} for k in METRICS}
            groups[scenario][condition]={"label":controllers[condition],"windows":len(selected),"metrics":statistics,"seed_metrics":per_seed,
                "actions":dict(Counter(r["installed_action"] for r in selected)),"vetoes":sum(not r["safety_allowed"] for r in selected)}
    comparisons={}
    for scenario in scenarios:
        comparisons[scenario]={}
        pairs=[("A3","A2"),("A3","H1"),("H1","A1"),("A2","A1"),("A3","B1")]
        if 'A4' in controllers:pairs.extend([('A4',c) for c in ('A3','H1','A2','O1')])
        for candidate,baseline in pairs:
            comparisons[scenario][candidate+"_minus_"+baseline]={}
            for metric in METRICS:
                deltas=[groups[scenario][candidate]["seed_metrics"][str(seed)][metric]-groups[scenario][baseline]["seed_metrics"][str(seed)][metric] for seed in seeds]
                comparisons[scenario][candidate+"_minus_"+baseline][metric]={"mean_difference":mean(deltas),"ci95":bootstrap_interval(deltas)}
    return groups,comparisons


def run(folder,cycles,seeds,scenarios):
    folder=local_path(folder);folder.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();rows=[];hashes={}
    for scenario in scenarios:
        for seed in seeds:
            trace=scenario_trace(scenario,seed,cycles)
            content=json.dumps(trace,sort_keys=True).encode()
            hashes[f"{scenario}_{seed}"]=hashlib.sha256(content).hexdigest()
            (folder/f"traffic_{scenario}_{seed}.json").write_bytes(content)
            for condition in ORDER:rows.extend(execute(condition,trace,scenario,seed,folder))
        print(f"Completed {scenario}: {len(seeds)*cycles*len(ORDER)} windows",flush=True)
    with (folder/"metrics.csv").open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    groups,comparisons=aggregate(rows,seeds,scenarios)
    result={"schema":"selfx.benchmark.v2","created_at_utc":datetime.now(timezone.utc).isoformat(),"provenance":"simulation","backend":"offline",
        "seeds":seeds,"scenarios":{k:SCENARIOS[k] for k in scenarios},"controllers":CONTROLLERS,"cycles":cycles,"interval_seconds":5,
        "window_count":len(rows),"wall_seconds":time.perf_counter()-start,"traffic_sha256":hashes,"groups":groups,"paired_comparisons":comparisons,
        "environment":{"python":platform.python_version(),"virtual_environment":str(Path(__import__('sys').prefix).resolve())},
        "statistics":"4000-draw paired seed bootstrap; fixed RNG seed 4099; 95% percentile intervals; exploratory comparisons, no multiplicity correction",
        "limits":["No packet or physical-network measurements","A3 vs H1 isolates memory after common heuristic guards","O1 knows the simulator and optimizes only the immediate candidate reward; it is not a deployment policy or a long-horizon upper bound","P95 is over modeled mean-window delays, not packet delays","Offline suite is not evidence of live LLM improvement","Decision timing excludes final memory flush and is machine dependent"]}
    (folder/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({"windows":len(rows),"wall_seconds":result["wall_seconds"],"output":str(folder)}),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cycles',type=int,default=120);p.add_argument('--seeds',nargs='+',type=int,default=list(range(1740,1750)))
    p.add_argument('--scenarios',nargs='+',choices=list(SCENARIOS),default=list(SCENARIOS))
    p.add_argument('--out-dir',default=str(config.PROJECT_ROOT/'output/benchmarks/v2'))
    a=p.parse_args()
    if not 1<=a.cycles<=1000 or len(set(a.seeds))!=len(a.seeds) or len(set(a.scenarios))!=len(a.scenarios):p.error('use 1..1000 cycles and unique seeds/scenarios')
    run(a.out_dir,a.cycles,a.seeds,a.scenarios)


if __name__=='__main__':main()
