# Ganesh: submission, run steps, demonstration and presentation

Verified on 06 November 2026. Assigned tasks: **T20-T25**.

Ganesh's work is the **replay-to-LoRA self-improvement component of SELF-X**.
It trains an actual language-model adapter, checks it against a frozen evaluation
set, and manages promotion, rejection and rollback. The verified network results
come from CPU/fluid-model replay. Live Mininet integration and the remaining
team tasks are separate.

## 1. Exactly which files to submit

All prepared files are in this folder on the current computer:

```text
C:\Users\RAVIPRAKASH\SDN\SDN\selfx\output\submission\ganesh
```

| File | What to do | Contents / purpose |
| --- | --- | --- |
| **Ganesh_Submission.zip** | **Submit this.** Approximately 13.5 MB. | Ganesh's source code, trained adapters, replay inputs, tests, raw evaluation evidence, pinned requirements, setup script, this presentation guide and both PDFs. |
| **Ganesh_Submission_Report.pdf** | Submit alongside the ZIP when separate documents are allowed. | Four-page report covering the six tasks, verification, results and reproduction. A copy is also inside the ZIP. |
| **SHA256SUMS.txt** | Include alongside the ZIP/PDF. | Checksums for the core archive, model companion, report and this guide. |
| **Ganesh_Offline_Model.zip** | Include if the evaluator needs the base model without downloading it, and the upload limit permits. Approximately 214.3 MB. | Pinned pretrained base model, model card, license and checksums. Python packages still need installation. |
| **GANESH_SUBMISSION_AND_DEMO.md** | Keep for presentation preparation; a copy is included at the root of the ZIP. | This file: what was done, simple commands, demo narration and speech. |

**If the portal accepts only one file, submit `Ganesh_Submission.zip`.** It already
contains this guide, the report and all Ganesh component source/evidence. Without the optional
model companion, first model loading needs internet access to download the pinned
public base model. Installation of Python packages needs internet in either case.

The existing `SELF_X_Pending_Work_Audit.pdf` is already inside the core ZIP at
`documentation/SELF_X_Pending_Work_Audit.pdf`. It records Ganesh's six tasks as
complete in CPU/replay scope and preserves the other 33 assignments. It need not
be uploaded again for a Ganesh-only component submission.

The prepared ZIP contains the needed files; do not manually collect individual
Python files or submit `.venv`, `.env`, caches, Git files or the entire workspace.

## 2. What Ganesh has completed

| Task | Work completed | Main code inside the extracted ZIP |
| --- | --- | --- |
| T20: replay-to-training pipeline | Collected and checked completed episodes; created isolated training, stress and holdout splits; retained rejected examples and source hashes. | `selfx/agent/self_improvement/dataset.py`, `source_check.py` |
| T21: fine-tunable local policy | Connected a pinned pretrained language model to constrained network actions, structured output and an independent safety guard. No cloud LLM API is needed. | `policy.py`, `runtime.py`, `selfx/agent/providers.py` |
| T22: LoRA fitting | Ran one real 120-step CPU training cycle; saved adapter weights, a first-step checkpoint and training logs; verified that base weights remained frozen. | `training.py`, `candidate/` evidence |
| T23: evaluation gate | Compared candidate and base on the same 576 frozen stress observations; checked reward, latency, loss, safety and data lineage before promotion. | `evaluation.py`, `prediction_check.py` |
| T24: adapter lifecycle | Implemented accepted promotion, rejection without changing the active pointer, automatic no-op/rollback on a controlled load failure, and audit history. | `registry.py`, `runtime.py`, `common.py` |
| T25: weight attribution | Compared the accepted deployment against the bare base on a sealed six-seed holdout with the same prompt and memory disabled; retained actual on-policy examples for a later training cycle. | `evaluation.py`, `deployment.py`, `heldout_attribution/` evidence |

Code filenames without another prefix in this table are under
`selfx/agent/self_improvement/`. Evidence is under
`selfx/output/self_improvement/ganesh_20261106/bounded_adoption/`.

### Simple explanation of the pipeline

