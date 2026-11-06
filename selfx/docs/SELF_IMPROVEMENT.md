# Ganesh: replay-trained LoRA and adapter lifecycle (T20-T25)

This adds an executable CPU training and deployment path under
`agent/self_improvement/`. It uses a real pretrained causal language model,
freezes its base parameters and trains LoRA matrices in `q_proj` and `v_proj`.
The existing independent action guard still constructs and validates flow
parameters. No cloud inference or paid training service is required.

The supported validation environment is the existing two-path fluid simulator.
The live telemetry bridge, full six-agent governor, DPP integration, A0-A5 study
and unseen-topology evaluation remain the separately assigned team tasks.

## Install and reproduce

From `selfx/`, use its local Python environment:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-lora.txt
.\.venv\Scripts\python.exe -m agent.self_improvement run --output output/self_improvement/new_run --steps 120 --cycles 48
```

Use a fresh output directory for each experiment. Models are cached in `.models/`,
which is excluded from Git and submission packaging. The pinned model is
[HuggingFaceTB/SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct),
revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, Apache-2.0. Its config,
tokenizer and safe-tensor weights are downloaded from that revision and hashed.
Remote model code is disabled. The optional dependency versions are pinned and
recorded again in each training manifest.

## T20: completed replay curation

`dataset.py` collects completed `(state, decision, measured outcome, reward,
reflection)` episodes or imports existing `eval.run_simulation` trace JSONL.
It does not invent missing outcomes for old memory-only records. Incomplete
records are quarantined with source locators. Approval must be a Boolean, all
numeric telemetry must be finite, and the recorded action is independently
validated again.

Only approved completed training episodes with reward >= 0 enter optimization.
Unsafe and below-threshold cases remain in `excluded.jsonl`; stress and holdout
keep the full workload. The initial behavior policy is explicitly labeled a
capacity-heuristic bootstrap, including bounded exploration. Later
`collect_bootstrap(..., policy=registered_policy.decide, seeds={"train": [...]})`
collects actual incumbent on-policy episodes for the next cycle.

The default independent seed groups are 3000-3007 for training, 3100-3103 for
stress and 3200-3205 for final holdout. Each includes mixed, flash and
alternate-heavy profiles. Cross-split observation duplicates and overlapping
seed groups are rejected. Source files, splits, examples and selection rules
have retained SHA256 manifests. Split files are verified before every use.

## T21-T22: actual language-model weight adaptation

`policy.py` presents a fixed, compact numeric observation and capacity/feasibility
flags. The model selects one of three existing vocabulary tokens: A (no-op),
B (reroute), C (bounded meter). `training.py` minimizes conditional cross entropy
over these tokens using approved replay actions. This is a constrained
action-token policy; it is not an unconstrained JSON/text-generation fine-tune.

Only LoRA matrices are optimized. The tokenizer, vocabulary projection and base
transformer remain frozen. Frozen-parameter hashes before/after fitting, adapter
parameter hashes, optimizer settings, sampled episode IDs, losses and model
revision are retained. Candidate folders contain `adapter_model.safetensors`,
`adapter_config.json`, `training.json` and `training_log.jsonl`. The first-step
checkpoint is retained as a genuine weak candidate for rejection testing.

Deployment supports a conservative deterministic rollout. The standard run uses
the adapter on 25% of observation hashes and the pinned bare base on the rest.
The mask/fraction are recorded in the immutable candidate manifest; the baseline
comparison uses the same mask with base weights on both branches. Thus weight
attribution measures this bounded adoption policy, not full-adapter performance.
A full-adapter candidate is allowed only if it independently passes the gate.
Cached inference is keyed by exact base/adapter tensors, config, fixed prompt and
observation hash; raw probabilities and cache-integrity hashes are retained.

The constrained policy cannot emit arbitrary switch IDs, flow matches or rates.
Local code synthesizes those values; the existing safety guard may veto the
proposal to no-op. Current observations must match the calibrated simulator.
Unsupported live telemetry fails closed rather than inventing queue values.

To continue fitting a promoted adapter from a new approved training dataset:

```powershell
.\.venv\Scripts\python.exe -m agent.self_improvement train --dataset output/self_improvement/next_cycle/dataset --output output/self_improvement/next_cycle/candidate --initial-adapter output/self_improvement/previous/candidate --steps 120
```

## T23-T24: frozen stress gate and auditable activation

`evaluation.py` compares the candidate and incumbent on exactly the same frozen
observations and recorded queue states. It computes independent same-window
network outcomes, rather than treating old behavior rewards as candidate scores.
Raw decisions, safety results, probabilities, measured metrics and per-seed
summaries are retained. This is offline frozen replay, not a sequential packet
testbed run.

The default, recorded gate requires mean reward gain >= 0.002, loss regression
<= 0.10 percentage points, latency regression <= 1 ms, profile mean-reward
regression <= 0.005, no increase in unsafe proposals and zero installed safety
violations. The registry freezes the stress digest and thresholds. Holdout
results cannot authorize promotion. Before activation it checks dataset/training
lineage, train-only optimizer IDs, model identities and hashes, then recomputes
every reported stress metric and guard result from raw observations. Stale
incumbent evidence, altered metrics and incomplete campaigns are rejected.

`registry.py` copies verified candidates into content-addressed artifact folders.
An exclusive writer lock serializes changes; `active.json` is replaced atomically
only after a passing decision. Rejected candidates leave the pointer byte-for-byte
unchanged. Hash-linked audit events retain candidate/incumbent identity,
evaluation digest and adapter-policy delta. This delta changes adapter identity;
the separate slow-loop V/weight/mask bridge is unchanged.

`runtime.py` verifies the active artifact before use. A controlled model load or
inference error returns no-op and automatically restores the prior incumbent.
Missing upstream telemetry returns no-op without blaming the adapter. The
end-to-end run demonstrates promotion, rejection of a genuinely trained earlier
checkpoint and automatic rollback, then reactivates the approved adapter.

```powershell
.\.venv\Scripts\python.exe -m agent.self_improvement status --registry output/self_improvement/new_run/registry
.\.venv\Scripts\python.exe -m agent.self_improvement rollback --registry output/self_improvement/new_run/registry --reason "operator rollback"
```

A crash may leave a `writer.lock` file. Inspect its recorded PID and confirm that
writer has stopped before removing that exact file. The system leaves activation
blocked instead of guessing whether a writer is still active.

## T25: separate weight changes from prompt/memory changes

Final attribution evaluates bare base and selected adapter once on sealed
holdout seeds, with identical prompts and memory disabled for both. It reports
cumulative reward per seed, mean paired difference, confidence interval and a
two-sided paired t-test. The only learned difference is the LoRA weights.
This is adapter-versus-base attribution; it does not replace the team's required
A1-to-A5 or matched-heuristic comparison. Learning here is imitation of approved
replay behavior; any gain over bare base is not evidence of superiority to that
capacity-aware teacher.

`completion.json` links the active adapter, stress decision, rejection evidence,
rollback demonstration, final holdout result and fine-tune iteration count.
`on_policy_replay/` contains fresh observations from the actual activated model
for a later cycle. They do not retroactively train the evaluated candidate.

## Use the registered backend in the existing loop

```powershell
$env:SDN_LORA_REGISTRY = (Resolve-Path output/self_improvement/new_run/registry).Path
.\.venv\Scripts\python.exe -m eval.run_simulation --provider local_lora --conditions A0 A1 A2 --cycles 12 --seeds 3300 --out-dir output/experiments/local_lora_smoke
```

`RestLLM("local_lora", model="path/to/registry")` also implements the existing
structured decision interface. Reflections on that path are explicitly
deterministic measured-outcome summaries. Local calls and fallbacks receive
local provenance, not API-success labels. A1/A2 here retain their historical
runner meanings; registering this backend does not implement A3-A5.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_self_improvement.py -q
.\.venv\Scripts\python.exe -m pytest tests eval/tests -q
```

Focused tests cover incomplete/unsafe data, leakage, changed hashes, real LoRA
updates with a frozen base, raw-metric replay, holdout exclusion, stale evidence,
atomic promotion, rollback, exclusive writers and audit tampering. Tiny random
transformers are used only for fast unit tests; the retained project evidence
uses the downloaded pretrained 135M model. Implementation follows the official
[PEFT LoRA workflow](https://huggingface.co/docs/peft/quicktour).
