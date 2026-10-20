# Current adaptive memory and latency benchmarks

The project goal is to evaluate whether a single SDN controller can reuse its own state-action-outcome episodes to manage repeated congestion. The website is a local review and replay dashboard. All network traffic and performance below are synthetic fluid-model values; provider requests are real.

## Evidence sets

| Set | Design | Interpretation |
|---|---|---|
| Primary | 8 scenarios, 10 held-out seeds (1760-1769), 120 windows, 9 controllers; 86,400 windows | Main paired workload comparison |
| Memory sensitivity | 4 near-capacity overload levels, 10 seeds (1780-1789), 120 windows, 4 controllers; 19,200 windows | Post-hoc constructed mechanism test; excluded from primary average |
| Fresh Gemini pilot | 2 seeds (1790, 1791), 12 cycles, 3 modes; 72 network cycles | Descriptive integration and whole-system latency |
| Initial Gemini pilot | 1770 and 1771 | Preserved prompt-arithmetic diagnostic; not the final pilot |
| Free models | 8 of 17 discovered zero-price model IDs returned valid compact JSON | Availability only, not network quality |

Memory rules were developed on seeds 1740 and 1741. Tests caught a support/retention mismatch: at least three neighbors requires retaining more than two observations per action/context cell. Four are now retained, with a 96-episode overall bound. No held-out outcome-driven hyperparameter search was performed.

## Adaptive memory

`agent/adaptive_memory.py` preserves capacity-scaled demand magnitude, three capacity margins and both queues. Retrieval matches the congestion/feasibility regime, uses a local distance caliper, separates evidence per action and weights recent nearby observations. At least three earlier completed observations are required. Repeated harmful-action evidence can choose no-op. Current parameters are rebuilt and independently validated. The local spread margin is a decision heuristic, not a calibrated statistical confidence interval.

A4 never evaluates candidate simulator outcomes to select an action. The measured reward compares the installed outcome with the original same-window no-op reference. No LLM weights or embedding neural weights are trained.

## Primary measured averages

| ID | Mean delay ms | Goodput Mbps | Mean total loss % | Safety vetoes |
|---|---:|---:|---:|---:|
| A0 | 26.003 | 12.904 | 8.162 | 0 |
| B1 | 20.611 | 13.058 | 6.986 | 0 |
| B2 | 23.227 | 12.983 | 7.561 | 2585 |
| A1 | 17.062 | 12.902 | 7.913 | 0 |
| A2 | 17.554 | 12.848 | 8.349 | 347 |
| H1 | 17.154 | 12.990 | 7.382 | 0 |
| A3 | 17.341 | 12.974 | 7.510 | 0 |
| O1 | 17.204 | 13.001 | 7.322 | 0 |
| A4 | 17.154 | 12.990 | 7.382 | 0 |

A4 matches H1 in all primary installed actions and network metrics. It avoids A3 regressions on mixed, flash and volatile demand; it does not establish an additional benefit over the common guard. In the separate near-capacity diagnostic, A4 learns to avoid repeated harmful throttling, improving reward and loss while increasing queue delay. This constructed mechanism result is not pooled into the primary average.

Seed means define inference. Paired differences use a 4,000-draw fixed-RNG percentile bootstrap and 95% intervals. Results are exploratory with no multiple-comparison correction. Network P95 is over modeled window means, not individual packet delays.

## Actual provider timing

| Mode | Mean full cycle s | P95 full cycle s | API requests | Five-second misses |
|---|---:|---:|---:|---:|
| legacy | 8.295 | 8.833 | 48 | 24/24 |
| compact | 4.189 | 4.564 | 24 | 0/24 |
| hybrid | 2.096 | 5.714 | 12 | 2/24 |

Compact mean wall time fell 49.5%; hybrid fell 74.7%. The hybrid pilot used 10 cache hits and 2 healthy bypasses. It did not produce a production deadline guarantee. Mean simulated loss was 6.986% for legacy and 7.470% for hybrid, so control quality is not uniformly better.

