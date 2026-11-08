# Ganesh task status - reviewed 07 November 2026

T20-T24 are implemented and verified in the project's CPU/frozen-replay path.
T25 is partial: the final weight-attribution comparison is verified, while the
target-quality, reward-convergence and iterations-to-target measurement remains
pending. The approved policy is active in its local registry. See
[the pending-work check](GANESH_PENDING_WORK_CHECK.md) for the remaining criterion.
The other students retain live integration, DPP, website, exact ablation and
topology-transfer work.

| Task | Delivered evidence |
| --- | --- |
| T20: replay datasets | 1,122 approved training episodes; 576 stress episodes; 864 sealed holdout episodes. Thirty unsafe/below-threshold examples excluded from fitting and retained. Split/source hashes, seed isolation and leakage checks. |
| T21: policy backend | Pinned pretrained SmolLM2-135M-Instruct with CPU adapter inference, constrained action tokens, independent safety and the existing structured-output interface. |
| T22: LoRA training | One 120-step fitting cycle; 460,800 trainable LoRA parameters out of 134,975,808 total. Reloaded base hashes match before/after; adapter weights changed and reload correctly. |
| T23: stress gate | Frozen 576-case incumbent/candidate comparison; raw metrics replayed independently; unchanged thresholds, training-only lineage, safety and stale-report checks. |
| T24: lifecycle | Successful bounded-adoption promotion, rejection of a weaker trained checkpoint, unchanged pointer on rejection and automatic rollback after a controlled load failure. Approved adapter restored. Six hash-linked registry events. |
| T25: weight attribution - partial | Six independent holdout seeds, three profiles, 864 observations, same prompt and memory disabled. Mean per-seed cumulative reward gain 1.020074; paired p = 0.0006203; 95% CI [0.675774, 1.364374]. Target-quality, reward convergence and iterations-to-target evidence is pending; one recorded fit is not that full measurement. |

## Retained evidence

The main evidence folder is
`selfx/output/self_improvement/ganesh_20261106/bounded_adoption/`:

- `completion.json` and `verification.json`: task and verification summary.
- `dataset/manifest.json` and split JSONL: immutable curated data and lineage.
- `candidate/`: trained safe-tensor adapter, config, training manifest and logs.
- `promotion_stress/`: passing frozen campaign and raw decisions/probabilities.
- `rejection_stress/`: genuine weak-checkpoint failure and raw evidence.
- `rollback_demo.json`: controlled failure, explicit no-op and incumbent restoration.
- `heldout_attribution/`: final sealed evaluation, per-seed results and statistics.
- `registry/`: verified artifact copies, active pointer, frozen gate contract and audit.
- `on_policy_replay/train_replay.jsonl`: actual activated-policy outcomes for the next cycle.

The parent folder preserves the first full-adapter trial and its rejection.
It improved mean reward by 0.028343 but increased loss by 0.148433 percentage
points, exceeding the unchanged 0.10-point gate limit. It was never activated.
The successful candidate retains the same fitted tensor values and uses a
deterministic observation-hash rollout threshold of 25%, with the pinned bare
base on the remainder. The fraction/mask are part of its immutable deployment
manifest. Actual selection was 136/576 stress observations and 231/864 holdout
observations. Gate thresholds were not relaxed, and holdout data was not used
to choose the deployment variant.

## Measured tradeoffs

| Holdout metric | Bare base | Bounded LoRA adoption |
| --- | ---: | ---: |
| Cumulative reward across all six seeds | 64.188490 | 70.308932 |
| Mean reward per observation | 0.074292 | 0.081376 |
| Mean modeled latency, ms | 19.014259 | 18.061938 |
| Mean total loss, % | 4.083811 | 4.117937 |
| Mean throughput, Mbps | 13.555983 | 13.553564 |
| Unsafe proposals vetoed by the independent guard | 484 | 353 |
| Installed safety violations | 0 | 0 |

Reward and modeled latency improved while loss rose by 0.034125 percentage
points and throughput fell slightly. This is bounded-policy evidence in the
fluid simulator, not uniform metric dominance, a live-network result, an
A1-to-A5 result, or proof of superiority to the capacity-aware bootstrap teacher.
Stress metrics and a same-window evaluation convention are documented in the
raw reports. The statistical replication unit is the independent seed, not each
individual observation.

## Validation and handoff

The retained 06 November project tests passed: 77 selfx core/evaluation tests (plus four subtests),
14 slow-loop tests and 15 Web tests, for 106 tests total. The 22 focused tests
exercise dataset rejection/leakage, actual LoRA weight updates, frozen base
weights, stress metric replay, holdout exclusion, atomic activation, stale
reports, corrupted artifacts, automatic rollback, local-only provenance,
bounded adoption and inference-cache integrity.

`scripts/verify_self_improvement.py` independently reloads the pretrained base
and adapter and verifies their actual parameter hashes, data/training lineage,
stress/rejection/holdout metrics, audit chain and rollback evidence. The existing
simulation runner also completed a 12-window A0/A1/A2 backend smoke run with
local provenance and zero cloud calls.

Run instructions, next-cycle fitting, backend configuration and scope are in
[SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md). For the retained approved backend:

```powershell
$env:SDN_LORA_REGISTRY = (Resolve-Path output/self_improvement/ganesh_20261106/bounded_adoption/registry).Path
.\.venv\Scripts\python.exe -m scripts.verify_self_improvement
.\.venv\Scripts\python.exe -m agent.self_improvement status --registry $env:SDN_LORA_REGISTRY
```

All other student task assignments and original course targets remain tracked
in the existing pending-work PDF. D4 still needs the separately assigned live
slow/fast bridge and system-level integration; this adapter pipeline supplies
its missing training and weight-lifecycle components.

## Submission verification

The hardened implementation passed a fresh 5,184-decision model replay across all retained campaigns, including the rejected full-adapter trial. No retained inference cache was used. The maximum probability difference was 1.2e-7. Original replay inputs exactly rebuilt all three curated splits and the excluded-case audit. Added checks cover malformed pointers, unauthorized rollback predecessors, forged rewards, gate/probability consistency and portable source maps.
