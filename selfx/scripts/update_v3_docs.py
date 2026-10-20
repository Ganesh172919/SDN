"""Keep the current navigation and measured protocol in sync with saved evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'output/benchmarks/v3'

def main():
    d=json.loads((B/'chart_data.json').read_text());s=d['primary'];g=d['live']['groups']
    lines=['# Current adaptive memory and latency benchmarks','',
        'The project goal is to evaluate whether a single SDN controller can reuse its own state-action-outcome episodes to manage repeated congestion. The website is a local review and replay dashboard. All network traffic and performance below are synthetic fluid-model values; provider requests are real.','',
        '## Evidence sets','',
        '| Set | Design | Interpretation |','|---|---|---|',
        '| Primary | 8 scenarios, 10 held-out seeds (1760-1769), 120 windows, 9 controllers; 86,400 windows | Main paired workload comparison |',
        '| Memory sensitivity | 4 near-capacity overload levels, 10 seeds (1780-1789), 120 windows, 4 controllers; 19,200 windows | Post-hoc constructed mechanism test; excluded from primary average |',
        '| Fresh Gemini pilot | 2 seeds (1790, 1791), 12 cycles, 3 modes; 72 network cycles | Descriptive integration and whole-system latency |',
        '| Initial Gemini pilot | 1770 and 1771 | Preserved prompt-arithmetic diagnostic; not the final pilot |',
        f"| Free models | {d['free_models']['ok']} of {d['free_models']['checked']} discovered zero-price model IDs returned valid compact JSON | Availability only, not network quality |",'',
        'Memory rules were developed on seeds 1740 and 1741. Tests caught a support/retention mismatch: at least three neighbors requires retaining more than two observations per action/context cell. Four are now retained, with a 96-episode overall bound. No held-out outcome-driven hyperparameter search was performed.','',
        '## Adaptive memory','',
        '`agent/adaptive_memory.py` preserves capacity-scaled demand magnitude, three capacity margins and both queues. Retrieval matches the congestion/feasibility regime, uses a local distance caliper, separates evidence per action and weights recent nearby observations. At least three earlier completed observations are required. Repeated harmful-action evidence can choose no-op. Current parameters are rebuilt and independently validated. The local spread margin is a decision heuristic, not a calibrated statistical confidence interval.','',
        'A4 never evaluates candidate simulator outcomes to select an action. The measured reward compares the installed outcome with the original same-window no-op reference. No LLM weights or embedding neural weights are trained.','',
        '## Primary measured averages','',
        '| ID | Mean delay ms | Goodput Mbps | Mean total loss % | Safety vetoes |','|---|---:|---:|---:|---:|']
    for c,v in d['overall'].items():lines.append(f"| {c} | {v['latency_ms']:.3f} | {v['throughput_kbps']/1000:.3f} | {v['loss_pct']:.3f} | {v['vetoes']} |")
    lines+=['', 'A4 matches H1 in all primary installed actions and network metrics. It avoids A3 regressions on mixed, flash and volatile demand; it does not establish an additional benefit over the common guard. In the separate near-capacity diagnostic, A4 learns to avoid repeated harmful throttling, improving reward and loss while increasing queue delay. This constructed mechanism result is not pooled into the primary average.','',
        'Seed means define inference. Paired differences use a 4,000-draw fixed-RNG percentile bootstrap and 95% intervals. Results are exploratory with no multiple-comparison correction. Network P95 is over modeled window means, not individual packet delays.','',
        '## Actual provider timing','',
        '| Mode | Mean full cycle s | P95 full cycle s | API requests | Five-second misses |','|---|---:|---:|---:|---:|']
    for mode in ('legacy','compact','hybrid'):
        v=g[mode];lines.append(f"| {mode} | {v['control_elapsed_ms']/1000:.3f} | {v['p95_control_ms']/1000:.3f} | {v['api_calls']} | {v['deadline_misses']}/24 |")
    lines+=['',f"Compact mean wall time fell {d['latency_reduction_pct']['compact']:.1f}%; hybrid fell {d['latency_reduction_pct']['hybrid']:.1f}%. The hybrid pilot used {g['hybrid']['origins'].get('api_cache',0)} cache hits and {g['hybrid']['origins'].get('healthy_bypass',0)} healthy bypasses. It did not produce a production deadline guarantee. Mean simulated loss was {g['legacy']['loss_pct']:.3f}% for legacy and {g['hybrid']['loss_pct']:.3f}% for hybrid, so control quality is not uniformly better.",'',
        'Compact mode removes the second API reflection call, pools HTTP connections, requests a shorter action choice and supplies computed current totals/feasibility flags. Hybrid adds a 64-entry exact-context cache, a 12-window TTL and supported local memory. Cache keys include demand, queues, capacity, buffer and observed ports; flow parameters are rebuilt and revalidated. Local measured reflection stays inside full-cycle timing. Pacing and HTTP/network/service time are separately recorded. Reduced call count is not proof that the provider server itself got faster.','',
        'The normal `eval.run_simulation` runner now includes A4. Offline A4 uses the adaptive policy; API A4 uses the hybrid fast controller. `output/experiments/fast_gemini_demo` records a separate normal-runner integration check with 3 actual API decisions, 3 healthy bypasses and no API reflection request.','',
        '## Run and reproduce','',r'```powershell',r'.\run.ps1 all',r'.\run.ps1 latency',r'.\.venv\Scripts\python.exe -m eval.run_memory_sensitivity',r'.\.venv\Scripts\python.exe -m scripts.export_simulated_netflow',r'.\.venv\Scripts\python.exe -m scripts.sweep_free_models --profile compact --out output/benchmarks/v3/free_model_checks.json',r'.\run.ps1 dashboard -Port 8766','```','',
        'The all command runs tests, the complete five-controller portable experiment and the primary benchmark in this folder’s .venv. Live commands consume available provider quota. `.env` stores keys and is excluded from the ZIP. Re-running an experiment resets its local memories. Use a distinct output directory if preserving an earlier run.','',
        'Authoring uses the bundled document runtime and Artifact Session. `python -m scripts.build_v3_artifacts` regenerates the report and figures when its authoring dependencies are available. `scripts/build_v3_presentation.mjs` builds the editable deck in Artifact Session; `scripts/finalize_v3_presentation.mjs` validates native tables/charts and embeds literal Excel chart data. Final PDFs are exported from the actual Word and PowerPoint files.','',
        '## Dedicated graph directory','',
        'Every current PNG and SVG is in [output/benchmarks/v3/figures](../output/benchmarks/v3/figures/). The manifest records source-data hashes. The 15-page PDF atlas contains all fifteen figures. Earlier v2 results remain under output/benchmarks/v2.','']
    for f in json.loads((B/'figures/manifest.json').read_text())['figures']:lines.append(f"- [{f['title']}](../{f['png']})")
    lines+=['','The 9,600 synthetic aggregate flow records are [traffic/simulated_netflow.csv](../output/benchmarks/v3/traffic/simulated_netflow.csv). These are NetFlow-style table records, not captured packets or RFC 7011 IPFIX messages.','',
        '## Limits','',
        'The simulator has two fixed-capacity paths, finite queues and a hand-designed numeric context. It does not model TCP, packet scheduling, actual flow export or deployed OpenFlow control-plane latency. Linux Mininet/Ryu needs separate endpoint validation. No SLA, stability or broad LLM-quality guarantee is established. The API sample contains only two independent seeds; no inference treats its individual windows as independent seed replications.']
    (ROOT/'docs/BENCHMARKS_V3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    readme=ROOT/'README.md';r=readme.read_text(encoding='utf-8')
    r=r.replace('# SELF X SDN control with state embedding memory','# SELF X SDN control with adaptive episodic memory')
    r=r.replace('[Experimental protocol](docs/EXPERIMENTS.md)','[Current benchmarks](docs/BENCHMARKS_V3.md) | [Original protocol](docs/EXPERIMENTS.md)')
    r=r.replace('# offline 5 seeds x 120 windows x 4 controllers','# offline 5 seeds x 120 windows x 5 controllers including A4')
    r=r.replace('Provider failures become visible safe no-op actions.','A1/A2 failures become visible no-op actions; A4 uses an explicitly labeled validated heuristic fallback.')
    r=r.replace('## Expanded benchmarks and graphs','## Historical v2 benchmark reference')
    old='See [benchmark protocol and graph guide](docs/BENCHMARKS.md). Run `.\\run.ps1 all` for tests, the complete portable experiment and 57,600 scenario benchmark windows. Run `.\\run.ps1 benchmark` for the suite alone. The dashboard adds scenario and metric selection with seed confidence intervals. Eight PNG/SVG figure pairs and an eight-page PDF atlas accompany the updated report and presentation.'
    r=r.replace(old,'The previous 57,600-window, six-scenario/eight-controller study remains in `output/benchmarks/v2`. Its historical protocol is in [BENCHMARKS.md](docs/BENCHMARKS.md). Current run commands use v3 and current submission files contain the v3 results.')
    current=f"""\n## Current revision 3\n\nSee [the full benchmark guide](docs/BENCHMARKS_V3.md), [all 15 PNG/SVG graphs](output/benchmarks/v3/figures/) and [synthetic NetFlow-style traffic](output/benchmarks/v3/traffic/simulated_netflow.csv). The current primary suite has 86,400 windows. The separate post-hoc memory sensitivity diagnostic has 19,200 windows. A4 is included in normal experiments and dashboard replay.\n\nRun `.\\run.ps1 all` for tests, the complete offline project and primary benchmarks. Run `.\\run.ps1 latency` for the live Gemini three-mode comparison. The measured hybrid mean cycle changed from {g['legacy']['control_elapsed_ms']/1000:.3f} s to {g['hybrid']['control_elapsed_ms']/1000:.3f} s ({d['latency_reduction_pct']['hybrid']:.1f}% reduction), with {g['hybrid']['deadline_misses']}/24 five-second misses. All provider work and local reuse have distinct provenance. A4 matches guard-only H1 in the primary suite; the targeted diagnostic demonstrates a loss/reward benefit with increased modeled delay.\n\nFor a normal fast API demo with only A0 and A4:\n\n```powershell\n.\\.venv\\Scripts\\python.exe -m eval.run_simulation --provider gemini --conditions A0 A4 --cycles 12 --seeds 1792 --out-dir output/experiments/custom_fast\n```\n\nThe existing `.env` is configured and ignored. `.venv` is the isolated Python environment. Final editable reports, slides, PDFs and the verified ZIP are in [output/submission](output/submission/).\n"""
    marker='\n## Current revision 3'
    if marker in r:r=r.split(marker)[0]
    readme.write_text(r.rstrip()+'\n'+current,encoding='utf-8')
    architecture=ROOT/'docs/ARCHITECTURE.md';a=architecture.read_text(encoding='utf-8')
    marker='\n## Current adaptive memory and fast control'
    if marker in a:a=a.split(marker)[0]
    a+=r'''
## Current adaptive memory and fast control

`eval/run_simulation.py` now includes A4 in its normal five-controller run. Offline A4 calls `agent/adaptive_memory.py`; provider A4 calls `agent/fast_control.py`. The legacy A1/A2 branch remains reproducible. `eval/run_adaptive_benchmarks.py` runs the primary held-out eight-scenario suite. `eval/run_memory_sensitivity.py` runs the separate constructed mechanism diagnostic. `eval/run_latency_benchmark.py` measures all provider and local work for the three latency modes.

```mermaid
flowchart TD
    T[Generated NetFlow-style demand and current queues] --> E[Capacity-scaled context and action-local retrieval]
    E --> H{Healthy zero-queue state?}
    H -- Yes --> N[Explicit local no-op bypass]
    H -- No --> C{Exact validated cache hit?}
    C -- Yes --> R[Rebuild current flow parameters]
    C -- No --> M{Supported local memory decision?}
    M -- Yes --> R
    M -- No --> A[One compact API action choice]
    A --> R
    R --> V[Independent deterministic action validation]
    N --> V
    V --> O[Commit one simulated five-second outcome]
    O --> F[Local measured reflection and bounded episode update]
    F --> E
    O --> P[CSV and provider audit]
    P --> G[15 PNG and SVG graphs plus PDF atlas]
    P --> D[Editable DOCX and PPTX with native charts]
```

Current data lives in `output/benchmarks/v3`: primary CSV/traffic hashes, `traffic/simulated_netflow.csv`, `latency_gemini/`, preserved `latency_gemini_initial/`, `memory_sensitivity/`, `free_model_checks.json`, `figures/` and `chart_data.json`. The dashboard reads this version and the full portable run `output/experiments/venv_v3`. See [the current benchmark protocol](BENCHMARKS_V3.md) for evidence boundaries and actual results.
'''
    architecture.write_text(a,encoding='utf-8')
    (ROOT/'docs/ARCHITECTURE.Rmd').write_text("---\ntitle: 'SELF X architecture and project navigation'\noutput:\n  html_document:\n    toc: true\n---\n\n"+a,encoding='utf-8')
    (ROOT/'output/benchmarks/README.md').write_text('# Benchmark navigation\n\n- v2: preserved prior six-scenario/eight-controller study.\n- v3: current eight-scenario/nine-controller study, separate memory sensitivity, fresh Gemini pilot, preserved initial prompt diagnostic, all free-model checks, synthetic NetFlow-style CSV, and a dedicated figures folder with 15 PNG/SVG pairs.\n\nThe primary suite and post-hoc memory diagnostic remain separate. See ../../docs/BENCHMARKS_V3.md for commands and limitations.\n',encoding='utf-8')
    print('Updated current protocol, README, architecture and R Markdown navigation')

if __name__=='__main__':main()
