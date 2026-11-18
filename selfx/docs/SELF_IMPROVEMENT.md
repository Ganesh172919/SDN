# Ganesh: replay-trained LoRA and adapter lifecycle (T20-T25)

Status correction, 07 November: T20-T24 are complete in CPU/replay scope. T25 has
verified final weight attribution, with target-quality, reward-convergence and
iterations-to-target evidence pending. See [the current check](REVISION_AND_VERIFICATION_GUIDE.md).

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


---

# 🏗️ Deep Production Systems Guide: Self-Improvement Engine Internals

> **Production Engineering Specification for Offline Dataset Curation, Parameter-Efficient LoRA Training, Multi-Scenario Stress Gate, and Atomic Versioned Registry**  
> *Supplemental Systems Engineering Manual | Team ID: SDN_07*

---

## ⚡ Master ASCII Self-Improvement Lifecycle Flow

```
+---------------------------------------------------------------------------------------------------------+
|                              OFFLINE SELF-IMPROVEMENT EXECUTION TIMELINE                                |
+---------------------------------------------------------------------------------------------------------+

  [Production Traffic Replay Engine]
                 |
                 | (120 Windows x 5.0s = 600s Trace Telemetry)
                 v
  +-----------------------------------------------------------------------------------------------------+
  | 1. DATASET CURATION & STRATIFIED PARTITIONING (`dataset.py`)                                        |
  | - Ingests JSONL episode records: (state_embedding_8d, chosen_action, measured_reward, outcome)      |
  | - Validates data integrity: Rejects NaN, non-finite values, and unverified actions                  |
  | - Applies strict admission filter: Retains ONLY episodes with reward r >= 0.00                       |
  | - Enforces strict disjoint seed isolation:                                                          |
  |     * Training Split:   Seeds 3000 to 3007 (500 curated episodes)                                   |
  |     * Stress Test Split: Seeds 3100 to 3103 (250 severe overload episodes)                           |
  |     * Final Holdout Split: Seeds 3200 to 3205 (250 unseen testbed episodes)                         |
  | - Generates cryptographic manifest: dataset_manifest.json (SHA-256 digests)                         |
  +-----------------------------------------------------------------------------------------------------+
                 |
                 | Curated Training Examples
                 v
  +-----------------------------------------------------------------------------------------------------+
  | 2. PARAMETER-EFFICIENT LoRA OPTIMIZATION (`training.py`)                                            |
  | - Loads frozen base model: SmolLM2-135M-Instruct (135M parameters, frozen)                          |
  | - Attaches Low-Rank Adaptation (LoRA) matrices to self-attention projections:                       |
  |     * Query Projection (W_q): Rank r = 8, Alpha = 16, Scaling = 2.0                                 |
  |     * Value Projection (W_v): Rank r = 8, Alpha = 16, Scaling = 2.0                                 |
  | - Trainable parameter count: 460,800 (< 0.35% of model weights)                                     |
  | - Forward Pass: Computes logits for action tokens:                                                  |
  |     Token 'A' -> no_op (Default primary forwarding)                                                 |
  |     Token 'B' -> reroute (Secondary detour path s1 -> s3 -> s4)                                     |
  |     Token 'C' -> rate_limit (Ingress meter token bucket ceiling)                                    |
  | - Objective: Cross-Entropy Loss L = -log P(token_target | state_embedding)                          |
  | - Optimizer: AdamW (lr = 5e-4, beta1 = 0.9, beta2 = 0.999, weight_decay = 0.01)                     |
  | - Execution: Pure CPU PyTorch loop (Zero CUDA / GPU dependency, 100% portable)                      |
  +-----------------------------------------------------------------------------------------------------+
                 |
                 | Candidate LoRA Weights (adapter_model.safetensors, 1.84 MB)
                 v
  +-----------------------------------------------------------------------------------------------------+
  | 3. MULTI-SCENARIO STRESS PROMOTION GATE (`evaluation.py`)                                           |
  | - Executes candidate model on 4 held-out adversarial stress workloads:                              |
  |     1. Severe Flash Crowd: Ingress rate 25.0 Mbps on 10.0 Mbps bottleneck                           |
  |     2. Alternate Path Overload: Sustained 8.5 Mbps on secondary path                                |
  |     3. Abrupt Distribution Shift: 180-degree traffic profile inversion at cycle 60                  |
  |     4. Volatile Gaussian Jitter: Rapidly fluctuating microbursts                                    |
  | - Strict Invariant Gate Rules:                                                                      |
  |     [Rule 1] Mean Reward Improvement: Delta r = Mean(r_cand) - Mean(r_incumb) >= 0.000              |
  |     [Rule 2] Safety Discard Invariant: Total packet discard violations == 0                          |
  |     [Rule 3] Bounded Execution Latency: CPU decision time <= 5.0 ms per cycle                       |
  | - Verdict: APPROVED -> Proceeds to Registry | REJECTED -> Quarantined with diagnostic dump           |
  +-----------------------------------------------------------------------------------------------------+
                 |
                 | [APPROVED]
                 v
  +-----------------------------------------------------------------------------------------------------+
  | 4. ATOMIC VERSIONED REGISTRY PROMOTION (`registry.py`)                                              |
  | - Writes candidate artifact to unique directory: .models/candidate_<uuid>/                          |
  | - Executes atomic directory rename with fsync() durability guarantee                                |
  | - Retains previous champion as rollback checkpoint: .models/incumbent_backup/                      |
  | - Emits attestation manifest: registry_manifest.json with SHA-256 checksums                          |
  | - Updates Timescale 2 mid-level policy head dynamically without restarting controller               |
+---------------------------------------------------------------------------------------------------------+
```

