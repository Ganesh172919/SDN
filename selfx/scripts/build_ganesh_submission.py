"""Package only Ganesh's implementation/evidence and optional offline base model."""
from pathlib import Path,PurePosixPath
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
import argparse
import json
import re
import shutil
import stat
import uuid

from agent.self_improvement.common import read,sha256,write

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'output/self_improvement/ganesh_20261106'
READY=EVIDENCE/'bounded_adoption/submission_readiness.json'
TARGET=ROOT/'output/submission/ganesh'
PREFIX='Ganesh_Submission'
SECRET=re.compile(rb'(?:sk-or-v1-[A-Za-z0-9]{30,}|AIza[A-Za-z0-9_-]{25,}|sk-ant-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)')


def copy(source,destination):
    source,destination=Path(source),Path(destination)
    if not source.is_file() or source.is_symlink() or source.name in {'.env','writer.lock'}:
        raise ValueError('missing or disallowed submission source')
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)


def text_and_path_check(folder):
    for path in folder.rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(folder)
        if any(part in {'.venv','.deps','__pycache__','.pytest_cache','.git'} for part in relative.parts):
            raise ValueError('environment or cache included in submission')
        if path.name=='.env' or path.suffix=='.pyc':raise ValueError('disallowed submission file')
        if path.suffix.lower() in {'.py','.json','.jsonl','.md','.txt','.csv','.ps1','.sha256'} and SECRET.search(path.read_bytes()):
            raise ValueError('credential pattern found in submission input')


def checksum_manifest(folder,name):
    paths=sorted(p for p in folder.rglob('*') if p.is_file() and p.name!=name)
    (folder/name).write_text(''.join(f'{sha256(p)}  {p.relative_to(folder).as_posix()}\n' for p in paths),encoding='utf-8')
    return len(paths)


def check_verified_source(stage,readiness):
    hashes=readiness.get('verified_source_sha256',{})
    if len(hashes)!=44:
        raise ValueError('missing verified source fingerprint set')
    for relative,expected in hashes.items():
        path=(stage/relative).resolve()
        if not path.is_relative_to(stage.resolve()) or not path.is_file() or sha256(path)!=expected:
            raise ValueError(f'packaged source differs from verified source: {relative}')


def archive(folder,destination):
    with ZipFile(destination,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(p for p in folder.rglob('*') if p.is_file()):
            name=PREFIX+'/'+path.relative_to(folder).as_posix()
            info=ZipInfo(name,date_time=(2026,11,6,0,0,0));info.compress_type=ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o644)<<16
            with path.open('rb') as source,z.open(info,'w',force_zip64=True) as sink:
                shutil.copyfileobj(source,sink,1024*1024)
    with ZipFile(destination) as z:
        seen=set()
        for info in z.infolist():
            pure=PurePosixPath(info.filename)
            if pure.is_absolute() or '..' in pure.parts or ':' in info.filename or info.filename.casefold() in seen:
                raise ValueError('unsafe or duplicate archive member')
            seen.add(info.filename.casefold())
        if z.testzip() is not None:raise ValueError('archive CRC verification failed')


