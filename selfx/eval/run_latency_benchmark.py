"""Paired live provider/control timing on generated recurring traffic."""
import argparse,csv,hashlib,json,time,sys
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from statistics import mean
import numpy as np
import config
from agent.adaptive_memory import AdaptiveMemory
from agent.fast_control import FastController
from agent.providers import RestLLM,ProviderError
from agent.schemas import DecisionOutput,ReflectionOutput
from agent import prompts
from agent.reward import compute_reward
from eval.run_adaptive_benchmarks import scenario_trace
from eval.run_simulation import local_path
from eval.simulator import FluidNetwork,decision_for

MODES={'legacy':'Two serial calls with full prompts','compact':'One compact call and local reflection','hybrid':'Compact call with validated local reuse'}

def execute(mode,trace,seed,folder,provider):
    net=FluidNetwork();memory=AdaptiveMemory(str(folder/f'{provider}_{mode}_{seed}_memory.json'),autosave=False);memory.clear()
    fast=FastController(provider,hybrid=mode=='hybrid');llm=RestLLM(provider) if mode=='legacy' else fast.llm
    rows=[];details=[]
    for cycle,demand in enumerate(trace):
        started=time.perf_counter();previous=list(net.queue);state=net.summary(demand);audit_start=len(llm.audit);error='';retrieved=[]
        if mode=='legacy':
            examples=memory.few_shot_examples(k=4,query=state);retrieved=[r['cycle'] for r in examples]
            try:
                decision=llm.with_structured_output(DecisionOutput).invoke(prompts.build_decide_messages(state,examples))
                if not decision.is_well_formed():raise ProviderError('malformed_decision')
                origin='api'
            except Exception as exc:
                origin='fallback_no_op';error=str(exc) if isinstance(exc,ProviderError) else type(exc).__name__
                decision=decision_for('no_op',demand,'Explicit legacy API fallback')
        else:decision,origin,retrieved,error=fast.decide(net,state,demand,memory,cycle)
        decision_ms=1000*(time.perf_counter()-started)
        guard=net.validate(demand,decision);installed=decision if guard.allowed else decision_for('no_op',demand,'Safety veto')
        before=net.evaluate(demand,decision_for('no_op',demand,'same-window counterfactual'))
        outcome=net.evaluate(demand,installed,commit=True);reward=compute_reward(before.metrics(),outcome.metrics()).reward
        reflection=f'Measured reward {reward:.6f}; modeled delay {outcome.latency_ms:.4f} ms; total loss {outcome.loss_pct:.4f}%.'
        if mode=='legacy' and origin=='api':
            try:reflection=llm.with_structured_output(ReflectionOutput).invoke(prompts.build_reflect_messages(state,installed.action,decision.model_dump(),outcome.metrics().__dict__,reward)).reflection
            except Exception:pass
        memory.add_record(cycle,state,installed.action,installed.model_dump(),reward,reflection)
        audit=llm.audit[audit_start:];elapsed=1000*(time.perf_counter()-started)
        row={'provider':provider,'mode':mode,'seed':seed,'cycle':cycle,'phase':demand['phase'],'origin':origin,'provider_error':error,
            'latency_ms':outcome.latency_ms,'throughput_kbps':outcome.throughput_kbps,'loss_pct':outcome.loss_pct,'reward':reward,
            'decision_ms':decision_ms,'control_elapsed_ms':elapsed,'deadline_miss':elapsed>5000,'action':installed.action,'safety_allowed':guard.allowed,
            'api_calls':len(audit),'api_successes':sum(r['status']=='ok' for r in audit),'pacing_ms':sum(r.get('pacing_ms',0) for r in audit),
            'transport_ms':sum(r.get('transport_ms',0) for r in audit),'prompt_chars':sum(r.get('prompt_chars',0) for r in audit),
            'retrieved_cycles':json.dumps(retrieved),'offered_mbit':outcome.offered_mbit,'delivered_mbit':outcome.delivered_mbit,'dropped_mbit':outcome.dropped_mbit,
            'queue_before_primary_mbit':previous[0],'queue_before_alternate_mbit':previous[1],
            'queue_primary_mbit':outcome.queue_mbit[0],'queue_alternate_mbit':outcome.queue_mbit[1],'provenance':'simulation'}
        rows.append(row);details.append({'metrics':row,'state':state,'demand':demand,'decision':decision.model_dump(),'outcome':outcome.__dict__,'reflection':reflection,'provider_calls':audit})
        print(f'{provider} {mode} seed={seed} cycle={cycle} {origin} {elapsed/1000:.3f}s',flush=True)
    memory.flush();return rows,details,llm.audit

