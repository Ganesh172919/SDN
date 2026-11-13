# SELF-X implementation audit

The [comparison atlas](comparison/SELF_X_Algorithm_Comparison.pdf) contains 13 XY plots with all 14 configurations. The [effects CSV](comparison/effects.csv) gives the change against each comparator. The [execution counters and paired intervals](comparison/effects.json) and [per-seed measurements and training fingerprints](comparison/runs.json) support the conclusions below.

## What the older scripts executed

| Earlier evidence | Implementation finding |
|---|---|
| Table V DQN and MARL | The two branches in [run_table5_comparison.py](../selfx/eval/run_table5_comparison.py) used fixed congestion thresholds and random action selection. They contained no neural value functions, replay optimisation, target updates, or trained checkpoints. The published 17.69% reduction against “DQN” inherits that proxy from the same script. |
| Table V LLM and full system | The reflexive LLM branch drew randomized threshold actions. The full branch called DPP with fixed parameters. It executed neither LoRA inference nor a governor. |
| Table II ablation | [run_table2_ablation.py](../selfx/eval/run_table2_ablation.py) used random choices in A1–A3, a heuristic in A4, and DPP in A5. Constructing a backend in the script did not invoke its learned policy. |
| Later remote pipeline experiment | [run_pipeline_study.py](../selfx/eval/run_pipeline_study.py) invokes a model client and LoRA. S2 performs critique. S3 replaces that path, and S4 adds both a window-rate optimiser and governance. S5 waits for the LoRA call before running DPP, which then chooses its own action. Governance comes from a single model response with role-labelled fields. These stages do not isolate every component. The tabular Q baseline in this experiment uses a value table. |

The old proxy commands require explicit historical mode and label regenerated results as proxy evidence.

## What ran in the corrected benchmark

| Configuration | Executed policy |
|---|---|
| S0 Static | Fixed primary forwarding. |
| S1 Base LM | Pinned SmolLM2 base model, constrained to three action tokens, every 5 s. |
| S2 Base LM + critique | S1 plus a separate model pass over the proposal and up to three prior windows' realised outcomes. This adds one simulated forward-pass delay. |
| S3 LoRA policy | Same direct action prompt and cadence as S1, with the shipped adapter enabled. S1 versus S3 tests the adapter as a direct policy. S2's critique is a separate arm. |
| S4 Agentic at 5 s | The full stack with DPP decisions every 5 s. |
| S5 SELF-X Agentic | Safety-constrained DPP every 100 ms, a LoRA action preference every 5 s, and a model-governed objective every 30 s. The LoRA preference subtracts an equivalent 0.20 from the preferred action's score when the action is feasible. |
| Capacity threshold / Least loaded / Tabular Q | Reference controllers at 5 s. The tabular learner updates from reward online. |
| DQN | One two-hidden-layer Q-network, experience replay, a target network and gradient updates. It chooses greedily every 100 ms in evaluation. |
| Two-agent IQL | A project-specific MARL reference. One DQN votes on routing and one on primary-path metering. Each has its own parameters, replay buffer and target network. They share telemetry and team reward. Their votes combine into the same three action kinds as DQN. |
| DPP only / Agentic without LoRA / Agentic without governor | All run DPP every 100 ms. DPP only removes both model components. The two other arms remove one component each. |

The governor runs five distinct specialist prompts on the same local model, then runs an orchestrator prompt conditioned on their ballots. The orchestrator chooses a bounded change to the DPP objective. The guard checks each effective action. The evaluation uses no replay stress gate or online LoRA training. Model computation is memoised by prompt or observation and assigned a fixed 400 ms per forward stage. The five specialists share one parallel stage. The LoRA checkpoint comes from the earlier training run and is supplied with the repository.

## What the measurements support

- **Cadence.** SELF-X Agentic averaged **60.54 ms** delay. It reduced delay **25.15%** versus static forwarding and **15.65%** versus the matched stack at 5 s. This latter comparison isolates the DPP decision cadence.
- **Learned baselines.** Delay was **1.22% lower** versus both DQN and two-agent IQL (paired difference −0.75 ms, pointwise 95% CI −0.96 to −0.54 ms, Holm-adjusted p = 0.0014). Agentic lost **0.33 percentage points more** traffic and delivered **0.40% less** goodput. All three neural networks completed 2,692 gradient updates and 26 target synchronisations each. The frozen policies made different proposals, and the guard produced identical effective action sequences for all 12 seeds, verified by per-slot action hashes. Their datapath curves overlap.
- **LoRA and governance.** The full stack was **0.12 ms slower** than DPP alone (Holm-adjusted p = 0.074). Disabling LoRA reduced delay by **0.48 ms** (Holm-adjusted p = 0.0054). LoRA changed 2,920 of 21,600 optimiser choices at the states actually visited by the full controller. The 72 governance epochs generated 360 ballots. All five roles and the orchestrator selected the same adjustment on every observed state. Reapplying that adjustment changed the objective, but this run gives no evidence of state-dependent governance.
- **Critique.** S2 requested 432 critiques with 420 nonempty memory prompts. It revised zero proposals. Any S1–S2 difference on these traces therefore cannot be credited to action revisions.

Training uses seeds 1000–1017. Testing uses seeds 2100–2111, four per workload profile. Each paired test seed uses the same offered traffic fingerprint for all controllers. The primary analysis estimates the equal-weight mean of the three profile-specific paired delay differences, with Welch–Satterthwaite intervals and Holm adjustment across the 13 comparisons against Agentic. Loss and goodput are secondary outcomes. The experiment evaluates one fluid topology and one trained realisation of each neural baseline. It provides no evidence for hardware performance or a novelty claim.

