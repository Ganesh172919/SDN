"""Current navigation, architecture and demo instructions from actual v4 data."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'output/benchmarks/v4'

def main():
    d=json.loads((B/'chart_data.json').read_text(encoding='utf-8'));s=d['primary'];o=d['overall'];live=d['live']
    table=['| Controller | Delay ms | Goodput Mbps | Total loss % | Reward |','|---|---:|---:|---:|---:|']
    for c,v in o.items():table.append(f"| {c} | {v['latency_ms']:.3f} | {v['throughput_kbps']/1000:.3f} | {v['loss_pct']:.3f} | {v['reward']:.6f} |")
    api=['| Provider / mode | Mean s | P95 s | Max s | Answered / requests | Timeouts | 5 s misses |','|---|---:|---:|---:|---:|---:|---:|']
    for provider,run in live.items():
        for mode,g in run['groups'].items():api.append(f"| {provider} / {mode} | {g['control_elapsed_ms']/1000:.3f} | {g['p95_control_ms']/1000:.3f} | {g['max_control_ms']/1000:.3f} | {g['api_successes']}/{g['api_calls']} | {g['local_timeouts']} | {g['deadline_miss']}/{g['windows']} |")
    measured='\n'.join(table);timing='\n'.join(api)
    readme=f'''# SELF-X: loss-aware SDN control with episodic memory

SELF-X observes generated network traffic, retrieves completed local episodes, suggests a bounded action, validates it, installs a simulated rule and learns from the measured outcome. The website is a local review and replay dashboard. All network results are from a finite-buffer fluid model; Gemini and free OpenRouter requests are real.

[Project guide](docs/PROJECT_GUIDE.md) · [Current benchmarks](docs/BENCHMARKS_V4.md) · [Complete rule demo](docs/RULE_DEMO.md) · [Architecture](docs/ARCHITECTURE.md) · [R Markdown architecture](docs/ARCHITECTURE.Rmd) · [Submission](output/submission/)

## Run in the project environment

```powershell
.\\setup.ps1
.\\run.ps1 all
.\\run.ps1 dashboard -Port 8766
```

Open http://127.0.0.1:8766. The `all` command runs the complete tests, all five normal-runner controllers and the nine-controller/eight-scenario benchmark in `.venv`. `.env` is the ignored key/configuration file; `.venv` is the isolated Python environment. Both provider keys are configured locally. Keys are never part of the report, slides or ZIP.

## Current measured results

{measured}

The primary suite uses seeds 1900–1909, 120 windows, eight scenarios and nine controllers: 86,400 controller windows on 9,600 unique demand windows. A4 improves loss and reward over H1, with higher modeled delay. H2 shares the improved meter without memory and has slightly higher reward than A4. The gain over H1 cannot be attributed solely to memory. All cold-start exploration remains in the results.

{timing}

The final provider pilot uses fresh seeds 1980/1981 and five-second wall-clock observation arrivals. The bounded path reuses one idle worker and its HTTPS session after completed calls; its 3.8-second provider wait budget includes startup, pacing and cancellation. API responses can still time out; local fallbacks are explicit. A lower call count or bounded tail does not guarantee lower mean time or faster provider servers. Raw diagnostics are retained separately.

## Demo and reproduction

1. Open **Rule demo**. Choose Gemini or OpenRouter, select a seed, then play or step through the saved actual suggestions.
2. Inspect observed demand, provider proposal, guard decision, installed output/meter rule, previous expiry and measured outcome.
3. Select **120-window memory learning demo**. Later repeated contexts show supported parameter selection, with earlier episode IDs.
4. Use **Run offline experiment** for fresh generated traffic. This makes no API request.

```powershell
.\\run.ps1 gemini
.\\run.ps1 openrouter
.\\.venv\\Scripts\\python.exe -m eval.run_v4_latency --provider gemini --realtime --seeds 1980 1981 --out-dir output/benchmarks/v4/latency_gemini_pooled
.\\.venv\\Scripts\\python.exe -m eval.run_v4_latency --provider openrouter --realtime --seeds 1980 1981 --out-dir output/benchmarks/v4/latency_openrouter_pooled
.\\.venv\\Scripts\\python.exe -m eval.build_rule_demo
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
'''
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    protocol=f'''# Revision 4 benchmark protocol and actual results

## Purpose

Improve loss and bounded control waiting while separating better meter rules from the additional effect of episodic memory. Network values are synthetic fluid-model outcomes; authenticated API calls are real.

## Frozen network policy

Development seeds: 1880/1881. Fresh held-out seeds: 1900–1909. Eight scenarios, 120 windows, nine controllers, 86,400 controller windows. Each condition begins with empty queues and memory and sees the same demand. The path capacity is 10 Mbps, buffer 0.5 Mbit and interval 5 seconds. Prior queues carry over.

A4 retains at most 128 parameter-conditioned episodes, six per action/parameter/context cell. Three prior neighbors per candidate are needed for supported choice. Headroom candidates are 0, 0.1 and 0.3 Mbps. Equivalent clipped caps are one candidate. No candidate simulator outcome is queried by A4. The loss-aware meter never reduces a flow by more than 20%; existing target, port, utilization and minimum-rate checks are unchanged.

H1 uses the previous fixed 80%-of-flow meter. V3 preserves the previous A4 policy. H2 shares the improved meter and uses fixed 0.1 Mbps headroom without memory. O2 chooses among the same candidate set using privileged current outcomes and is not a deployable or long-horizon bound.

{measured}

A4 improves loss/reward over H1 while modeled delay increases. H2 has slightly higher reward than A4; these data do not establish extra reward benefit from memory. The complete learning mechanism is demonstrated separately, with exploration retained in performance averages.

## Statistics

Seed means are the unit of inference. Paired seed percentile bootstrap: 4,000 draws, RNG 4099, 95% intervals. Comparisons are exploratory without multiplicity adjustment. Window P95 is not packet RTT. Total loss includes meter drops; pooled volume loss differs from mean window loss. The figure manifest hashes every source used by the graphs.

## Real provider pilots and retained diagnostics

- Accelerated admission diagnostic: seeds 1920/1921, `latency_gemini/` and `latency_openrouter/`.
- Initial scheduled diagnostic: seeds 1940/1941, `latency_*_scheduled/`; exposed avoidable healthy and fallback repeat calls.
- Cache/bypass diagnostic: seeds 1960/1961, `latency_*_final/`; process startup remained visible overhead.
- Final pooled-worker pilot: seeds 1980/1981, `latency_*_pooled/`. Two modes, 24 windows per mode/provider; observations arrive every five wall-clock seconds. Mode order reverses on the second seed.

{timing}

The final pooled worker is idle only between completed requests and reuses the HTTPS session. First startup, pacing, waits, IPC, timeout termination/join, validation, outcome, reflection and memory update are inside control timing. The last cycle includes worker shutdown. Observation scheduling idle time is separately recorded. No request is hidden outside timing. A local timeout cannot undo remote generation already accepted by a server. Provider service varies over time and there are only two independent seeds.

Origins distinguish fresh API, validated API cache, validated local fallback cache, healthy bypass, supported memory, timeout, admission/provider failure and rejected suggestion. A schema-valid answer may fail rule validation, so success counts and installed API-action windows can differ. All failures and cold-start windows stay in metrics.

## Evidence paths

`output/benchmarks/v4/metrics.csv`, `summary.json`, `traffic_*.json`, `traffic/simulated_netflow.csv`, `chart_data.json`, `figures/manifest.json`, `latency_*_pooled/trace.jsonl`, `rule_expiry.json`, `rule_demo_offline/` and `free_model_checks.json`. All 17 graphs are PNG and SVG. The atlas, editable report and editable native-chart deck use these saved measurements. Old v2/v3 evidence is unchanged.

See [README](../README.md) for commands and [rule demo](RULE_DEMO.md) for interpretation. Catalog checks cover every discovered zero-price OpenRouter ID; this is availability, not control-quality ranking. Keys stay in ignored `.env`; artifacts and ZIP exclude credentials and `.venv`.
'''
    (ROOT/'docs/BENCHMARKS_V4.md').write_text(protocol,encoding='utf-8')
    demo='''# Complete simulated rule-change demo

Run `.\\run.ps1 dashboard -Port 8766`, then open http://127.0.0.1:8766/#rule-demo.

## What to show

1. Select Gemini and seed 1980. Step from a healthy window to the congested window. The saved real model proposal is shown verbatim; the effective path changes from primary port 2 to alternate port 3 when validated.
2. Advance to alternate-busy demand. The controller can install a capacity-aware meter on the exact flow, with OUTPUT 2. Compare admitted cap, deliberate drops, overflow, goodput and modeled queue delay.
3. Inspect **Install and expire**. An ADD uses cookie, priority 100, exact IPv4 match and hard_timeout 5 seconds. The prior rule expires at the next virtual window. Healthy demand returns to default port 2. Final expiry leaves no active intervention rule.
4. Switch to OpenRouter. Actual free-router suggestions and timed-out/unavailable calls are distinct. A missing answer is shown as a local fallback; it is not an invented suggestion.
5. Select the 120-window offline learning demo. Early rate interventions explore 0, 0.1 and 0.3 Mbps headroom. Later repeated contexts use at least three matching prior observations per parameter. Inspect earlier cycle IDs and parameter evidence in the complete audit. It contains 15 exploration, 45 supported memory and 60 local-rule windows.

## Raw suggestion versus installed decision

Every saved record has current demand and queues, provider request audit, optional raw suggestion, local recommendation, guard result, installed decision, rule instructions, expiry, same-state no-op comparison and measured outcome. Provider reasoning never bypasses the independent guard.

The preserved initial scheduled Gemini diagnostic, seed 1940 cycle 4, contains a reroute suggestion that would put the alternate link at approximately 140.9% utilization. The 90% validator rejects it and installs the local meter. This is a useful negative example of why suggestions and rule installation are separate.

`api_cache` means a previously validated API action. `local_rule_cache` means a previously validated local fallback. Neither is a fresh API response. `deadline_fallback` ends local waiting and installs the deterministic local rule. Request timeouts and deferrals remain visible in the provider table and raw audit.

## Model boundary

The rule table and traffic are simulated. No Ryu endpoint, OVS bridge, physical switch, packet capture or external network is changed. Real provider calls demonstrate integration, while the isolated offline benchmark evaluates network policies. Replay itself sends no API request. The matched H2 comparison shows that a working learning mechanism does not establish a reward gain over a strong no-memory policy.

Sources: `agent/rule_demo.py`, `agent/bounded_control.py`, `agent/loss_aware_memory.py`, `eval/run_v4_latency.py`, `eval/build_rule_demo.py`, `web/rule-demo.js`. Evidence: `output/benchmarks/v4/latency_gemini_pooled/`, `latency_openrouter_pooled/`, `rule_demo_offline/`, and the preserved scheduled diagnostic folders.
'''
    (ROOT/'docs/RULE_DEMO.md').write_text(demo,encoding='utf-8')
    architecture='''# SELF-X architecture and navigation

## Goal and execution boundary

Observe generated traffic, retrieve completed experiences, propose an action, validate a bounded rule, measure and store feedback. All code, traffic and outputs are inside selfx. The validated Windows backend is a two-path finite-buffer fluid model. Actual Gemini/free OpenRouter calls supply suggestions; the local rule table is simulated.

## Entry points

| Entry | Purpose |
|---|---|
| setup.ps1 | Create isolated .venv and install project dependencies |
| run.ps1 all | Tests, full normal project experiment and primary benchmarks |
| run.ps1 dashboard -Port 8766 | Loopback website and saved rule replay |
| eval/run_simulation.py | Five-controller normal runner, offline or named provider |
| eval/run_v4_benchmarks.py | Eight-scenario/nine-controller paired network evaluation |
| eval/run_v4_latency.py | Real API timing, rule lifecycle, traffic schedule |
| eval/build_rule_demo.py | 120-window exploration-to-memory demonstration |
| scripts/build_v4_artifacts.py | Graphs, editable report, atlas and chart data |
| scripts/build_v4_presentation.mjs | Editable native charts/tables in Artifact Session |
| scripts/verify_v4_submission.py | Data, artifact, browser and credential checks; ZIP |

## Complete flow

```mermaid
flowchart TD
  T[Seeded demand JSON / aggregate flow CSV] --> N[FluidNetwork: persistent queues]
  N --> S[Current rates, capacities, queues and flow match]
  S --> M[LossAwareMemory: context + action + meter parameter]
  M --> L[Current local capacity-aware recommendation]
  L --> C{Healthy / supported memory / exact cache?}
  C -->|yes| V[Independent rule validator]
  C -->|no| P[DeadlineProvider: admit, pooled worker, compact real API call]
  P -->|valid response| V
  P -->|timeout / unavailable / deferred| F[Explicit local fallback]
  F --> V
  V -->|rejected suggestion| F
  V -->|allowed| R[Simulated OpenFlow rule table: ADD + 5 s expiry]
  R --> O[Fluid outcome: delivery, queues, overflow, meter loss]
  O --> W[Same-state no-op-relative reward and local reflection]
  W --> M
  R --> A[Full rule / suggestion / expiry audit]
  O --> A
  P --> A
  A --> D[Local dashboard and rule replay]
  A --> B[Raw CSV/JSON -> hashes -> PNG/SVG -> DOCX/PPTX -> native PDFs]
```

## Topology and rule behavior

Primary: s1 port 2 → s2 → s4. Alternate: s1 port 3 → s3 → s4. Each path: 10 Mbps and 0.5 Mbit buffer. One elephant begins on primary each five-second window. Known flow match: in_port=1, eth_type=2048, ipv4_dst=10.0.0.8. A reroute outputs port 3; a meter uses METER plus OUTPUT 2. Rules have priority 100 and hard_timeout=5. At the next virtual observation the previous intervention expires; final expiry restores default forwarding and no active intervention.

## Memory and attribution

Capacity-scaled demand, three feasibility margins and queues retain magnitude. Only completed cycles train the 128-episode memory. Meter candidates have 0/0.1/0.3 Mbps headroom, clipped to unchanged safety limits; three prior observations per candidate are needed for supported selection. Context vectors are cached and retention is diversified by action, parameter and regime. H2 has the same meter without memory; H1 has the old fixed 80% cap. The primary suite improves on H1 loss/reward, but does not establish extra reward benefit over H2.

## Provider and filesystem boundary

Keys load from ignored .env; execution uses .venv. Only configured provider endpoints receive generated traffic summaries. OpenRouter permits the free router or :free IDs. A 3.8-second parent wait budget includes pacing, worker startup, IPC and termination/join. Completed requests leave an idle reusable HTTPS worker; timeouts terminate it, and final-cycle cleanup is measured. No pending API work is moved outside timing. Provider responses and local cache/fallback origins remain distinct.

The dashboard binds loopback and serves a fixed allowlist. /api/rule-demo accepts gemini, openrouter or offline and returns saved bounded records. Replay sends no new API request. /api/run is same-origin guarded and creates bounded offline experiments. No arbitrary project files or keys are served.

## Data lineage and artifacts

Current raw data: output/benchmarks/v4. Primary seeds 1900–1909; final provider seeds 1980/1981. Diagnostics 1920/1921, 1940/1941 and 1960/1961 are retained separately. Primary traffic has SHA256 hashes and 9,600 aggregate CSV records. Graph manifest hashes CSV, JSON and runtime sources. Native DOCX and PPTX remain editable; actual Word/PowerPoint export creates their PDFs. The 17-page atlas includes every current graph. Verification produces output/verification.json and a credential-free source/evidence ZIP. Old v2/v3 evidence is preserved.

See [benchmark protocol](BENCHMARKS_V4.md), [rule demo](RULE_DEMO.md) and [README](../README.md) for results and commands. The original Linux testbed remains a separate adapter requiring independent packet/network validation.
'''
    (ROOT/'docs/ARCHITECTURE.md').write_text(architecture,encoding='utf-8')
    (ROOT/'docs/ARCHITECTURE.Rmd').write_text('---\ntitle: "SELF-X architecture and project navigation"\noutput:\n  html_document:\n    toc: true\n    toc_depth: 3\n---\n\n'+architecture,encoding='utf-8')
    (ROOT/'output/benchmarks/README.md').write_text('# Benchmark navigation\n\nCurrent: [v4 protocol](../../docs/BENCHMARKS_V4.md), [graphs](v4/figures/), [raw results](v4/), [rule demo](../../docs/RULE_DEMO.md). V4 contains primary, actual provider pilots, preserved development diagnostics and the offline learning replay. All network values are simulated.\n\nHistorical v3 and v2 folders remain unchanged. Canonical submission files contain revision 4.\n',encoding='utf-8')
    guide=ROOT/'docs/PROJECT_GUIDE.md';text=guide.read_text(encoding='utf-8');heading='\n## Revision 4 entry points\n';text=text.split(heading)[0]+heading+'\nSee [the current README](../README.md), [benchmark protocol](BENCHMARKS_V4.md), [complete rule replay](RULE_DEMO.md) and [architecture/R Markdown](ARCHITECTURE.Rmd). The current A4 uses parameter-conditioned memory and bounded pooled provider calls. The original sections below describe the project motivation; current measurements are in BENCHMARKS_V4.md.\n';guide.write_text(text,encoding='utf-8')
    print('Updated current README, benchmark protocol, rule-demo guide and Markdown/Rmd architecture.')

if __name__=='__main__':main()
