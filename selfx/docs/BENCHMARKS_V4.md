# Revision 4 benchmark protocol and actual results

## Purpose

Improve loss and bounded control waiting while separating better meter rules from the additional effect of episodic memory. Network values are synthetic fluid-model outcomes; authenticated API calls are real.

## Frozen network policy

Development seeds: 1880/1881. Fresh held-out seeds: 1900–1909. Eight scenarios, 120 windows, nine controllers, 86,400 controller windows. Each condition begins with empty queues and memory and sees the same demand. The path capacity is 10 Mbps, buffer 0.5 Mbit and interval 5 seconds. Prior queues carry over.

A4 retains at most 128 parameter-conditioned episodes, six per action/parameter/context cell. Three prior neighbors per candidate are needed for supported choice. Headroom candidates are 0, 0.1 and 0.3 Mbps. Equivalent clipped caps are one candidate. No candidate simulator outcome is queried by A4. The loss-aware meter never reduces a flow by more than 20%; existing target, port, utilization and minimum-rate checks are unchanged.

H1 uses the previous fixed 80%-of-flow meter. V3 preserves the previous A4 policy. H2 shares the improved meter and uses fixed 0.1 Mbps headroom without memory. O2 chooses among the same candidate set using privileged current outcomes and is not a deployable or long-horizon bound.

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

A4 improves loss/reward over H1 while modeled delay increases. H2 has slightly higher reward than A4; these data do not establish extra reward benefit from memory. The complete learning mechanism is demonstrated separately, with exploration retained in performance averages.

## Statistics

Seed means are the unit of inference. Paired seed percentile bootstrap: 4,000 draws, RNG 4099, 95% intervals. Comparisons are exploratory without multiplicity adjustment. Window P95 is not packet RTT. Total loss includes meter drops; pooled volume loss differs from mean window loss. The figure manifest hashes every source used by the graphs.

## Real provider pilots and retained diagnostics

- Accelerated admission diagnostic: seeds 1920/1921, `latency_gemini/` and `latency_openrouter/`.
- Initial scheduled diagnostic: seeds 1940/1941, `latency_*_scheduled/`; exposed avoidable healthy and fallback repeat calls.
- Cache/bypass diagnostic: seeds 1960/1961, `latency_*_final/`; process startup remained visible overhead.
- Final pooled-worker pilot: seeds 1980/1981, `latency_*_pooled/`. Two modes, 24 windows per mode/provider; observations arrive every five wall-clock seconds. Mode order reverses on the second seed.

| Provider / mode | Mean s | P95 s | Max s | Answered / requests | Timeouts | 5 s misses |
|---|---:|---:|---:|---:|---:|---:|
| gemini / previous | 0.486 | 1.087 | 2.482 | 12/12 | 0 | 0/24 |
| gemini / bounded | 0.487 | 1.511 | 1.765 | 10/10 | 0 | 0/24 |
| openrouter / previous | 0.524 | 2.094 | 2.466 | 3/8 | 0 | 0/24 |
| openrouter / bounded | 1.222 | 3.620 | 3.621 | 5/10 | 5 | 0/24 |

The final pooled worker is idle only between completed requests and reuses the HTTPS session. First startup, pacing, waits, IPC, timeout termination/join, validation, outcome, reflection and memory update are inside control timing. The last cycle includes worker shutdown. Observation scheduling idle time is separately recorded. No request is hidden outside timing. A local timeout cannot undo remote generation already accepted by a server. Provider service varies over time and there are only two independent seeds.

Origins distinguish fresh API, validated API cache, validated local fallback cache, healthy bypass, supported memory, timeout, admission/provider failure and rejected suggestion. A schema-valid answer may fail rule validation, so success counts and installed API-action windows can differ. All failures and cold-start windows stay in metrics.

## Evidence paths

`output/benchmarks/v4/metrics.csv`, `summary.json`, `traffic_*.json`, `traffic/simulated_netflow.csv`, `chart_data.json`, `figures/manifest.json`, `latency_*_pooled/trace.jsonl`, `rule_expiry.json`, `rule_demo_offline/` and `free_model_checks.json`. All 17 graphs are PNG and SVG. The atlas, editable report and editable native-chart deck use these saved measurements. Old v2/v3 evidence is unchanged.

See [README](../README.md) for commands and [rule demo](RULE_DEMO.md) for interpretation. Catalog checks cover every discovered zero-price OpenRouter ID; this is availability, not control-quality ranking. Keys stay in ignored `.env`; artifacts and ZIP exclude credentials and `.venv`.