```text
Completed network episodes
          |
          v
Check outcomes, rewards, safety and data separation
          |
          v
Train a small LoRA adapter while freezing the base model
          |
          v
Compare candidate and incumbent on frozen stress data
          |
          +-- fails gate --> Reject; keep the active policy
          |
          +-- passes gate --> Activate; record audit event
                                    |
                                    +-- runtime fault --> No-op and rollback
```

LoRA means **Low-Rank Adaptation**: learn small additional matrices instead of
updating the entire language model. Here, **460,800 parameters were trainable out
of 134,975,808 total parameters**. The action choices are no-op, reroute and rate
limit; a separate safety check decides whether a proposal can be installed.

## 3. How to run it on this computer

Use **PowerShell**. The existing workspace already has its Python environment and
model. Run:

```powershell
cd C:\Users\RAVIPRAKASH\SDN\SDN\selfx
$PY = ".\.venv\Scripts\python.exe"
$Evidence = "output/self_improvement/ganesh_20261106/bounded_adoption"
& $PY -m scripts.verify_self_improvement --output tmp/ganesh_demo_verification.json
```

Expected: the final JSON contains `"status": "passed"`, all six task IDs,
successful weight/source checks and zero installed safety violations.
The new verification output goes into `tmp/`; submitted evidence stays intact.

Continue with the demo in section 5 from this same PowerShell window.

## 4. How to run the submitted ZIP on another Windows computer

### One-time preparation, before the presentation

1. Install **Python 3.12**. Confirm `python --version` shows 3.12.
2. Extract `Ganesh_Submission.zip` into a short folder such as `C:\SDN_demo`.
3. For a demo without downloading the model, extract `Ganesh_Offline_Model.zip`
   into the **same folder**. Both archives share the `Ganesh_Submission` prefix.
4. Confirm this file exists:
   `C:\SDN_demo\Ganesh_Submission\setup_submission.py`.
5. Open PowerShell and run:

```powershell
cd C:\SDN_demo\Ganesh_Submission
python tools/verify_bundle.py
python setup_submission.py
cd selfx
$PY = ".\.venv\Scripts\python.exe"
$Evidence = "output/self_improvement/ganesh_20261106/bounded_adoption"
& $PY -m scripts.verify_self_improvement --output tmp/ganesh_demo_verification.json
```

Expected: file integrity passes, package installation ends successfully, and the
last command returns `"status": "passed"`.

If `python` selects a different version and the Windows Python launcher is
installed, use `py -3.12 tools/verify_bundle.py` and
`py -3.12 setup_submission.py` for the first two Python commands.

No environment activation command, GPU, API key, Ryu controller or Mininet is
required for this component demo. Complete installation and one model load before
class; CPU model loading and inference can take time. The model companion avoids
the base-model download; it does not contain Python dependency installers.

On Linux/macOS, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
The clean-environment and relocation checks retained for this submission were
performed on Windows with Python 3.12.

## 5. Simple demonstration: show these in order

Start in `selfx/` with `$PY` and `$Evidence` set as above. Open the submission PDF
beside PowerShell. Use the retained results for the performance discussion and
the short new run to show backend execution.

### Demo A: show that the assigned work is complete

```powershell
& $PY -m agent.self_improvement status --registry "$Evidence/registry"
$Done = Get-Content "$Evidence/completion.json" -Raw | ConvertFrom-Json
$Done | Select-Object status, owner, task_ids, fine_tune_iterations | Format-List
```

Expected: `status: completed`, owner Ganesh, T20-T25, one fitting iteration, and
six registry audit events. The approved active adapter ID is:

```text
e38b484ce26842f219eedc0ec849471ec6ba3f6eeec4d9812b6bb3a14526481f
```

**Say:** "This is the trained adapter currently selected in my local registry.
The completion record links my six tasks to the saved experiment evidence."

### Demo B: prove that testing and independent verification pass

```powershell
& $PY -m pytest tests/test_self_improvement.py -q --basetemp=tmp/ganesh_demo_tests
& $PY -m scripts.verify_self_improvement --output tmp/ganesh_demo_verification.json
```

