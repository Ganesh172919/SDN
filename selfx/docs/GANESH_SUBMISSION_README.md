# SELF-X - Ganesh submission (T20-T25)

Status correction, 07 November: T20-T24 are complete in CPU/replay scope; T25 is
partial. Its final reward comparison is verified, while explicit target-quality,
reward-convergence and iterations-to-target evidence remains pending. See
`selfx/docs/GANESH_PENDING_WORK_CHECK.md`. Earlier six-complete wording in the
frozen 06 November release is superseded by the current task assessment.

This is Ganesh's verified replay-to-LoRA component, with source, trained adapters,
raw evidence, tests and a submission report. The supported claim is CPU-trained,
safety-gated language-model adaptation evaluated using frozen fluid-network
replay. Live Mininet integration and the full six-agent/DPP course study belong
to the remaining team tasks.

## Start here

1. Extract `Ganesh_Submission.zip` to any directory.
2. Optionally extract `Ganesh_Offline_Model.zip` into the same parent directory.
   Both archives create the same `Ganesh_Submission/` folder. The companion
   provides only the pinned base model; Python packages still need installation.
3. From `Ganesh_Submission/`, check transferred files using system Python:

   ```text
   python tools/verify_bundle.py
   ```

4. Use Python **3.12** to create the pinned environment:

   ```text
   python setup_submission.py
   ```

5. Change to `selfx/`. On Windows, use `.venv\Scripts\python.exe` for the commands
   below. On Linux/macOS, replace it with `.venv/bin/python`.

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_self_improvement.py -q --basetemp=tmp/submission_tests
   .\.venv\Scripts\python.exe -m scripts.verify_self_improvement --output tmp/reverification.json
   .\.venv\Scripts\python.exe -m agent.self_improvement status --registry output/self_improvement/ganesh_20261106/bounded_adoption/registry
   ```

No API credentials are required. If the companion model was not extracted, the
first model load downloads the pinned public model revision. Existing absolute
paths in historical manifests record the original experiment environment;
`source_map.json` provides portable replay locations. The loader receives the
base model explicitly, so historical adapter-config paths are not used to find
it.

The verified model revision is
`HuggingFaceTB/SmolLM2-135M-Instruct@12fd25f77366fa6b3b4b768ec3050bf629380bac`.
The optional companion includes its publisher model card and Apache-2.0 license.

## Review order and evidence

- Read `GANESH_SUBMISSION_AND_DEMO.md` for the exact submission files, simple
  demo commands, a presentation speech and answers to common questions.
- Read `documentation/Ganesh_Submission_Report.pdf` for the task matrix,
  verification outcome, measurements and claim boundaries.
- Read `selfx/docs/GANESH_TASK_COMPLETION.md` and `SELF_IMPROVEMENT.md` for code
  interfaces, commands and the training/gate design.
- Inspect `selfx/output/self_improvement/ganesh_20261106/bounded_adoption/`:
  `candidate/`, `dataset/`, `registry/`, `promotion_stress/`, `rejection_stress/`,
  `heldout_attribution/`, `rollback_demo.json`, `completion.json`,
  `submission_verification.json`, and `submission_readiness.json`.
- The parent evidence folder retains original replay inputs and the rejected
  full-adapter trial. The approved policy uses the trained weights at a fixed
  25% observation-hash rollout threshold; the pinned bare base handles the rest.

The original results show improved reward and modeled latency, with a small
loss increase within the gate allowance and slightly lower throughput. These
are adapter-versus-base results. They are not live packet measurements,
A1-to-A5 results, or proof of superiority to the bootstrap heuristic.

## Additional reproduction

Recheck actual language-model decisions without using any retained inference
cache (CPU-intensive):

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_self_improvement --fresh-inference --output tmp/fresh_reverification.json
```

Run the existing backend adapter on a fresh simulated trace:

```powershell
.\.venv\Scripts\python.exe -m eval.run_simulation --provider local_lora --model output/self_improvement/ganesh_20261106/bounded_adoption/registry --conditions A0 A1 A2 --cycles 4 --seeds 3301 --out-dir output/local_backend_check
```

Start a new complete training/lifecycle experiment in a new directory:

```powershell
.\.venv\Scripts\python.exe -m agent.self_improvement run --output output/new_lora_cycle --steps 120 --cycles 48
```

The submitted trained weights are immutable evidence; reproduction creates new
artifacts. A new candidate is allowed to fail its frozen stress gate. Preserve
that outcome rather than relaxing thresholds or changing the sealed holdout.

## Integrity and scope

`MANIFEST.sha256` covers the component files. `MODEL_FILES.sha256`, when present,
covers the optional model companion. The release `SHA256SUMS.txt` covers the ZIP
files, report and presentation guide. Neither archive contains API keys, `.env`, virtual environments,
Git state or unrelated student outputs. `documentation/SELF_X_Pending_Work_Audit.pdf`
retains all team assignments: Ganesh's six tasks are closed in CPU/replay scope;
the other 33 tasks remain tracked separately.
