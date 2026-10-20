# Complete simulated rule-change demo

Run `.\run.ps1 dashboard -Port 8766`, then open http://127.0.0.1:8766/#rule-demo.

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
