# Compile the SELF-X IEEE-format manuscript

The audited EC466 manuscript starts at `main.tex`. The project includes its
bibliography, generated LaTeX tables and four vector figures. It uses the
standard IEEEtran class and bibliography style from the TeX distribution.

## Overleaf

From a Git checkout, run the following command at the repository root.

```console
python selfx/scripts/package_ieee_submission.py
```

Upload `output/submission/current/Overleaf_Source.zip` as a new Overleaf project.
Select `main.tex` as the main document and use pdfLaTeX. The archive already
contains the evidence-derived files required to compile the paper.

For a different output directory, pass `--destination DIR`. Pass
`--materials DIR` to include prepared review documents and presentation files
from another directory.

## Local build

With TeX Live or MacTeX, run these commands from the repository root.

```console
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

If latexmk is unavailable, run pdfLaTeX, BibTeX, and pdfLaTeX twice.

```console
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Copy the resulting `main.pdf` to `SELF_X_IEEE_Paper.pdf` at the repository root
before rebuilding the course archive.

## Rebuild the paper evidence

Use [REPRODUCE.md](../REPRODUCE.md) in the project repository or the full course
archive. The paper reads tables from `comparison/results.tex`,
`comparison/manuscript_table.tex`, `comparison/revision_analysis.tex`, and
`comparison/expanded_profiles.tex`. It references only the four
`comparison/paper_*.pdf` figures.
