"""Create the tested Python 3.12 environment for the portable Ganesh submission."""
from pathlib import Path
import argparse
import subprocess
import sys
import venv


def project_root():
    here=Path(__file__).resolve().parent
    for candidate in (here/"selfx",here.parent,here):
        if (candidate/"requirements-submission.txt").is_file():
            return candidate
    raise RuntimeError("submission requirements are missing")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv",help="optional environment path; defaults to selfx/.venv")
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,12):
        raise SystemExit("Use Python 3.12, which matches the tested CPU submission environment.")
    project=project_root()
    environment=Path(args.venv).resolve() if args.venv else project/".venv"
    executable=environment/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")
    if not executable.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    def run(*arguments):
        subprocess.run([str(executable),*arguments],cwd=project,check=True)
    run("-m","pip","install","torch==2.8.0","--index-url","https://download.pytorch.org/whl/cpu","--disable-pip-version-check")
    lock=project/"requirements-submission-lock.txt"
    run("-m","pip","install","-r",str(lock if lock.exists() else project/"requirements-submission.txt"),"--disable-pip-version-check")
    run("-m","pip","check")
    print(f"Ready: {executable}")


if __name__=="__main__":main()
