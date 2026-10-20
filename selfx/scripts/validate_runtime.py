"""Run the full portable project in its own interpreter and preserve real check results."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import config


def main():
    if sys.prefix == sys.base_prefix:
        raise SystemExit('Use the project .venv: .\run.ps1 all')
    results=[]
    for label,command in [
        ('tests',['-m','pytest','tests','eval/tests','-q']),
        ('portable_experiment',['-m','eval.run_simulation','--out-dir','output/experiments/venv_v4']),
        ('scenario_benchmarks',['-m','eval.run_v4_benchmarks']),
    ]:
        completed=subprocess.run([sys.executable,*command],cwd=config.PROJECT_ROOT,capture_output=True,text=True)
        record={'check':label,'exit_code':completed.returncode,'output_tail':completed.stdout[-1500:]}
        results.append(record)
        print(label+': '+('PASS' if completed.returncode==0 else 'FAIL'),flush=True)
        if completed.returncode:
            print(completed.stderr[-1500:]);break
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'python':sys.executable,'prefix':sys.prefix,
            'base_prefix':sys.base_prefix,'isolated_virtual_environment':sys.prefix!=sys.base_prefix,
            'status':'passed' if len(results)==3 and all(r['exit_code']==0 for r in results) else 'failed','checks':results}
    (config.PROJECT_ROOT/'output/runtime_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