Expected: **22 focused tests pass** and verification reports `"status": "passed"`.
The verifier reconstructs the curated data from original replay, reloads real
model tensors and checks metrics, lineage, the audit chain and rollback evidence.

**Say:** "These checks verify saved weights and raw evidence, in addition to
testing the code paths. The larger project suite also passed 106 tests plus four
subtests; those are separate from these 22 focused tests."

### Demo C: show acceptance, rejection and rollback evidence

```powershell
$Pass = Get-Content "$Evidence/promotion_stress/report.json" -Raw | ConvertFrom-Json
$Fail = Get-Content "$Evidence/rejection_stress/report.json" -Raw | ConvertFrom-Json
$Pass.gate | Format-List
$Fail.gate | Format-List
Get-Content "$Evidence/rollback_demo.json"
```

Expected:

- Passing campaign: `accepted: True` and `all_frozen_stress_criteria_passed`.
- Weaker trained checkpoint: `accepted: False`, with recorded reasons.
- Rollback record: `controlled_fault: true`, fallback action `no_op`, rollback
  `completed`, and restored policy ID starting with `base:`.
- The approved adapter was subsequently restored; Demo A shows its current ID.

**Say:** "The lifecycle accepts only candidates that pass the unchanged stress
gate. A weaker checkpoint was rejected without changing the active policy. A
controlled adapter-load fault produced an explicit no-op and restored the prior
base policy. These are retained, independently checked lifecycle records."

This step displays the recorded fault experiment; it does not inject a new fault
into the submitted registry. The focused tests also execute lifecycle behavior
using temporary fixtures.

### Demo D: execute the local backend on a new short simulation

```powershell
$DemoOut = "output/ganesh_demo_" + (Get-Date -Format "yyyyMMdd_HHmmss")
& $PY -m eval.run_simulation --provider local_lora --model "$Evidence/registry" --conditions A0 A1 A2 --cycles 4 --seeds 3302 --out-dir $DemoOut
```

Expected: **12 windows** in total; A1/A2 decisions have `origin=local_lora`;
`api_decision_windows`, `api_reflection_windows` and `fallback_windows` are zero.
The summary is saved at `$DemoOut/summary.json`.

**Say:** "This new trace shows the trained local backend working through the
existing simulation interface without cloud inference. It is a functionality
demo. The performance comparison comes from the larger sealed holdout."

For this short seed, zero reward and identical network metrics across the three
conditions are expected; the trace is not congested enough to establish gains.
The runner's existing A0/A1/A2 names here are backend smoke conditions. This demo
does not establish completion of the separate required A1-to-A5 study.

### Demo E: present the retained results

Show page 3 of `Ganesh_Submission_Report.pdf` and the table in section 6 below.
If asked for the source JSON, run:

```powershell
$Done.holdout_summary | ConvertTo-Json -Depth 6
$Done.weight_attribution | Format-List
```

**Say:** "Both policies received the same frozen observations. The same prompt
was used and memory was disabled. This isolates the effect of the fitted weights
within the fixed rollout mask."

For a short presentation, use A, C, D and E; perform the full verification in B
beforehand and keep its successful output available.

## 6. Results to report accurately

### Experiment record

- Base model: `HuggingFaceTB/SmolLM2-135M-Instruct`.
- Pinned revision: `12fd25f77366fa6b3b4b768ec3050bf629380bac`.
- Training: **1,122 approved episodes**, **120 optimizer steps**, one fitting cycle.
- Stress set: **576 observations**, separate seeds from training.
- Final holdout: **864 observations**, six independent seeds, three profiles.
- **30 rejected training examples** were retained for audit rather than fitted.
- Accepted deployment: a **25% deterministic observation-hash threshold** selects
  the fitted adapter; other observations use the pinned bare base. Actual adapter
  selection was 136/576 stress and 231/864 holdout observations.
- **24 actual on-policy episodes** were saved for a later training cycle. They
  were not used to train the submitted adapter.

### Final sealed holdout: bare base versus bounded LoRA adoption

