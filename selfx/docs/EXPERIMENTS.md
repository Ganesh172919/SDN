# Experiment design and reproducibility

## Conditions

| ID | Portable offline run | API pilot |
| --- | --- | --- |
| A0 | Static primary path | Same static primary path |
| B1 | Greedy feasible least-loaded route | Same deterministic baseline |
| A1 | Threshold controller without memory | Provider decision without memory |
| A2 | Same threshold controller with similar-state action reuse | Same provider prompt plus retrieved episodes |

Offline A1/A2 measure deterministic case retrieval, not LLM capability. The model setting and prompt instructions are held constant within each API pair. OpenRouter's free router may select different models; actual IDs are logged. Model nondeterminism remains.

## Workload

The main offline run uses seeds 1729 to 1733 and 120 five-second windows per controller and seed: 600 simulated seconds each and 2400 windows overall. This is accelerated simulation, not ten minutes of packet emulation. Repeated light, primary-burst, alternate-busy and dual-congestion episodes have seeded uniform perturbations. Aggregate demand records are NetFlow-style synthetic data, not a captured dataset.

Every condition starts with zero queues and empty memory and reuses byte-identical demand. SHA256 values bind the traffic to the summary. Memory has no future or cross-seed records. The paced Gemini pilot uses three seeds and 24 windows per controller and seed. The free-router pilot uses one seed and 12 windows. Their sizes and fallback coverage constrain conclusions.

## Equations and units

For path i, C=10 Mbps, B=0.5 Mbit and T=5 s:

`q_next = min(B, max(0, q_prev + (admitted_rate-C)*T))`

`overflow = max(0, q_prev + (admitted_rate-C)*T - B)`

`delivered = q_prev + admitted_rate*T - q_next - overflow`

Average queue is the exact area under the piecewise linear queue trajectory divided by T. Modeled delay is `8 + 1000*average_queue/C` ms, weighted across delivered volume on both paths. It is a queue-plus-propagation proxy, not measured RTT or p95. Goodput equals delivered volume/T. Loss includes overflow and deliberate meter drops against all offered traffic. The test suite checks conservation: old queue plus offered equals delivered plus dropped plus new queue.

The meter proposes `ceil(0.8*elephant_kbps)` to respect a 20% reduction bound. Safety enforces a 512 kbps floor and a 90% alternate capacity ceiling, and vetoes unknown targets. Actions expire after one window; queues persist.

## Reward and statistics

`r = -0.4*delta_latency/50 + 0.4*delta_goodput/5000 - 0.2*delta_loss/20`

Units are ms, kbps and percentage points. The simulator compares a no-op counterfactual and chosen action on the same demand and initial queues; only the chosen action commits the next queue. This measures a local modeled effect, not real-world causality or stability. The original LangGraph testbed uses sequential windows instead.

Tables use arithmetic means across windows. Pooled loss separately aggregates dropped/offered volume. For multiple seeds, 95% Student-t intervals use paired per-seed differences, n-1 degrees of freedom, and critical values 2.776 for five seeds or 4.303 for three. Windows are not independent replicates. One seed has no interval; small samples are exploratory. Failed API windows stay in operational results and are counted.

## Reproduce

```powershell
.\run.ps1 test
.\run.ps1 experiment
.\run.ps1 probe
.\run.ps1 gemini
.\run.ps1 openrouter
.\run.ps1 free-models
.\run.ps1 dashboard
```

Python equivalents include `python -m pytest tests eval/tests -q`, `python -m eval.run_simulation`, and `python app.py`. `.deps` is local to this computer's bundled Python 3.12. On another machine, run `setup.ps1` to create `.venv`; binary packages cannot be copied across Python versions.

## Primary research sources

1. Shinn et al. Reflexion: Language Agents with Verbal Reinforcement Learning, NeurIPS 2023. https://arxiv.org/abs/2303.11366 . Verbal feedback and episodic memory motivate the approach. Its task-specific scores are not SDN measurements.
2. Rusek et al. RouteNet: Leveraging Graph Neural Networks for network modeling and optimization in SDN, 2019. https://arxiv.org/abs/1910.01508 . Reports worst-case mean relative error of 15.4% in its KPI prediction evaluation. Prediction error is not a routing latency reduction or a result reproduced here.
3. Google model catalog: https://ai.google.dev/gemini-api/docs/models . Confirms `gemini-3.5-flash-lite`.
4. Google structured output: https://ai.google.dev/gemini-api/docs/structured-output . Application-level semantic validation is still required.
5. Google rate limits: https://ai.google.dev/gemini-api/docs/rate-limits . Quotas vary by project, model and tier.
6. OpenRouter Free Models Router: https://openrouter.ai/docs/guides/routing/routers/free-router . Free endpoints and actual routed model identity are recorded.
7. Ryu REST reference: https://ryu.readthedocs.io/en/latest/app/ofctl_rest.html . Flow, meter and counter interface definitions for the separate Linux adapter.

Accessed 20 October 2026. Published measurements remain separate from local experiments.
