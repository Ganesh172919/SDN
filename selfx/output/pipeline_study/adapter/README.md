---
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
library_name: peft
pipeline_tag: text-generation
tags: [lora, sdn, flow-control, self-x]
---

# Stage-S3 LoRA adapter

Fitted by `selfx/scripts/train_pipeline_adapter.py` on the episodic replay buffer
that stage S2 accumulated while controlling this datapath. This is the artefact
stages S3, S4 and S5 load; it is the one the published results were produced with.

| | |
|---|---|
| Base | `HuggingFaceTB/SmolLM2-135M-Instruct`, revision `12fd25f7…`, frozen |
| Adaptation | LoRA, rank 8, alpha 16, on `q_proj` and `v_proj` |
| Trainable parameters | 460,800 of 134,975,808 |
| Objective | cross-entropy over three frozen action tokens (`no_op`, `reroute`, `rate_limit`) |
| Training set | 13 quantised states, advantage-filtered, class-balanced sampling |
| Gate set | 11 states from seeds held out of training |
| Gate result | agreement 0.273 (frozen base) → 0.455 (candidate), margin 0.02 → **promoted** |

`training.json` carries the provenance the loader checks before it will use this
adapter: parameter hashes taken before and after the fit proving the base stayed
frozen and the adapter weights moved, a hash of `training_log.jsonl`, and hashes
of the two artefact files. `agent/self_improvement/common.artifact_identity`
refuses the adapter if any of them does not match.

Regenerate with:

```bash
cd selfx && .venv/Scripts/python -m scripts.train_pipeline_adapter
```

A refit will not reproduce these weights bit-for-bit across PyTorch versions. The
committed adapter is the published artefact; see `REPRODUCE.md` §4.
