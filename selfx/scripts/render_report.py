"""Use the packaged DOCX renderer with Microsoft Word conversion on Windows.

The packaged runtime has no Windows LibreOffice. Word exports the actual DOCX;
the packaged renderer handles PDF rasterization and page naming unchanged.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path.home() / ".codex/plugins/cache/openai-primary-runtime/documents/26.1015.12040/skills/documents"
spec = importlib.util.spec_from_file_location("packaged_docx_renderer", SKILL / "render_docx.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def word_convert(doc_path, user_profile, convert_tmp_dir, stem, verbose=False):
    output = Path(convert_tmp_dir) / (stem + ".pdf")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/export_word.ps1"),
                    "-InputPath", str(Path(doc_path).resolve()), "-OutputPath", str(output)], check=True, capture_output=True, timeout=120)
    return str(output), "Converted from the actual DOCX using Microsoft Word"


if __name__ == "__main__":
    local_tmp = ROOT / "tmp"
    os.environ["TEMP"] = os.environ["TMP"] = str(local_tmp)
    tempfile.tempdir = str(local_tmp)
    renderer.convert_to_pdf = word_convert
    renderer.main()