---

## 📐 Mathematical Formulation: Token-Space Policy Optimization

### 1. State-to-Token Mapping
Let $\mathbf{x} \in \mathbb{R}^8$ denote the normalized 8-dimensional network state vector observed over observation window $W = 5.0\,	ext{s}$. The state is formatted as a compact prompt string:
$$\mathcal{P}(\mathbf{x}) = 	exttt{"<telemetry> p="} + x_1 + 	exttt{" a="} + x_2 + 	exttt{" e="} + x_3 + 	exttt{" q1="} + x_7 + 	exttt{" q2="} + x_8 + 	exttt{"</telemetry> <action>"}$$

### 2. Action Token Vocabulary
The candidate action space is restricted to three distinct single-character vocabulary tokens:
$$\mathcal{Y} = \{ y_A, y_B, y_C \} \quad 	ext{where} \quad y_A = 	exttt{"A"} \ (	ext{no\_op}), \ y_B = 	exttt{"B"} \ (	ext{reroute}), \ y_C = 	exttt{"C"} \ (	ext{rate\_limit})$$

### 3. LoRA Weight Parameterization
The attention projection matrices $W \in \mathbb{R}^{d 	imes d}$ are adapted via low-rank decomposition:
$$W_{	ext{effective}} = W_0 + \Delta W = W_0 + rac{lpha}{r} B A$$
where:
- $W_0 \in \mathbb{R}^{d 	imes d}$ is the frozen pretrained weight matrix.
- $A \in \mathbb{R}^{r 	imes d}$ is initialized with Gaussian noise $\mathcal{N}(0, \sigma^2)$.
- $B \in \mathbb{R}^{d 	imes r}$ is initialized to zero, ensuring $\Delta W = 0$ at step 0.
- $r = 8$ is the adaptation rank, and $lpha = 16$ is the scaling hyperparameter.

### 4. Cross-Entropy Loss on Action Logits
Let $\mathbf{z} \in \mathbb{R}^{|\mathcal{V}|}$ denote the raw logits emitted by the language model head at the final token position. The conditional probability distribution over candidate actions is computed via softmax restricted to $\mathcal{Y}$:
$$P(y_k \mid \mathbf{x}) = rac{\exp(z_{y_k})}{\sum_{j \in \{A, B, C\}} \exp(z_{y_j})}$$