| Metric | Bare base | Accepted deployment | Interpretation |
| --- | ---: | ---: | --- |
| Cumulative reward, all six seeds | 64.188490 | 70.308932 | Improved |
| Mean reward per observation | 0.074292 | 0.081376 | Improved |
| Mean modeled network latency, ms | 19.014259 | 18.061938 | Lower |
| Mean total loss, % | 4.083811 | 4.117937 | Increased by 0.034125 percentage points |
| Mean throughput, Mbps | 13.555983 | 13.553564 | Slight decrease |
| Unsafe proposals vetoed by the guard | 484 | 353 | Fewer unsafe proposals; guard still required |
| Installed safety violations | 0 | 0 | None observed in this replay |

Across six independent seeds, the mean cumulative reward gain per seed was
**1.020074**, with a **95% confidence interval [0.675774, 1.364374]** and a
two-sided paired t-test **p = 0.0006203**. The replication unit was the seed, not
each individual observation.

**Why 25% adoption?** The initial full-adapter trial improved reward but increased
stress loss by **0.148433 percentage points**, exceeding the frozen gate allowance
of **0.10 percentage points**, so it was rejected. The bounded variant used the
same fitted weights with a fixed hash mask and passed the unchanged stress gate.
The sealed holdout was evaluated after this selection; it did not select the
deployment fraction.

**How strong is the verification?** The larger project suite passed **106 main
tests plus four subtests**. A clean environment and an extracted, relocated
package each passed **22 focused tests**. Fresh inference independently reproduced
**5,184 retained model decisions**, with no retained inference cache; all actions
matched and the largest probability difference was about **1.2e-7**. Original
replay inputs exactly rebuilt the curated splits and excluded-case audit. The
final archive extraction also passed integrity, tensor/source verification and
a 12-window backend smoke run with zero cloud calls and no original-project reads.

The 106 tests are a project total; they are not 106 Ganesh-specific tests. Do not
add the 22 focused tests to 106 to claim a larger distinct-test count.

## 7. Presentation speech: approximately three minutes

> Good morning. I am Ganesh, and my contribution to SELF-X is the replay-to-LoRA
> self-improvement component, covering tasks T20 to T25.
>
> The problem I addressed is how a network action policy can learn from completed
> episodes while keeping model updates controlled and auditable. A training run
> alone is not enough: we also need to decide whether its output should replace
> the current policy, and what should happen if loading that policy fails.
>
> My pipeline first checks completed episodes and separates training, stress and
> holdout data. I used 1,122 approved training episodes, 576 stress observations
> and 864 sealed holdout observations. Rejected training examples and source
> hashes were retained so the data preparation can be independently checked.
>
> I used the pinned SmolLM2 135M instruction model and trained a LoRA adapter on
> the CPU for 120 steps. LoRA updates small additional matrices: 460,800 parameters
> were trainable. Reloaded tensor hashes confirmed that the base weights stayed
> frozen and that the adapter weights actually changed.
>
> After training, the candidate goes through an unchanged stress gate. The gate
> checks reward, latency, loss and installed safety violations before activation.
> The initial full-adapter trial improved reward but exceeded the allowed loss
> regression, so it was rejected. The accepted deployment uses the fitted adapter
> at a fixed 25 percent observation-hash threshold and the bare base elsewhere.
> This selection was made using stress data, before opening the holdout.
>
> I also implemented lifecycle handling. The retained evidence shows successful
> promotion, rejection of a weaker checkpoint without changing the active policy,
> and automatic no-op and rollback during a controlled adapter-load failure.
>
> On the final holdout, cumulative reward increased from 64.188490 to 70.308932,
> and modeled network latency decreased from 19.014259 to 18.061938 milliseconds.
> Loss increased slightly, from 4.083811 to 4.117937 percent, and throughput fell
> slightly. No installed safety violations were observed in either condition.
> Across six independent seeds, the paired reward comparison gave a p-value of
> 0.0006203. Both conditions used the same prompt with memory disabled.
>
> Verification included 22 focused tests, exact reconstruction of the curated
> data, real model-tensor reload checks and fresh reproduction of 5,184 recorded
> decisions. The extracted submission also ran in a clean environment without
> reading the original project or making cloud inference calls.
>
> I will now show the active registry, the accepted and rejected gate records,
> the rollback evidence, and a short new local-backend run. These results establish
> the CPU and frozen-replay adapter component. Live Mininet integration, the full
> governance and DPP system, and the complete A1-to-A5 study remain with the
> separately assigned team work. Thank you.