Compact mode removes the second API reflection call, pools HTTP connections, requests a shorter action choice and supplies computed current totals/feasibility flags. Hybrid adds a 64-entry exact-context cache, a 12-window TTL and supported local memory. Cache keys include demand, queues, capacity, buffer and observed ports; flow parameters are rebuilt and revalidated. Local measured reflection stays inside full-cycle timing. Pacing and HTTP/network/service time are separately recorded. Reduced call count is not proof that the provider server itself got faster.

The normal `eval.run_simulation` runner now includes A4. Offline A4 uses the adaptive policy; API A4 uses the hybrid fast controller. `output/experiments/fast_gemini_demo` records a separate normal-runner integration check with 3 actual API decisions, 3 healthy bypasses and no API reflection request.

## Run and reproduce

```powershell
.\run.ps1 all
.\run.ps1 latency
.\.venv\Scripts\python.exe -m eval.run_memory_sensitivity
.\.venv\Scripts\python.exe -m scripts.export_simulated_netflow
.\.venv\Scripts\python.exe -m scripts.sweep_free_models --profile compact --out output/benchmarks/v3/free_model_checks.json
.\run.ps1 dashboard -Port 8766
```

The all command runs tests, the complete five-controller portable experiment and the primary benchmark in this folder’s .venv. Live commands consume available provider quota. `.env` stores keys and is excluded from the ZIP. Re-running an experiment resets its local memories. Use a distinct output directory if preserving an earlier run.

Authoring uses the bundled document runtime and Artifact Session. `python -m scripts.build_v3_artifacts` regenerates the report and figures when its authoring dependencies are available. `scripts/build_v3_presentation.mjs` builds the editable deck in Artifact Session; `scripts/finalize_v3_presentation.mjs` validates native tables/charts and embeds literal Excel chart data. Final PDFs are exported from the actual Word and PowerPoint files.

## Dedicated graph directory

Every current PNG and SVG is in [output/benchmarks/v3/figures](../output/benchmarks/v3/figures/). The manifest records source-data hashes. The 15-page PDF atlas contains all fifteen figures. Earlier v2 results remain under output/benchmarks/v2.

- [Generated traffic used by every controller](../output\benchmarks\v3\figures\traffic_scenarios.png)
- [Held-out delay across eight traffic scenarios](../output\benchmarks\v3\figures\scenario_latency_matrix.png)
- [Adaptive memory compared with previous guarded memory](../output\benchmarks\v3\figures\paired_memory_effect.png)
- [The memory ablation after the same base guard](../output\benchmarks\v3\figures\guard_ablation.png)
- [Delay must be judged together with loss and goodput](../output\benchmarks\v3\figures\metric_tradeoffs.png)
- [Distributions over the measured simulation windows](../output\benchmarks\v3\figures\distribution_ecdf.png)
- [Action feasibility and installed behavior](../output\benchmarks\v3\figures\actions_and_vetoes.png)
- [Queue occupancy around the alternate-path traffic shift](../output\benchmarks\v3\figures\queue_shift_heatmap.png)
- [Measured control computation in the isolated virtual environment](../output\benchmarks\v3\figures\offline_control_overhead.png)
- [Actual Gemini control latency after the pipeline changes](../output\benchmarks\v3\figures\api_latency_compare.png)
- [Provider work and local reuse are counted separately](../output\benchmarks\v3\figures\api_call_origins.png)
- [Measured full-cycle latency by simulated traffic window](../output\benchmarks\v3\figures\api_timeline.png)
- [Compact free-model checks: 8/17 valid responses](../output\benchmarks\v3\figures\free_model_availability.png)
- [Targeted memory diagnostic near the capacity boundary](../output\benchmarks\v3\figures\memory_sensitivity.png)
- [Memory adapts after observed harmful throttling](../output\benchmarks\v3\figures\memory_learning.png)

The 9,600 synthetic aggregate flow records are [traffic/simulated_netflow.csv](../output/benchmarks/v3/traffic/simulated_netflow.csv). These are NetFlow-style table records, not captured packets or RFC 7011 IPFIX messages.

## Limits

The simulator has two fixed-capacity paths, finite queues and a hand-designed numeric context. It does not model TCP, packet scheduling, actual flow export or deployed OpenFlow control-plane latency. Linux Mininet/Ryu needs separate endpoint validation. No SLA, stability or broad LLM-quality guarantee is established. The API sample contains only two independent seeds; no inference treats its individual windows as independent seed replications.
