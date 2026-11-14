# Reproduce the SELF-X IEEE paper

Team SDN_07 · EC466 Software Defined Networks · IIIT Dharwad

Use the archive root (the directory containing this file). The paper reports only the audited CPU comparison, which runs real local language model inference and trains the neural baselines. Other experiments and lab components are not evidence for this paper.

## 1. Install the CPU environment

Use 64-bit Python 3.12. Windows PowerShell:

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-comparison.txt
~~~

Linux/macOS:

~~~sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-comparison.txt
~~~

The commands below assume the virtual environment is active or that `python` is replaced with `.\.venv\Scripts\python.exe` on Windows. The rerun was verified on Windows x86-64, Python 3.12.15, and PyTorch 2.8.0+cpu with two threads and deterministic algorithms. No credentials, GPU, Mininet, or cloud inference are required.

## 2. Get the model and inspect the inputs

The first run downloads the public HuggingFaceTB/SmolLM2-135M-Instruct model at revision 12fd25f77366fa6b3b4b768ec3050bf629380bac into selfx/.models/. Internet access is required for dependency installation and the first model download. The checkpoint, config, and training evidence for the frozen adapter are in selfx/output/pipeline_study/adapter/. The earlier synthetic training replay is in selfx/output/pipeline_study/replay_dataset.jsonl. The paper does not train an adapter on its evaluation traces.

All evaluation traffic is **synthetic**. selfx/traffic_gen.py generates the schedule; selfx/eval/pipeline_model.py projects it onto 100 ms demand slots. There is no external traffic dataset. The three profiles, indexed by seed modulo three, are steady_bursty, flash_crowd, and volatile_dpp.

| Setting | Value |
| --- | --- |
| Neural training | Seeds 1000–1017; 120 simulated seconds each |
| Paired test | Seeds 2100–2111; 180 simulated seconds each; four seeds per profile |
| Neural initialization | DQN 3928; IQL route 3928 and meter 3929 |
| Two fluid paths | 10 Mbps and 2 Mbit buffer each; propagation 2 and 12 ms |
| Control timing | 100 ms slot; 5 s window; 30 s governance epoch; 400 ms assumed per model stage |
| Guard | At most 90% projected alternate utilization; at least 512 kbps meter and at most 20% bulk reduction |
| S5 parameters | Initial V=8; delay/loss/goodput/energy/resource weights 0.25/0.25/0.25/0.15/0.10; prior 0.20 |
| Neural settings | 2 × 64 hidden units, replay 20,000, batch 64, Adam 0.001, discount 0.97; train every 8 slots and copy targets every 100 updates |
| Tabular settings | Online per episode; initial epsilon 0.20, decay 0.995, floor 0.02; learning rate 0.25, discount 0.90 |

paper/main.tex lists all fourteen configurations. paper/comparison/runs.json contains seed assignments, training fingerprints, model and adapter identities, per-slot action hashes, and 5 s measurements. effects.csv and effects.json contain paired analyses. SELF_X_Algorithm_Comparison.pdf in that directory has thirteen full comparison plots.

## 3. Rerun the results and figures

~~~console
python -m pytest --basetemp .pytest-tmp selfx/tests/test_audited_comparison.py selfx/tests/test_pipeline_study.py
python selfx/eval/run_audited_comparison.py --smoke --output reproduced/smoke
python selfx/eval/run_audited_comparison.py --output reproduced/full
python selfx/eval/plot_manuscript.py --effects reproduced/full/effects.json --output reproduced/full
python selfx/eval/plot_expanded_paper.py --runs reproduced/full/runs.json --output reproduced/full
python selfx/eval/verify_manuscript_reproduction.py paper/comparison/runs.json reproduced/full/runs.json
python selfx/eval/revision_analysis.py --runs reproduced/full/runs.json --output reproduced/full
python selfx/eval/verify_fixed_governor.py --runs reproduced/full/runs.json --output reproduced/full
python selfx/eval/verify_neural_guard.py --runs reproduced/full/runs.json --output reproduced/full
~~~

The smoke run uses short traces and is not paper evidence. A few optional integration tests may skip when legacy provider replay files are absent. The full run retrains DQN/IQL, evaluates 168 controller/seed runs (302,400 test slots), and writes runs.json, effects.csv, effects.json, results.tex, thirteen PNGs, and the atlas. The paper plotting commands generate its four vector figures and the main and workload tables. The revision checks regenerate trace-level intervals and Holm sensitivity, test fixed governance on S5, and retrain/replay the neural arms to audit proposal disagreements. The verifier compares recorded model/adapter identities, network fingerprints, applied-action hashes and all run data. Platform or library differences can affect numerical reproducibility.

To rebuild the plots without inference or training:

~~~console
python selfx/eval/plot_audited_comparison.py --output paper/comparison
python selfx/eval/plot_manuscript.py
python selfx/eval/plot_expanded_paper.py
python selfx/eval/revision_analysis.py
~~~

To compile from the shipped evidence, see paper/README_OVERLEAF.md. To build with a rerun, copy results.tex, manuscript_table.tex, revision_analysis.tex, paper_delay_effects.pdf, paper_delay_loss.pdf, paper_architecture.pdf, paper_window_traces.pdf, and expanded_profiles.tex from reproduced/full to paper/comparison first. With TeX Live and latexmk:

~~~console
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
~~~

## 4. Other implementation entry points

- `python Web/server.py` starts the local simulation dashboard at http://127.0.0.1:5000.
- selfx/ contains the controller, Ryu client, traffic generator and Mininet topology scripts, as well as the evaluation. Follow the repository README and selfx/docs/ for the optional Linux lab and dashboard.
- slow-loop/ contains a separate governance prototype and dependency list. The IEEE experiment uses selfx/eval/audited_models.py as its governor.
- Legacy benchmark drivers and supporting source remain available for project inspection. They do not regenerate the paper's results.