## 8. Short answers for questions

| Question | Answer |
| --- | --- |
| Did you really train model weights? | Yes. One 120-step LoRA fit changed adapter tensors; the frozen base and saved adapter were independently reloaded and hashed. |
| Why use LoRA? | It limits fitting to small additional matrices while keeping the pretrained base frozen. |
| What does the model decide? | A constrained action choice: no-op, reroute or rate limit. Local code supplies bounded structured parameters and an independent guard checks the proposal. |
| Why not activate the full adapter? | Its stress loss increase exceeded the unchanged allowance. The fixed 25% rollout variant passed the stress gate. |
| Does every metric improve? | No. Reward and modeled latency improved, while loss increased slightly and throughput decreased slightly. Report the tradeoff. |
| Are the latency values CPU inference time? | No. They are modeled network latency from the fluid replay. This work does not prove a 100 ms control deadline on the CPU. |
| Is this live Mininet evidence? | No. It is fluid-model/frozen-replay evidence. Live deployment is separate work. |
| Is this proof of superiority to the bootstrap heuristic? | No. The statistical comparison is the accepted deployment versus the pinned bare base. Training imitates approved bootstrap behavior. |
| Does the p-value establish the full A1-to-A5 result? | No. It is the six-seed paired adapter-versus-base comparison only. |
| What happens if an adapter fails to load? | The runtime emits an explicit no-op and attempts audited rollback to the authorized prior policy. The controlled failure record demonstrates this path. |
| What can be improved next? | Live-system integration, broader independent seeds/topologies, full A1-to-A5 experiments and additional train/evaluate cycles using newly collected episodes. |

## 9. Optional reproduction after the presentation

Recompute all retained model predictions without using the saved inference cache
(CPU-intensive; this is not needed for the short classroom demo):

```powershell
& $PY -m scripts.verify_self_improvement --fresh-inference --output tmp/ganesh_fresh_verification.json
```

Start a new complete fitting/lifecycle experiment in a new output directory:

```powershell
$NewRun = "output/ganesh_new_cycle_" + (Get-Date -Format "yyyyMMdd_HHmmss")
& $PY -m agent.self_improvement run --output $NewRun --steps 120 --cycles 48
```

A new candidate can legitimately fail its gate. Keep that outcome and its raw
evidence. Do not lower thresholds, tune on the sealed holdout or overwrite the
submitted experiment to manufacture a passing result.

## 10. Where the evaluator can inspect evidence

Inside `Ganesh_Submission/`:

| Location | Shows |
| --- | --- |
| `documentation/Ganesh_Submission_Report.pdf` | Task matrix, checks, results and scope |
| `selfx/docs/GANESH_TASK_COMPLETION.md` | Detailed task closure |
| `selfx/docs/SELF_IMPROVEMENT.md` | Technical workflow and CLI usage |
| `selfx/output/self_improvement/ganesh_20261106/bounded_adoption/completion.json` | Result summary, selected deployment and attribution |
| Same evidence folder: `candidate/`, `dataset/` | Trained adapter, logs, manifests and curated data |
| Same evidence folder: `promotion_stress/`, `rejection_stress/` | Accepted and rejected evaluations with raw traces |
| Same evidence folder: `rollback_demo.json`, `registry/` | Fault handling, active pointer and audit chain |
| Same evidence folder: `heldout_attribution/` | Sealed holdout report and per-seed statistics |
| Same evidence folder: `submission_verification.json`, `submission_readiness.json` | Fresh-inference check and verified source/environment record |
| Parent evidence folder: `replay/`, `source_map.json` | Original inputs and portable source mapping |
| `MANIFEST.sha256`; optional `MODEL_FILES.sha256` | Component and model-file integrity |

The release folder on the original computer additionally contains
`FINAL_VALIDATION.json` and `final_validation/` logs for the final archive
extraction checks. This Markdown presentation guide is included at the root of
the core ZIP and supplied separately for convenient reading.