def run(folder,provider,seeds,cycles):
    folder=local_path(folder);folder.mkdir(parents=True,exist_ok=True);rows=[];details=[];audits=[];hashes={};started=time.perf_counter()
    for i,seed in enumerate(seeds):
        trace=scenario_trace('recurring',seed,cycles);data=json.dumps(trace,sort_keys=True).encode();hashes[str(seed)]=hashlib.sha256(data).hexdigest();(folder/f'traffic_{seed}.json').write_bytes(data)
        order=list(MODES) if i%2==0 else list(reversed(MODES))
        for mode in order:
            r,d,a=execute(mode,trace,seed,folder,provider);rows.extend(r);details.extend(d);audits.extend(a)
            (folder/'progress.json').write_text(json.dumps({'provider':provider,'last_completed':[seed,mode],'windows':len(rows)}),encoding='utf-8')
            (folder/f'{mode}_{seed}_trace.json').write_text(json.dumps(d),encoding='utf-8')
    groups={}
    for mode,label in MODES.items():
        selected=[r for r in rows if r['mode']==mode]
        groups[mode]={'label':label,'windows':len(selected),'origins':dict(Counter(r['origin'] for r in selected)),
            **{k:mean(r[k] for r in selected) for k in ('latency_ms','throughput_kbps','loss_pct','reward','decision_ms','control_elapsed_ms','pacing_ms','transport_ms','prompt_chars')},
            'p95_control_ms':float(np.quantile([r['control_elapsed_ms'] for r in selected],.95)),
            'deadline_misses':sum(r['deadline_miss'] for r in selected),'api_calls':sum(r['api_calls'] for r in selected),'api_successes':sum(r['api_successes'] for r in selected),
            'per_seed':{str(seed):{k:mean(r[k] for r in selected if r['seed']==seed) for k in ('control_elapsed_ms','decision_ms','latency_ms','loss_pct','reward')} for seed in seeds}}
    with (folder/'metrics.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (folder/'trace.jsonl').write_text('\n'.join(json.dumps(d,allow_nan=False) for d in details)+'\n',encoding='utf-8')
    (folder/'provider_calls.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    summary={'schema':'selfx.latency.v3','created_at_utc':datetime.now(timezone.utc).isoformat(),'provider':provider,'requested_model':config.GEMINI_MODEL if provider=='gemini' else config.OPENROUTER_MODEL,
        'provenance':'simulation','seeds':seeds,'cycles':cycles,'window_count':len(rows),'trace_sha256':hashes,'groups':groups,'wall_seconds':time.perf_counter()-started,
        'isolated_virtual_environment':sys.prefix!=sys.base_prefix,'runtime':sys.executable,'deadline_ms':5000,
        'limits':['Small two-seed recurring synthetic-workload pilot','Different call counts and local reuse are explicit system changes, not proof of faster provider servers',
            'Transport time includes HTTP/network/service time; pacing is recorded separately','Full control time includes reflection; no work is silently moved outside the measured interval',
            'Seed order reverses mode order to reduce time-order bias; provider variation remains','Failures and local cache/bypass/memory origins remain in all metrics']}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(groups,indent=2));return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provider',choices=['gemini','openrouter'],default='gemini');p.add_argument('--seeds',type=int,nargs='+',default=[1790,1791]);p.add_argument('--cycles',type=int,default=12);p.add_argument('--out-dir')
    a=p.parse_args()
    if not 1<=a.cycles<=120 or len(set(a.seeds))!=len(a.seeds):p.error('Use bounded cycles and unique seeds')
    run(a.out_dir or config.PROJECT_ROOT/f'output/benchmarks/v3/latency_{a.provider}',a.provider,a.seeds,a.cycles)
