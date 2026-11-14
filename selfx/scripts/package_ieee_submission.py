"""Package the course artifacts from tracked implementation and paper evidence."""
import argparse
from hashlib import sha256
import io
from pathlib import Path
import re
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = ROOT / "output/submission/SELF_X_2026-11-14"
OVERLEAF = (
    "main.tex", "execution.tex", "trace_results.tex", "refs.bib", "README_OVERLEAF.md", "comparison/results.tex",
    "comparison/manuscript_table.tex", "comparison/paper_delay_effects.pdf",
    "comparison/paper_delay_loss.pdf", "comparison/revision_analysis.tex",
    "comparison/paper_architecture.pdf", "comparison/paper_window_traces.pdf",
    "comparison/expanded_profiles.tex",
)
EXTRA = (
    "REPRODUCE.md", "selfx/eval/plot_expanded_paper.py", "selfx/eval/plot_manuscript.py", "selfx/eval/verify_manuscript_reproduction.py",
    "selfx/eval/revision_analysis.py", "selfx/eval/verify_fixed_governor.py",
    "selfx/eval/verify_neural_guard.py", "paper/comparison/neural_guard_check.json",
    "paper/comparison/revision_analysis.json", "paper/comparison/fixed_governor_check.json",
    "selfx/scripts/package_ieee_submission.py", *(f"paper/{n}" for n in OVERLEAF),
)
CREDENTIAL = re.compile(
    rb"AIza[0-9A-Za-z_-]{35}|gsk_[0-9A-Za-z]{40,}|sk-(?:proj-|or-v1-)?[0-9A-Za-z_-]{30,}|"
    rb"hf_[0-9A-Za-z]{28,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
TEXT = {".py", ".ps1", ".sh", ".md", ".json", ".jsonl", ".csv", ".js",
        ".html", ".css", ".tex", ".bib", ".yml", ".yaml", ".txt", ".example", ".ini"}


def include(name):
    if name in {"README.md", "requirements.txt", "requirements-comparison.txt", ".env.example",
                "selfx/output/pipeline_study/replay_dataset.jsonl", "paper/COMPARISON.md"}:
        return True
    if name.startswith("selfx/output/"):
        return name.startswith("selfx/output/pipeline_study/adapter/")
    if name.startswith("paper/"):
        return name.startswith("paper/comparison/")
    return name.startswith(("selfx/", "slow-loop/", "Web/", "sdn-self-improving-agent/",
                            "results/", "visualizations/"))


def write_sources(archive, entries):
    for path, member in entries:
        if path.suffix.lower() in TEXT and CREDENTIAL.search(path.read_bytes()):
            raise ValueError(f"Possible credential in {member}")
        archive.write(path, member)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DEST)
    destination = parser.parse_args().destination
    destination.mkdir(parents=True, exist_ok=True)
    overleaf = destination / "Overleaf_Source.zip"
    full = destination / "SELF_X_Submission.zip"
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    source = sorted({p for p in tracked if include(p)} | set(EXTRA))
    deliverables = sorted([*destination.glob("SELF_X_*.pdf"), *destination.glob("SELF_X_*.md")])
    with ZipFile(overleaf, "w", ZIP_DEFLATED, compresslevel=9) as z:
        write_sources(z, ((ROOT / "paper" / name, name) for name in OVERLEAF))
    with ZipFile(full, "w", ZIP_DEFLATED, compresslevel=9) as z:
        write_sources(z, ((ROOT / name, name) for name in source))
        write_sources(z, ((item, item.name) for item in deliverables))
        z.write(overleaf, overleaf.name)
    if full.stat().st_size >= 100_000_000:
        raise ValueError("Archive exceeds course upload limit")
    with ZipFile(full) as z:
        assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist()))
        assert "selfx/output/pipeline_study/adapter/adapter_model.safetensors" in z.namelist()
        with ZipFile(io.BytesIO(z.read(overleaf.name))) as nested:
            assert nested.testzip() is None and set(nested.namelist()) == set(OVERLEAF)
    items = [overleaf, full, *deliverables]
    (destination / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in items), encoding="utf-8"
    )
    for p in items:
        print(f"{p.name}: {p.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
