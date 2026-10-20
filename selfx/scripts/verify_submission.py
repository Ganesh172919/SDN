"""Verify submitted measurements, deliverables, source scope and credential exclusion."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import re
from pathlib import Path
from statistics import mean
from zipfile import ZipFile, ZIP_DEFLATED
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output"
FINAL=OUT/"submission"
EXCLUDE={".deps",".venv","__pycache__",".pytest_cache","tmp",".git","history","builds"}
SECRET=re.compile(rb"sk-or-v1-[A-Za-z0-9]{30,}|AQ\.[A-Za-z0-9_-]{30,}|AIza[A-Za-z0-9_-]{25,}|sk-ant-[A-Za-z0-9_-]{20,}")


def verify_evidence():
    results={}
    for name in ("offline","gemini","gemini_paced","openrouter","venv_full","gemini_venv","venv_v3","fast_gemini_demo"):
        folder=OUT/"experiments"/name
        summary=json.loads((folder/"summary.json").read_text(encoding="utf-8"))
        rows=list(csv.DictReader((folder/"metrics.csv").open(encoding="utf-8")))
        detail=[json.loads(line) for line in (folder/"trace.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows)==len(detail)
        for seed,sha in summary["trace_sha256"].items():
            assert hashlib.sha256((folder/f"traffic_{seed}.json").read_bytes()).hexdigest()==sha
        for c,group in summary["conditions"].items():
            selected=[r for r in rows if r["condition"]==c]
            assert len(selected)==group["windows"]
            for metric in ("latency_ms","throughput_kbps","loss_pct","reward"):
                assert math.isclose(mean(float(r[metric]) for r in selected),group[metric],abs_tol=1e-9)
        previous={}
        for trace in detail:
            m=trace["metrics"];key=(m["condition"],m["seed"])
            assert all(n<m["cycle"] for n in trace["retrieved_cycles"])
            assert m["provenance"]=="simulation"
            old=previous.get(key,[0,0]);outcome=trace["outcome"]
            assert math.isclose(sum(old)+outcome["offered_mbit"],outcome["delivered_mbit"]+outcome["dropped_mbit"]+sum(outcome["queue_mbit"]),abs_tol=1e-6)
            previous[key]=outcome["queue_mbit"]
        audit=json.loads((folder/"provider_calls.json").read_text(encoding="utf-8"))
        results[name]={"windows":len(rows),"api_ok":sum(a["status"]=="ok" for a in audit),"api_errors":sum(a["status"]!="ok" for a in audit)}
    return results


def source_files():
    files=[]
    for directory, folders, names in os.walk(ROOT, followlinks=False):
        folders[:]=[f for f in folders if f not in EXCLUDE and not f.startswith('.chart-data-')]
        for name in names:
            path=Path(directory)/name
            if name in {'.env','SHA256SUMS.txt'} or path.suffix.lower() in {'.zip','.pyc'} or name.startswith('_scratch'):continue
            files.append(path)
    return files


def verify_no_secrets(path):
    if path.suffix in {'.docx','.pptx'}:
        with ZipFile(path) as z:
            for item in z.namelist():
                assert not SECRET.search(z.read(item)), f"credential pattern in {path.name}"
    elif path.suffix.lower() in {'.py','.md','.rmd','.js','.mjs','.css','.json','.jsonl','.csv','.ps1','.txt','.example','.html',''}:
        assert not SECRET.search(path.read_bytes()), f"credential pattern in {path.name}"


def verify_benchmark(version='v2',expected_windows=57600):
    folder=OUT/'benchmarks'/version;summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((folder/'metrics.csv').open(encoding='utf-8')))
    assert len(rows)==summary['window_count']==expected_windows
    traces={}
    for key,digest in summary['traffic_sha256'].items():
        path=folder/('traffic_'+key+'.json')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        traces[key]=json.loads(path.read_text(encoding='utf-8'))
    groups={};previous={}
    for row in rows:
        key=(row['scenario'],row['condition'],row['seed']);groups.setdefault(key,[]).append(row)
        demand=traces[row['scenario']+'_'+row['seed']][int(row['cycle'])]
        assert row['flow_id']==demand['flow_id']
        for name in ('primary_background_mbps','alternate_background_mbps','elephant_mbps'):assert float(row[name])==demand[name]
        assert all(i<int(row['cycle']) for i in json.loads(row['retrieved_cycles']))
        old=previous.get(key,[0,0]);queues=[float(row['queue_primary_mbit']),float(row['queue_alternate_mbit'])]
        assert math.isclose(sum(old)+float(row['offered_mbit']),float(row['delivered_mbit'])+float(row['dropped_mbit'])+sum(queues),abs_tol=1e-6)
        assert row['provenance']=='simulation'
        if row['condition'] in {'A3','A4'}:assert row['safety_allowed']=='True'
        previous[key]=queues
    for (scenario,condition,seed),selected in groups.items():
        assert len(selected)==summary['cycles']
        expected=summary['groups'][scenario][condition]['seed_metrics'][seed]
        for metric in ('latency_ms','throughput_kbps','loss_pct','reward','control_elapsed_ms'):
            assert math.isclose(mean(float(r[metric]) for r in selected),expected[metric],abs_tol=1e-9)
    if version=='v3':
        assert summary['seeds']==list(range(1760,1770))
        indexed={(r['scenario'],r['seed'],r['cycle'],r['condition']):r for r in rows}
        for row in rows:
            if row['condition']=='A4':
                baseline=indexed[row['scenario'],row['seed'],row['cycle'],'H1']
                assert row['installed_action']==baseline['installed_action']
                assert all(row[k]==baseline[k] for k in ('latency_ms','throughput_kbps','loss_pct','reward'))
    return {'windows':len(rows),'scenarios':len(summary.get('scenarios',summary.get('levels_mbps',{}))),'controllers':len(summary['controllers']),'seeds':len(summary['seeds']),'traffic_hashes_checked':len(traces),'conservation':'passed','guarded_vetoes':0}


def verify_latency(name='latency_gemini'):
    folder=OUT/'benchmarks/v3'/name;summary=json.loads((folder/'summary.json').read_text())
    rows=list(csv.DictReader((folder/'metrics.csv').open()))
    details=[json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
    audit=json.loads((folder/'provider_calls.json').read_text())
    assert len(rows)==len(details)==summary['window_count']==72
    assert sum(int(r['api_calls']) for r in rows)==len(audit)
    for seed,digest in summary['trace_sha256'].items():assert hashlib.sha256((folder/f'traffic_{seed}.json').read_bytes()).hexdigest()==digest
    previous={}
    for r in rows:
        key=(r['mode'],r['seed']);old=previous.get(key,[0,0]);queue=[float(r['queue_primary_mbit']),float(r['queue_alternate_mbit'])]
        assert math.isclose(sum(old)+float(r['offered_mbit']),float(r['delivered_mbit'])+float(r['dropped_mbit'])+sum(queue),abs_tol=1e-6)
        assert all(i<int(r['cycle']) for i in json.loads(r['retrieved_cycles']))
        assert (r['deadline_miss']=='True')==(float(r['control_elapsed_ms'])>5000)
        if r['origin'] in {'api_cache','healthy_bypass','episodic_memory'}:assert int(r['api_calls'])==0
        previous[key]=queue
    for mode,g in summary['groups'].items():
        selected=[r for r in rows if r['mode']==mode]
        assert len(selected)==g['windows']==24
        for metric in ('control_elapsed_ms','decision_ms','latency_ms','throughput_kbps','loss_pct','reward','pacing_ms','transport_ms'):
            assert math.isclose(mean(float(r[metric]) for r in selected),g[metric],abs_tol=1e-8)
        assert sum(r['deadline_miss']=='True' for r in selected)==g['deadline_misses']
    return {'windows':len(rows),'api_requests':len(audit),'api_successes':sum(a['status']=='ok' for a in audit),
            'deadline_misses':{m:g['deadline_misses'] for m,g in summary['groups'].items()},'conservation':'passed'}


def verify_netflow():
    folder=OUT/'benchmarks/v3';rows=list(csv.DictReader((folder/'traffic/simulated_netflow.csv').open()))
    assert len(rows)==9600
    traces={};keys=set()
    for row in rows:
        key=(row['scenario'],row['seed']);cycle=int(row['start_virtual_ms'])//5000
        if key not in traces:traces[key]=json.loads((folder/f'traffic_{key[0]}_{key[1]}.json').read_text())
        demand=traces[key][cycle]
        assert (key,cycle) not in keys;keys.add((key,cycle))
        assert int(row['end_virtual_ms'])-int(row['start_virtual_ms'])==5000
        assert row['flow_id']==demand['flow_id']
        assert int(row['elephant_bytes_offered'])==round(demand['elephant_mbps']*1e6*5/8)
        assert row['provenance']=='synthetic_aggregate_not_packet_capture'
    return {'records':len(rows),'traffic_traces_matched':len(traces),'virtual_interval_ms':5000}


def main():
    evidence=verify_evidence()
    for name in ("SELF_X_Report.docx","SELF_X_Report.pdf","SELF_X_Presentation.pptx","SELF_X_Presentation.pdf","SELF_X_Benchmark_Atlas.pdf"):
        assert (FINAL/name).stat().st_size>10000, name
    pdf_counts={name:len(PdfReader(FINAL/name).pages) for name in ("SELF_X_Report.pdf","SELF_X_Presentation.pdf","SELF_X_Benchmark_Atlas.pdf")}
    assert pdf_counts=={"SELF_X_Report.pdf":16,"SELF_X_Presentation.pdf":20,"SELF_X_Benchmark_Atlas.pdf":15}
    with ZipFile(FINAL/"SELF_X_Presentation.pptx") as z:
        slides=[n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
        charts=[n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n)]
        assert len(slides)==20 and len(charts)==8
        assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')])>=8
    benchmark={'v2_preserved':verify_benchmark(),'v3_primary':verify_benchmark('v3',86400),'v3_sensitivity':verify_benchmark('v3/memory_sensitivity',19200)}
    latency={'fresh':verify_latency(),'initial_diagnostic':verify_latency('latency_gemini_initial')}
    manifest=json.loads((OUT/'benchmarks/v3/figures/manifest.json').read_text())
    assert len(manifest['figures'])==15
    for name,digest in manifest['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    for figure in manifest['figures']:
        for extension in ('png','svg'):assert (ROOT/figure[extension]).stat().st_size>1000
    runtime=json.loads((OUT/'runtime_validation.json').read_text(encoding='utf-8'))
    browser=json.loads((OUT/'browser_validation.json').read_text(encoding='utf-8'))
    assert runtime['status']=='passed' and runtime['isolated_virtual_environment']
    assert not browser['errors'] and not browser['mobileOverflow'] and browser['virtualEnvironment']
    files=source_files()
    for path in files:verify_no_secrets(path)
    verification={"evidence":evidence,"benchmark":benchmark,"latency":latency,"synthetic_netflow":verify_netflow(),"figures_checked":15,"pdf_pages":pdf_counts,"source_files_checked":len(files),
                  "credentials_excluded":True,"tests":runtime['checks'][0]['output_tail'].strip(), "browser":browser,"virtual_environment":runtime['prefix']}
    (OUT/"verification.json").write_text(json.dumps(verification,indent=2),encoding="utf-8")
    archive=FINAL/"SELF_X_Submission.zip"
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for path in source_files():z.write(path,"selfx/"+path.relative_to(ROOT).as_posix())
    with ZipFile(archive) as z:
        assert not any(n.endswith('/.env') or '/.deps/' in n or '/tmp/' in n for n in z.namelist())
    (FINAL/"SHA256SUMS.txt").write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(FINAL.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding="utf-8")
    print(json.dumps(verification,indent=2))
    print(f"Submission archive: {archive.stat().st_size} bytes")


if __name__=='__main__':main()
