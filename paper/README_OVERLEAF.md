# Compile the SELF-X paper in Overleaf

This project uses the [official IEEE Conference Template](https://www.overleaf.com/latex/templates/ieee-conference-template/grfzhhncsfqn) and the unmodified IEEEtran conference class.

1. In Overleaf, select **New Project → Upload Project** and choose **Overleaf_Source.zip**.
2. Select **main.tex** as the main document and **pdfLaTeX** as the compiler.
3. Recompile and download the PDF. Keep execution.tex, trace_results.tex and the comparison directory at the project root.

On a machine with TeX Live and latexmk, run `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` from this source directory. The implementation bundle includes separate commands for generating the table and figures and a supplementary 13-plot atlas.
