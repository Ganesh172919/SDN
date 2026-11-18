"""Build the course submission and its Overleaf source from a project checkout."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = ROOT / "output/submission/current"
MAX_BYTES = 100_000_000
OVERLEAF = (
    "main.tex", "execution.tex", "trace_results.tex", "refs.bib", "README_OVERLEAF.md",
    "comparison/results.tex", "comparison/manuscript_table.tex",
    "comparison/revision_analysis.tex", "comparison/expanded_profiles.tex",
    "comparison/paper_architecture.pdf", "comparison/paper_delay_effects.pdf",
    "comparison/paper_delay_loss.pdf", "comparison/paper_window_traces.pdf",
)
MATERIALS = (
    "Overleaf_SELF_X_Bundle.zip",
    "SELF_X_Revision_Report.pdf", "SELF_X_Revision_Response.md",
    "SELF_X_Deep_Review_Round_1.md", "SELF_X_Deep_Review_Round_2.md",
    "SELF_X_Initial_Draft.pdf", "SELF_X_Revision_1.pdf", "SELF_X_Revision_2.pdf",
    "SELF_X_Revision_2_Expanded.pdf", "SELF_X_Revision_2_Decision_Model.pdf",
    "SELF_X_Presentation.pdf", "SELF_X_Presentation.pptx",
)
ROOT_FILES = {
    ".env.example", ".gitignore", "README.md", "REPRODUCE.md", "pytest.ini",
    "PROJECT_FLOW.md", "requirements.txt", "requirements-comparison.txt",
    "PS_01_Problem_Statement.pdf", "SELF_X_IEEE_Paper.pdf", "mermaid-diagram.svg",
}
DESKTOP_REPLAY = {
    "selfx/output/benchmarks/v4/summary.json",
    "selfx/output/benchmarks/v4/metrics.csv",
}
DASHBOARD_EVIDENCE = (
    "selfx/output/ablation_table2/", "selfx/output/baseline_table5/",
    "selfx/output/dpp_validation/", "selfx/output/transfer_evaluation/",
    "selfx/output/topologies/", "selfx/output/traffic/", "selfx/output/statistical_tests/",
    "selfx/output/pipeline_study/", "selfx/output/explainer/",
)
CREDENTIAL = re.compile(
    rb"AIza[0-9A-Za-z_-]{35}|gsk_[0-9A-Za-z]{40,}|sk-(?:proj-|or-v1-)?[0-9A-Za-z_-]{30,}|"
    rb"hf_[0-9A-Za-z]{28,}|gh[pousr]_[0-9A-Za-z]{36,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
TEXT = {".py", ".ps1", ".sh", ".md", ".json", ".jsonl", ".csv", ".js", ".svg",
        ".html", ".css", ".tex", ".bib", ".yml", ".yaml", ".txt", ".example", ".ini"}


def include(name):
    if name in ROOT_FILES:
        return True
    if name.startswith("Web/data/"):
        return False
    if name.startswith("selfx/output/"):
        return (
            name.startswith(DASHBOARD_EVIDENCE)
            or name in DESKTOP_REPLAY
            or re.fullmatch(r"selfx/output/experiments/[a-z0-9_]+/summary\.json", name)
        )
    if name.startswith("paper/"):
        return (
            name in {"paper/COMPARISON.md", "paper/AUDITED_COMPARISON_SPECIFICATION.md"}
            or name in {f"paper/{item}" for item in OVERLEAF}
            or name.startswith(("paper/comparison/", "paper/figures/"))
        )
    if name.startswith("results/"):
        return re.fullmatch(r"results/a[0-5]-canonical-run-seed42/(?:run\.json|summary\.json|metrics\.jsonl)", name)
    return name.startswith(("selfx/", "slow-loop/", "Web/", "sdn-self-improving-agent/",
                            "docs/", "visualizations/"))


def source_files():
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    candidates = sorted({
        name for name in tracked if include(name) and (ROOT / name).is_file()
    })
    required = ROOT_FILES - {"PROJECT_FLOW.md", "mermaid-diagram.svg"}
    required |= DESKTOP_REPLAY | {f"paper/{item}" for item in OVERLEAF}
    required |= {
        "Web/server.py", "Web/index.html", "paper/comparison/runs.json",
        "selfx/output/pipeline_study/adapter/adapter_model.safetensors",
    }
    missing = required.difference(candidates)
    if missing:
        raise ValueError(f"Missing submission inputs: {', '.join(sorted(missing))}")
    return candidates


def write_sources(archive, entries):
    for path, member in entries:
        if path.is_symlink():
            raise ValueError(f"Symbolic link in submission inputs: {member}")
        if path.suffix.lower() in TEXT and CREDENTIAL.search(path.read_bytes()):
            raise ValueError(f"Possible credential in {member}")
        archive.write(path, member)


def check_archive(path):
    with ZipFile(path) as archive:
        members = archive.namelist()
        if archive.testzip() is not None or len(members) != len(set(members)):
            raise ValueError(f"Invalid archive: {path.name}")


def build(destination, materials, compiled_paper):
    source = source_files()
    supplied = [name for name in MATERIALS if (materials / name).is_file()]
    destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination) as staging:
        staged = Path(staging)
        paper = staged / "SELF_X_IEEE_Paper.pdf"
        paper.write_bytes(compiled_paper.read_bytes())
        overleaf = staged / "Overleaf_Source.zip"
        full = staged / "SELF_X_Submission.zip"
        with ZipFile(overleaf, "w", ZIP_DEFLATED, compresslevel=9) as archive:
            write_sources(archive, ((ROOT / "paper" / name, name) for name in OVERLEAF))
        with ZipFile(full, "w", ZIP_DEFLATED, compresslevel=9) as archive:
            write_sources(archive, (
                (paper if name == paper.name else ROOT / name, name) for name in source
            ))
            release = "output/submission/current"
            write_sources(archive, ((materials / name, f"{release}/{name}") for name in supplied))
            archive.write(overleaf, f"{release}/{overleaf.name}")
        if full.stat().st_size >= MAX_BYTES:
            raise ValueError(f"Archive is {full.stat().st_size:,} bytes; limit is {MAX_BYTES:,}")
        check_archive(overleaf)
        check_archive(full)
        for name in supplied:
            (staged / name).write_bytes((materials / name).read_bytes())

        files = [full, overleaf, paper, *(staged / name for name in supplied)]
        checksums = staged / "SHA256SUMS.txt"
        checksums.write_text(
            "".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files),
            encoding="utf-8",
        )
        for path in [*files, checksums]:
            print(f"{path.name}: {path.stat().st_size:,} bytes")
            path.replace(destination / path.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", "--output", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--materials", type=Path, help="Directory with prepared review and presentation files.")
    parser.add_argument("--paper", type=Path, default=ROOT / "SELF_X_IEEE_Paper.pdf",
                        help="Compiled manuscript to ship with the source.")
    args = parser.parse_args()
    build(args.destination, args.materials or args.destination, args.paper)


if __name__ == "__main__":
    main()
