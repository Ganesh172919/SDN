# SELF-X: loss-aware SDN control with episodic memory

SELF-X observes generated network traffic, retrieves completed local episodes, suggests a bounded action, validates it, installs a simulated rule and learns from the measured outcome. The website is a local review and replay dashboard. All network results are from a finite-buffer fluid model; Gemini and free OpenRouter requests are real.

[Project guide](docs/PROJECT_GUIDE.md) · [Current benchmarks](docs/BENCHMARKS_V4.md) · [Complete rule demo](docs/RULE_DEMO.md) · [Architecture](docs/ARCHITECTURE.md) · [R Markdown architecture](docs/ARCHITECTURE.Rmd) · [Submission](output/submission/)

## Run in the project environment

```powershell
.\setup.ps1
.\run.ps1 all
.\run.ps1 dashboard -Port 8766
```

Open http://127.0.0.1:8766. The `all` command runs the complete tests, all five normal-runner controllers and the nine-controller/eight-scenario benchmark in `.venv`. `.env` is the ignored key/configuration file; `.venv` is the isolated Python environment. Both provider keys are configured locally. Keys are never part of the report, slides or ZIP.

## Current measured results

| Controller | Delay ms | Goodput Mbps | Total loss % | Reward |
|---|---:|---:|---:|---:|
| A0 | 25.904 | 12.872 | 8.149 | 0.000000 |
| B1 | 20.609 | 13.024 | 6.996 | 0.061813 |
| A2 | 17.495 | 12.821 | 8.304 | 0.055081 |
| H1 | 17.131 | 12.956 | 7.391 | 0.077639 |
| A3 | 17.259 | 12.945 | 7.477 | 0.074975 |
| V3 | 17.131 | 12.956 | 7.391 | 0.077639 |
| H2 | 17.363 | 13.011 | 7.077 | 0.083304 |
| A4 | 17.452 | 13.011 | 7.075 | 0.082764 |
| O2 | 17.096 | 13.016 | 7.050 | 0.086096 |

The primary suite uses seeds 1900–1909, 120 windows, eight scenarios and nine controllers: 86,400 controller windows on 9,600 unique demand windows. A4 improves loss and reward over H1, with higher modeled delay. H2 shares the improved meter without memory and has slightly higher reward than A4. The gain over H1 cannot be attributed solely to memory. All cold-start exploration remains in the results.

| Provider / mode | Mean s | P95 s | Max s | Answered / requests | Timeouts | 5 s misses |
|---|---:|---:|---:|---:|---:|---:|
| gemini / previous | 0.486 | 1.087 | 2.482 | 12/12 | 0 | 0/24 |
| gemini / bounded | 0.487 | 1.511 | 1.765 | 10/10 | 0 | 0/24 |
| openrouter / previous | 0.524 | 2.094 | 2.466 | 3/8 | 0 | 0/24 |
| openrouter / bounded | 1.222 | 3.620 | 3.621 | 5/10 | 5 | 0/24 |

The final provider pilot uses fresh seeds 1980/1981 and five-second wall-clock observation arrivals. The bounded path reuses one idle worker and its HTTPS session after completed calls; its 3.8-second provider wait budget includes startup, pacing and cancellation. API responses can still time out; local fallbacks are explicit. A lower call count or bounded tail does not guarantee lower mean time or faster provider servers. Raw diagnostics are retained separately.

## Demo and reproduction

1. Open **Rule demo**. Choose Gemini or OpenRouter, select a seed, then play or step through the saved actual suggestions.
2. Inspect observed demand, provider proposal, guard decision, installed output/meter rule, previous expiry and measured outcome.
3. Select **120-window memory learning demo**. Later repeated contexts show supported parameter selection, with earlier episode IDs.
4. Use **Run offline experiment** for fresh generated traffic. This makes no API request.

```powershell
.\run.ps1 gemini
.\run.ps1 openrouter
.\.venv\Scripts\python.exe -m eval.run_v4_latency --provider gemini --realtime --seeds 1980 1981 --out-dir output/benchmarks/v4/latency_gemini_pooled
.\.venv\Scripts\python.exe -m eval.run_v4_latency --provider openrouter --realtime --seeds 1980 1981 --out-dir output/benchmarks/v4/latency_openrouter_pooled
.\.venv\Scripts\python.exe -m eval.build_rule_demo
```

Live commands use provider quota. Use a distinct output folder when preserving a run. Provider catalog availability and free quota can change; only the free router or `:free` IDs are used on OpenRouter.

## Evidence and editable submission

- [PNG/SVG figures and manifest](output/benchmarks/v4/figures/) and [17-page graph atlas](output/submission/SELF_X_Benchmark_Atlas.pdf)
- [Synthetic aggregate traffic CSV](output/benchmarks/v4/traffic/simulated_netflow.csv), hashed JSON traces, metrics CSV and summary JSON
- [Editable report](output/submission/SELF_X_Report.docx), [PDF report](output/submission/SELF_X_Report.pdf), [editable slides](output/submission/SELF_X_Presentation.pptx) and [slide PDF](output/submission/SELF_X_Presentation.pdf)
- [Source/evidence ZIP](output/submission/SELF_X_Submission.zip), SHA256SUMS.txt, runtime/browser verification JSON

`scripts/build_v4_artifacts.py` rebuilds graphs, atlas and report with authoring dependencies. `scripts/build_v4_presentation.mjs` authors native editable slides in Artifact Session. `scripts/finalize_v4_presentation.mjs` checks geometry/package integrity and embeds chart workbooks. Native Word/PowerPoint exports produce the PDFs.

## Limits and preserved work

This Windows validation does not contact physical switches, generate packet captures, or certify Linux Mininet/Ryu. The original Linux testbed sources are retained separately. The model has two fixed-capacity paths and constant demand within each window; it does not model TCP. No production SLA or broad LLM-quality benefit is established. [v3](docs/BENCHMARKS_V3.md) and [v2](docs/BENCHMARKS.md) raw evidence remain under their original version folders; previous canonical deliverables are in output/history/v3.
