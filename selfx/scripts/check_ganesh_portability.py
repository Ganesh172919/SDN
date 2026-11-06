"""Test relocated files while denying reads from the original project tree."""
from pathlib import Path
import argparse
import json
import os
import runpy
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--forbid-source',required=True)
    parser.add_argument('--mode',choices=['verify','test','smoke'],required=True)
    args=parser.parse_args()
    project=Path(args.project).resolve();original=Path(args.forbid_source).resolve()
    if project==original:raise ValueError('relocation must use a separate project directory')
    os.chdir(project);sys.path.insert(0,str(project))
    os.environ['HF_HUB_OFFLINE']='1'
    forbidden=[original/name for name in ['agent','eval','scripts','tests','.models','output/self_improvement','config.py','safety.py','ryu_client.py']]
    forbidden=[os.path.normcase(str(p.resolve())) for p in forbidden]
    denied=[]
    def guard(event,arguments):
        if event!='open' or not arguments or not isinstance(arguments[0],(str,bytes,os.PathLike)):return
        path=os.path.normcase(os.path.abspath(os.fsdecode(arguments[0])))
        if any(path==prefix or path.startswith(prefix+os.sep) for prefix in forbidden):
            denied.append(path);raise RuntimeError('relocated package tried to read original project files')
    sys.addaudithook(guard)
    import config,agent
    assert config.PROJECT_ROOT==project
    assert Path(agent.__file__).resolve().is_relative_to(project)
    temp=project/'tmp';temp.mkdir(exist_ok=True)
    if args.mode=='test':
        import pytest
        status=pytest.main(['tests/test_self_improvement.py','-q','--basetemp=tmp/portable_pytest','--junitxml=tmp/portable_tests.xml'])
        if status:raise SystemExit(status)
        result={'status':'passed','mode':'test','denied_original_reads':len(denied)}
    elif args.mode=='verify':
        from scripts.verify_self_improvement import verify
        result=verify('output/self_improvement/ganesh_20261106/bounded_adoption')
        result['denied_original_reads']=len(denied)
    else:
        sys.argv=['eval.run_simulation','--provider','local_lora','--model','output/self_improvement/ganesh_20261106/bounded_adoption/registry',
            '--conditions','A0','A1','A2','--cycles','4','--seeds','3302','--out-dir','output/portable_backend_smoke']
        runpy.run_module('eval.run_simulation',run_name='__main__')
        summary=json.loads((project/'output/portable_backend_smoke/summary.json').read_text())
        assert all(c['api_decision_windows']==0 and c['api_reflection_windows']==0 for c in summary['conditions'].values())
        assert all(c['fallback_windows']==0 for c in summary['conditions'].values())
        result={'status':'passed','mode':'smoke','windows':12,'cloud_calls':0,'denied_original_reads':len(denied)}
    if denied:raise AssertionError('original project reads detected')
    (temp/('portable_'+args.mode+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','mode':args.mode,'denied_original_reads':len(denied)}))


if __name__=='__main__':main()
