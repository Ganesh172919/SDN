"""Create an all-inclusive Overleaf bundle containing all TeX, Bib, PDF, and PNG figure assets."""
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT / "paper"
OUT_PATH = ROOT / "submission" / "Overleaf_SELF_X_Bundle.zip"

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(OUT_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in PAPER_DIR.rglob("*"):
        if f.is_file():
            # Exclude presentation and large intermediate raw files if any
            if f.suffix.lower() in {".pptx", ".html"}:
                continue
            if f.name in {"runs.json", "historical_main.tex"}:
                continue
            rel = f.relative_to(PAPER_DIR)
            z.write(f, str(rel))

print(f"Created {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