def build(include_model=True,stage_only=False):
    readiness=read(READY) if READY.exists() else {}
    if not stage_only and (readiness.get('status')!='ready' or readiness.get('scope')!='Ganesh T20-T25; CPU/frozen-replay'):
        raise ValueError('submission verification is not complete')
    fresh=read(EVIDENCE/'bounded_adoption/submission_verification.json')
    if fresh.get('fresh_model_predictions',{}).get('status')!='passed':
        raise ValueError('fresh model verification required before packaging')
    TARGET.mkdir(parents=True,exist_ok=True)
    if not stage_only:
        copy(ROOT/'docs/GANESH_SUBMISSION_AND_DEMO.md',TARGET/'GANESH_SUBMISSION_AND_DEMO.md')
    temporary=ROOT/'tmp'/('ganesh-package-'+uuid.uuid4().hex)
    stage=temporary/PREFIX;stage.mkdir(parents=True)
    if not stage.resolve().is_relative_to((ROOT/'tmp').resolve()):raise ValueError('staging escaped workspace')
    for path in (ROOT/'agent').rglob('*.py'):
        copy(path,stage/'selfx'/path.relative_to(ROOT))
    for name in ('__init__.py','simulator.py','run_benchmarks.py','run_simulation.py'):
        copy(ROOT/'eval'/name,stage/'selfx/eval'/name)
    for name in ('config.py','safety.py','ryu_client.py','latency_probe.py','requirements-lora.txt',
                 'requirements-submission.txt','requirements-submission-lock.txt'):
        copy(ROOT/name,stage/'selfx'/name)
    copy(ROOT/'tests/test_self_improvement.py',stage/'selfx/tests/test_self_improvement.py')
    copy(ROOT/'scripts/verify_self_improvement.py',stage/'selfx/scripts/verify_self_improvement.py')
    copy(ROOT/'scripts/setup_ganesh_submission.py',stage/'setup_submission.py')
    copy(ROOT/'scripts/verify_ganesh_bundle.py',stage/'tools/verify_bundle.py')
    copy(ROOT/'scripts/check_ganesh_portability.py',stage/'tools/check_portability.py')
    for name in ('SELF_IMPROVEMENT.md','GANESH_TASK_COMPLETION.md','GANESH_PENDING_WORK_CHECK.md'):
        copy(ROOT/'docs'/name,stage/'selfx/docs'/name)
    for path in EVIDENCE.rglob('*'):
        if path.is_file() and path.name not in {'writer.lock','handoff.json'} and not path.name.endswith('.tmp'):
            copy(path,stage/'selfx'/path.relative_to(ROOT))
    copy(ROOT/'docs/GANESH_SUBMISSION_README.md',stage/'README.md')
    if not stage_only:
        copy(TARGET/'GANESH_SUBMISSION_AND_DEMO.md',stage/'GANESH_SUBMISSION_AND_DEMO.md')
        copy(TARGET/'Ganesh_Submission_Report.pdf',stage/'documentation/Ganesh_Submission_Report.pdf')
    copy(ROOT.parent/'output/pdf/SELF_X_Pending_Work_Audit.pdf',stage/'documentation/SELF_X_Pending_Work_Audit.pdf')
    if READY.exists():copy(READY,stage/'VERIFICATION_SUMMARY.json')
    (stage/'selfx/README.md').write_text('Ganesh T20-T25 component. Start with ../README.md.\n',encoding='utf-8')
    (stage/'THIRD_PARTY_NOTICES.md').write_text(
        'The base model is HuggingFaceTB/SmolLM2-135M-Instruct, pinned revision '
        '12fd25f77366fa6b3b4b768ec3050bf629380bac. Its publisher identifies it as Apache-2.0. '
        'The optional companion archive includes the publisher model card and Apache license text. '
        'Python libraries retain their own installed license notices. No new license is applied to student project code.\n',encoding='utf-8')
    text_and_path_check(stage)
    if not stage_only:check_verified_source(stage,readiness)
    count=checksum_manifest(stage,'MANIFEST.sha256')
    if stage_only:
        result={'status':'staged_for_portability_test','staging':str(stage),'submission_files':count}
        write(TARGET/'STAGING.json',result);print(json.dumps(result,indent=2));return result
    core=TARGET/'Ganesh_Submission.zip';archive(stage,core)
    outputs=[core]
    if include_model:
        model_stage=temporary/'offline';model_stage.mkdir()
        source=ROOT/'.models/smollm2-135m-instruct-12fd25f7'
        base_files=('config.json','generation_config.json','tokenizer.json','tokenizer_config.json',
            'special_tokens_map.json','model.safetensors','download_manifest.json','MODEL_CARD.md','LICENSE-APACHE-2.0.txt')
        for name in base_files:
            copy(source/name,model_stage/'selfx/.models/smollm2-135m-instruct-12fd25f7'/name)
        (model_stage/'OFFLINE_MODEL_README.md').write_text(
            'Extract this optional archive into the same parent directory as Ganesh_Submission.zip. '
            'It supplies the pinned base model under the same Ganesh_Submission/selfx/.models folder. '
            'Python dependencies still require installation. Run tools/verify_bundle.py after extracting both archives.\n',encoding='utf-8')
        checksum_manifest(model_stage,'MODEL_FILES.sha256')
        model_zip=TARGET/'Ganesh_Offline_Model.zip';archive(model_stage,model_zip);outputs.append(model_zip)
    all_outputs=outputs+[TARGET/'Ganesh_Submission_Report.pdf',TARGET/'GANESH_SUBMISSION_AND_DEMO.md']
    (TARGET/'SHA256SUMS.txt').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in all_outputs),encoding='utf-8')
    result={'status':'packaged','staging':str(stage),'submission_files':count,
        'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in all_outputs}}
    write(TARGET/'PACKAGE_CONTENTS.json',result)
    print(json.dumps(result,indent=2))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--without-model',action='store_true')
    parser.add_argument('--stage-only',action='store_true')
    args=parser.parse_args();build(not args.without_model,args.stage_only)


if __name__=='__main__':main()