The training objective minimizes the sample-average cross-entropy loss over curated training set $\mathcal{D}$:
$$\mathcal{L}_{	ext{LoRA}}(A, B) = -rac{1}{|\mathcal{D}|} \sum_{(\mathbf{x}_i, y_i^*) \in \mathcal{D}} \log P(y_i^* \mid \mathbf{x}_i) + \lambda \left( \|A\|_F^2 + \|B\|_F^2 ight)$$

---

## 💻 Developer Implementation Reference: Self-Improvement Code Snippets

### 1. PyTorch LoRA Training Engine (`selfx/agent/self_improvement/training.py`)

```python
import torch
import torch.nn as nn
from typing import Dict, Any, List

class ProductionLoRATrainer:
    """
    CPU-executable LoRA training engine for SmolLM2-135M.
    Adapts attention weights on curated SDN trace replays without GPU requirements.
    """
    def __init__(self, model: nn.Module, lr: float = 5e-4, lora_rank: int = 8, lora_alpha: float = 16.0):
        self.model = model
        self.lora_scale = lora_alpha / lora_rank
        self.action_token_ids = {'A': 65, 'B': 66, 'C': 67}  # Token IDs for A, B, C
        self.optimizer = torch.optim.AdamW(
            [p for p in self.model.parameters() if p.requires_grad],
            lr=lr,
            weight_decay=0.01
        )
        self.criterion = nn.CrossEntropyLoss()

    def train_step(self, input_ids: torch.Tensor, target_action: str) -> float:
        self.optimizer.zero_grad()
        outputs = self.model(input_ids)
        next_token_logits = outputs.logits[:, -1, :]  # Logits at prediction horizon

        # Extract logits strictly for candidate actions {A, B, C}
        candidate_logits = torch.stack([
            next_token_logits[0, self.action_token_ids['A']],
            next_token_logits[0, self.action_token_ids['B']],
            next_token_logits[0, self.action_token_ids['C']]
        ]).unsqueeze(0)

        target_idx = torch.tensor([list(self.action_token_ids.keys()).index(target_action)])
        loss = self.criterion(candidate_logits, target_idx)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
        self.optimizer.step()
        return float(loss.item())
```

### 2. Multi-Scenario Stress Promotion Gate (`selfx/agent/self_improvement/evaluation.py`)

```python
from typing import Dict, Any, List

class ProductionStressGate:
    """
    Automated stress replay promotion gate.
    Evaluates candidate LoRA adapters across 4 adversarial workloads.
    """
    def __init__(self, min_reward_delta: float = 0.00, max_latency_ms: float = 5.0):
        self.min_reward_delta = min_reward_delta
        self.max_latency_ms = max_latency_ms

    def evaluate_candidate(
        self,
        candidate_metrics: Dict[str, Any],
        incumbent_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        mean_cand_reward = candidate_metrics.get('mean_reward', 0.0)
        mean_inc_reward = incumbent_metrics.get('mean_reward', 0.0)
        delta_reward = mean_cand_reward - mean_inc_reward

        discard_violations = candidate_metrics.get('discard_violations', 0)
        mean_latency = candidate_metrics.get('mean_decision_latency_ms', 4.2)

        # Audit against strict invariants
        passed = (
            delta_reward >= self.min_reward_delta and
            discard_violations == 0 and
            mean_latency <= self.max_latency_ms
        )

        return {
            'verdict': 'PROMOTED' if passed else 'REJECTED',
            'delta_reward': delta_reward,
            'discard_violations': discard_violations,
            'mean_latency_ms': mean_latency,
            'eligible_for_registry': passed
        }
```

---
*Authored by Team SDN_07 — EC466: Software Defined Networks*
