"""Recompute v4 evidence and package only verified, credential-free outputs."""
import csv,hashlib,json,math,re
from collections import Counter
from statistics import mean
from zipfile import ZipFile,ZIP_DEFLATED
from pypdf import PdfReader
from agent.schemas import DecisionOutput
from agent.reward import compute_reward
from eval.simulator import FluidNetwork,decision_for
from eval.run_v4_benchmarks import summarize
from scripts.verify_submission import ROOT,OUT,FINAL,source_files,verify_no_secrets,verify_evidence,verify_benchmark

B=OUT/'benchmarks/v4'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def close(a,b,tol=1e-7):assert math.isclose(float(a),float(b),abs_tol=tol,rel_tol=1e-9),(a,b)

def primary():
    s=read(B/'summary.json');rows=list(csv.DictReader((B/'metrics.csv').open(encoding='utf-8')));traces={}
    assert len(rows)==s['window_count']==86400
    for key,digest in s['traffic_sha256'].items():
        path=B/f'traffic_{key}.json';assert hashlib.sha256(path.read_bytes()).hexdigest()==digest;traces[key]=read(path)
    previous={};typed=[];net=FluidNetwork()
    for row in rows:
        r=dict(row)
        for k in ('seed','cycle','memory_examples','parameter_support'):r[k]=int(r[k])
        for k in ('latency_ms','throughput_kbps','loss_pct','reward','control_elapsed_ms','offered_mbit','delivered_mbit','dropped_mbit','meter_dropped_mbit'):r[k]=float(r[k])
        r['safety_allowed']=r['safety_allowed']=='True';typed.append(r)
        demand=traces[f"{r['scenario']}_{r['seed']}"][r['cycle']]
        assert demand['flow_id']==r['flow_id']
        for k in ('primary_background_mbps','alternate_background_mbps','elephant_mbps'):close(r[k],demand[k])
        assert all(n<r['cycle'] for n in json.loads(r['retrieved_cycles']))
        before_queue=[float(r['queue_before_primary_mbit']),float(r['queue_before_alternate_mbit'])]
        key=(r['scenario'],r['condition'],r['seed']);assert before_queue==previous.get(key,[0.,0.])
        net.queue=before_queue
        decision=decision_for(r['installed_action'],demand,'Replay validation')
        if row['rate_limit_kbps']:decision.rate_limit_kbps=int(row['rate_limit_kbps'])
        assert net.validate(demand,decision).allowed
        outcome=net.evaluate(demand,decision)
        for k in ('latency_ms','throughput_kbps','loss_pct','offered_mbit','delivered_mbit','dropped_mbit','meter_dropped_mbit'):close(r[k],getattr(outcome,k),1e-6)
        close(r['queue_primary_mbit'],outcome.queue_mbit[0]);close(r['queue_alternate_mbit'],outcome.queue_mbit[1])
        previous[key]=outcome.queue_mbit
        before=net.evaluate(demand,decision_for('no_op',demand,'baseline'))
        close(r['reward'],compute_reward(before.metrics(),outcome.metrics()).reward,1e-7)
        close(sum(before_queue)+outcome.offered_mbit,outcome.delivered_mbit+outcome.dropped_mbit+sum(outcome.queue_mbit),1e-6)
    groups,paired=summarize(typed,s['seeds'],s['scenarios'])
    for sc in groups:
        for c,g in groups[sc].items():
            expected=s['groups'][sc][c];assert g['actions']==expected['actions'] and g['vetoes']==expected['vetoes']
            for k,v in g['metrics'].items():
                close(v['mean'],expected['metrics'][k]['mean'])
                for a,b in zip(v['ci95'],expected['metrics'][k]['ci95']):close(a,b)
        for pair,metrics in paired[sc].items():
            for k,v in metrics.items():
                close(v['mean_difference'],s['paired_comparisons'][sc][pair][k]['mean_difference'])
                for a,b in zip(v['ci95'],s['paired_comparisons'][sc][pair][k]['ci95']):close(a,b)
    flows=list(csv.DictReader((B/'traffic/simulated_netflow.csv').open(encoding='utf-8')));assert len(flows)==9600
    for r in flows:
        assert r['provenance']=='synthetic_aggregate_not_packet_capture';assert int(r['end_virtual_ms'])-int(r['start_virtual_ms'])==5000
        demand=traces[f"{r['scenario']}_{r['seed']}"][int(r['start_virtual_ms'])//5000]
        assert r['flow_id']==demand['flow_id'] and int(r['elephant_bytes_offered'])==round(demand['elephant_mbps']*1e6*5/8)
    return {'windows_replayed':len(rows),'traffic_hashes':len(traces),'aggregate_records':len(flows),'paired_intervals_recomputed':True}

def rules_and_timing(folder,offline=False):
    details=[json.loads(l) for l in (folder/'trace.jsonl').read_text(encoding='utf-8').splitlines()];s=read(folder/'summary.json')
    previous={};origins=Counter();calls=[]
    for d in details:
        m=d['metrics'];e=d['rule_event'];key=(m['mode'],m['seed']);cycle=m['cycle'];origins[m['origin']]+=1
        assert all(n<cycle for n in json.loads(m['retrieved_cycles']))
        net=FluidNetwork();net.queue=d['state']['simulation']['queues_mbit'];decision=DecisionOutput.model_validate(d['decision']);guard=net.validate(d['demand'],decision)
        assert guard.allowed
        after=net.evaluate(d['demand'],decision)
        for k in ('latency_ms','loss_pct','throughput_kbps'):close(m[k],getattr(after,k),1e-6)
        assert net.queue==previous.get(key,[0,0]);previous[key]=after.queue_mbit
        assert e['backend']=='simulated_rule_table' and e['physical_switch_contacted'] is False
        for rule in e['expired_rules']:assert rule['expires_virtual_seconds']==cycle*5
        if e['installed_rule']:
            rule=e['installed_rule'];assert rule['hard_timeout']==5 and rule['expires_virtual_seconds']==cycle*5+5 and rule['priority']==100
            assert rule['match']==decision.target_flow_match
        assert e['effective_output_port']==(3 if decision.action=='reroute' else 2)
        assert e['meter_kbps']==decision.rate_limit_kbps
        if m['origin']=='api' and m['mode']=='bounded':assert e['provider_suggestion'] is not None
        if m['origin'] in ('api_cache','local_rule_cache','healthy_bypass','episodic_memory'):assert not d['provider_calls']
        if not offline:
            close(m['deadline_miss'],m['control_elapsed_ms']>5000)
            audit=d['provider_calls'];calls+=audit
            assert m['api_calls']==sum(a.get('request_started',True) for a in audit)
            assert m['api_successes']==sum(a['status']=='ok' for a in audit)
            for a in audit:
                if a['status']=='deferred':assert not a['request_started']
                if a['status']=='deadline_timeout':assert e['provider_suggestion'] is None
    for end in read(folder/'rule_expiry.json'):assert not end['active_rules'] and end['effective_output_port']==2 and end['meter_kbps'] is None
    if not offline:
        for seed,digest in s['trace_sha256'].items():assert hashlib.sha256((folder/f'traffic_{seed}.json').read_bytes()).hexdigest()==digest
        csvrows=list(csv.DictReader((folder/'metrics.csv').open(encoding='utf-8')));assert len(csvrows)==len(details)
        for m,g in s['groups'].items():
            records=[d['metrics'] for d in details if d['metrics']['mode']==m]
            for k in ('latency_ms','loss_pct','throughput_kbps','reward','control_elapsed_ms'):close(g[k],mean(r[k] for r in records))
            for k in ('api_calls','api_successes','deadline_miss','local_timeouts','deferred'):assert g[k]==sum(r[k] for r in records)
    return {'windows':len(details),'origins':dict(origins),'request_audits':len(calls),'rules_replayed':True}

def main():
    evidence={'primary_v4':primary(),'normal_experiments_preserved':verify_evidence(),'v3_preserved':verify_benchmark('v3',86400),'v2_preserved':verify_benchmark()}
    evidence['rule_learning']=rules_and_timing(B/'rule_demo_offline',True)
    evidence['providers']={}
    for provider in ('gemini','openrouter'):
        for suffix in ('','_scheduled','_final','_pooled'):
            evidence['providers'][provider+suffix]=rules_and_timing(B/f'latency_{provider}{suffix}')
    runtime=read(OUT/'runtime_validation.json');browser=read(OUT/'browser_validation.json')
    assert runtime['status']=='passed' and runtime['isolated_virtual_environment']
    assert not browser['errors'] and not browser['mobileOverflow'] and browser['virtualEnvironment'] and browser['memoryDemo']=='passed'
    manifest=read(B/'figures/manifest.json');assert len(manifest['figures'])==17
    for name,digest in manifest['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    for fig in manifest['figures']:
        for extension in ('png','svg'):assert (ROOT/fig[extension]).stat().st_size>1000
    pdfs={n:len(PdfReader(FINAL/n).pages) for n in ('SELF_X_Report.pdf','SELF_X_Presentation.pdf','SELF_X_Benchmark_Atlas.pdf')}
    assert pdfs=={'SELF_X_Report.pdf':16,'SELF_X_Presentation.pdf':20,'SELF_X_Benchmark_Atlas.pdf':17},pdfs
    with ZipFile(FINAL/'SELF_X_Presentation.pptx') as z:
        assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==20
        assert len([n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n)])==8
        assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')])==8
    files=source_files()
    for path in files:verify_no_secrets(path)
    result={'status':'passed','revision':4,'evidence':evidence,'figures_checked':17,'pdf_pages':pdfs,'editable_native_charts':8,'source_files_checked':len(files),'credentials_excluded':True,
        'tests':runtime['checks'][0]['output_tail'].strip(),'virtual_environment':runtime['prefix'],'browser':browser}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    archive=FINAL/'SELF_X_Submission.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for path in source_files():z.write(path,'selfx/'+path.relative_to(ROOT).as_posix())
    with ZipFile(archive) as z:assert not any(n.endswith('/.env') or '/.venv/' in n or '/tmp/' in n for n in z.namelist())
    (FINAL/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(FINAL.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','pdf_pages':pdfs,'figures':17,'source_files':len(files),'zip_bytes':archive.stat().st_size,'tests':result['tests']},indent=2))

if __name__=='__main__':main()
