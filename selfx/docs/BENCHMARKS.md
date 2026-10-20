# Enhanced benchmarks and visualization guide

The expanded suite evaluates 57,600 analytical simulation windows: six scenarios, ten paired seeds (1740 to 1749), eight controllers and 120 five-second windows per condition. It runs in the isolated `.venv`. This is accelerated fluid simulation; no captured packet or physical-network dataset is claimed.

## Controllers and ablations

| ID | Method |
| --- | --- |
| A0 | Static primary path |
| B1 | Feasible least-loaded path |
| B2 | Stable flow-hash ECMP-style choice followed by the common safety gate |
| A1 | Original threshold controller without memory |
| A2 | Original reward-pruned similar-state memory |
| H1 | Guarded threshold controller without memory |
| A3 | The same guard plus balanced recent, positive and negative episode memory |
| O1 | Privileged myopic model reference selecting immediate reward among feasible actions |

A3 checks retrieved action feasibility using current demand and rebuilds parameters. It never evaluates candidate simulator outcomes or reads future demand. H1 shares A3's healthy-load guard, so A3 versus H1 isolates added memory. O1 knows the simulator and is not a deployable baseline or guaranteed long-horizon upper bound. The original A2 remains visible.

## Scenarios

Mixed traffic, primary flash crowds, a busy alternate path, a halfway distribution shift, persistent dual overload and a light-load negative control all use reproducible demand bytes. Memory and queues reset for every scenario, seed and controller. Each trace has a SHA256 hash in the summary. Every controller receives the same trace for its scenario and seed.

## Metrics and intervals

Mean modeled window delay, delivered goodput, total loss including meter drops, reward, proposal vetoes and computation time are recorded per window. P95 is over modeled mean-window delays, not individual packets. Mean loss and pooled dropped-volume loss are distinct statistics. Computation timing excludes a final batched memory flush; this makes offline loop timing comparable across controllers.

Intervals use 4,000 bootstrap resamples of the ten seed-level estimates, with RNG seed 4099. Pairwise effects resample paired per-seed differences. Comparisons are exploratory with no multiplicity correction. Intervals are not computed by treating 1,200 windows as independent trials.

## Findings

A3 eliminates infeasible retrieved proposals in this suite; the original A2 has 134 vetoes. Added memory does not consistently beat H1. In mixed load, A3 minus H1 modeled delay is approximately +0.473 ms, and in flash demand approximately +0.611 ms. Other scenario means match. The guard improves proposal validity; a general learning-performance advantage is not established.

## Graph navigation

| Figure | Question answered |
| --- | --- |
| Scenario delay matrix | How do all eight controllers behave across the six scenarios? |
| Scenario seed intervals | How much do results vary across seeds? |
| Paired memory effects | What changes when memory is added after the same guard? |
| Empirical distributions | How are modeled window delays and losses distributed? |
| Metric tradeoffs | Does lower delay come with loss or goodput costs? |
| Actions and vetoes | Which proposals are rejected and which actions are installed? |
| Queue shift heatmap | How do path queues change in one illustrative shift trace? |
| Control overhead | How much local computation does each control loop require? |

All figures are exported as PNG and SVG under `output/figures/benchmarks`. The eight-page PDF atlas is `output/submission/SELF_X_Benchmark_Atlas.pdf`. Editable numeric comparison charts and tables also appear in the PowerPoint. The report appends the full protocol and findings.

## Execute and inspect

```powershell
.\setup.ps1
.\run.ps1 all
.\run.ps1 dashboard
```

`.env` holds credentials and `.venv` holds Python packages. Keys must not be placed in the dashboard or submitted files. `run.ps1` always selects the project's virtual environment. Use `run.ps1 benchmark` for just the expanded suite. `output/runtime_validation.json` records the actual interpreter, test results and complete run status. Raw benchmark rows are in `output/benchmarks/v2/metrics.csv`.

## External approach references

RFC 2992 describes equal-cost multipath hash-threshold selection: https://www.rfc-editor.org/rfc/rfc2992 . The B2 abstraction adopts stable equal-region hashing, with this project's separate safety constraint; it is not a complete RFC implementation. RFC 7011 defines actual IPFIX flow export: https://www.rfc-editor.org/rfc/rfc7011 . This project creates synthetic flow demand records and does not emit wire-format IPFIX. Accessed 20 October 2026.
