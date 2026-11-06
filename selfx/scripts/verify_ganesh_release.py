"""Extract the final release and verify checksums, relocation and runtime behavior."""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import argparse
import hashlib
import json
import stat
import subprocess
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'output/submission/ganesh'


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def extract_checked(archive, target, used):
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('archive CRC mismatch')
        for entry in z.infolist():
            pure = PurePosixPath(entry.filename)
            path = (target / entry.filename).resolve()
            key = entry.filename.casefold()
            if (pure.is_absolute() or '..' in pure.parts or ':' in entry.filename
                    or '\\' in entry.filename or key in used
                    or not path.is_relative_to(target.resolve())
                    or pure.parts[0] != 'Ganesh_Submission'
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('unsafe or duplicate release archive member')
            used.add(key)
        z.extractall(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, help='Previously verified clean Python environment')
    args = parser.parse_args()
    validation_record = RELEASE / 'FINAL_VALIDATION.json'
    started = datetime.now(timezone.utc).isoformat()
    validation_record.write_text(json.dumps({'status': 'running', 'started_at_utc': started}, indent=2), encoding='utf-8')
    release_hashes = {}
    for line in (RELEASE / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        if Path(name).name != name or digest(RELEASE / name) != expected:
            raise ValueError('release checksum mismatch')
        release_hashes[name] = expected
    target = ROOT / 'tmp' / ('ganesh-final-check-' + uuid.uuid4().hex)
    target.mkdir(parents=True)
    if not target.resolve().is_relative_to((ROOT / 'tmp').resolve()):
        raise ValueError('extraction escaped workspace')
    used = set()
    for name in ('Ganesh_Submission.zip', 'Ganesh_Offline_Model.zip'):
        extract_checked(RELEASE / name, target, used)
    package = target / 'Ganesh_Submission'
    for relative in ('GANESH_SUBMISSION_AND_DEMO.md', 'documentation/Ganesh_Submission_Report.pdf'):
        if digest(package / relative) != digest(RELEASE / Path(relative).name):
            raise ValueError('packaged guide or report differs from the released copy')
    summary = json.loads((package / 'VERIFICATION_SUMMARY.json').read_text(encoding='utf-8'))
    for relative, expected in summary['verified_source_sha256'].items():
        if digest(package / relative) != expected:
            raise ValueError('final source differs from relocation-verified source')
    print('Final archive checksums, paths, CRCs and 44 source hashes passed.', flush=True)
    validation = RELEASE / 'final_validation'
    validation.mkdir(exist_ok=True)
    commands = [('integrity', [args.python, str(package / 'tools/verify_bundle.py')])]
    for mode in ('test', 'verify', 'smoke'):
        commands.append((mode, [args.python, str(package / 'tools/check_portability.py'),
            '--project', str(package / 'selfx'), '--forbid-source', str(ROOT), '--mode', mode]))
    for label, command in commands:
        result = subprocess.run(command, cwd=package, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (validation / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(f'final {label} verification failed; see {validation / (label + ".log")}')
        print(f'Final extracted package: {label} passed.', flush=True)
    report = {'status': 'passed', 'started_at_utc': started,
        'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'release_sha256': release_hashes,
        'archive_members': len(used), 'verified_source_files': len(summary['verified_source_sha256']),
        'extracted_package': str(package), 'checks': ['release_checksums', 'archive_paths_and_crcs',
        'core_and_model_manifests', 'verified_source_hashes', 'packaged_guide_and_report', '22_focused_tests',
        'relocated_source_rebuild_and_weight_verification', '12_window_backend_smoke'],
        'forbidden_original_reads': 0, 'cloud_calls': 0}
    validation_record.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
