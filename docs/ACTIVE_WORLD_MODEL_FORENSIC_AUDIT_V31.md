# V31 — Existing Active World Model: Integrity Versus Generalization

## Ground truth from the operator's PC

Operator V30: **1976 passed, Ruff PASS**.
\`cortex_external_latent_cli_v30 --synthetic-example\` accepted six
**synthetic** transitions; this tests the schema only.
\`cortex_world_training_cli audit --project-root .\` reported:
- architecture_ready=true
- dataset_exists=true, manifest_allowed=true, training_ready=true
- candidate_trained=true, candidate_promotable=true
- active_predictor_ready=true, learning_complete=true
- next_action=run_active_predictor_and_collect_real_transitions

**CRITICAL INTERPRETATION:** The pre-existing completion audit checks
artifact flags and the **active registry JSON type**, NOT a successful
CPU neural forward pass, weight SHA256 verification, or scientifically
independent episode/environment test data. Consequently, it establishes
**a declared active model artifact**, not that the model can make
valid predictions in a real environment.

## V31 added forensic, read-only active-artifact audit

\`cortex_active_world_integrity_v31.py\` + operator CLI:
1. Read the V1 transition JSONL, dataset manifest, candidate manifest,
   promoted candidate and registry; limit file sizes and paths.
2. Rebuild the existing dataset manifest and check input-record content
   hashes, split counts, binding of checkpoint to dataset manifest and
   encoder identity.
3. Compute SHA256 from the original and promoted \`safetensors\`
   bytes, compare to both manifests and registry.
4. Check candidate manifest integrity, active registry integrity,
   promoted receipt identity and source candidate lineage.
5. Count identical image hashes and image-transition pairs reused
   across train/validation/test partitions. This is only a **partial**
   leakage audit, but known image sharing invalidates independence.
6. Warn that V1 transition format DOES NOT attest independent
   episodes, independently held-out environments, timestamp alignment,
   image-source ownership, sensor calibration or legitimate data origin.
7. Never import PyTorch, decode images, invoke model inference, run
   hardware, use GPU, download anything, auto-promote, or write a file.

The new audit reports `artifact_chain_ok` (file/registry/manifests)
separately from `dataset_split_evidence_ok` (exact image contamination).
A true artifact chain and a successful CPU forward pass DO NOT negate
a train/test-leakage blocker. The optional CPU smoke requires its own
read/inference approvals, uses `torch.inference_mode()` and only an
unrepresentative synthetic zero vector, and NEVER activates new weights.

A verified SHA256 chain proves byte consistency relative to local
metadata **only**, not that a file is a valid safetensors tensor map,
safe learned dynamics, externally signed, or independently generalizing.

If a controlled ComfyUI bootstrap reuses one image across many samples,
\`exact_image_overlap_between_splits\` might legitimately cause
\`integrity_blocked\`: this is an IMPORTANT detected evidence gap, not
proof that the MLP weights cannot execute. DO NOT bypass such a flag
by renaming files or randomly redistributing individual frames.
Group by *source image/trajectory/environment* and collect independent
test material instead.

## One-line Windows PowerShell operator commands

Sync + test + lint:
~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Configuration-only (reads nothing):
~~~powershell
python -m hex_cortex.memory.cortex_active_world_integrity_cli_v31 --project-root . --dry-run
~~~

Actual read-only deep integrity audit of your existing local V1
registry, weights and dataset (**operator approval**):
~~~powershell
python -m hex_cortex.memory.cortex_active_world_integrity_cli_v31 --project-root . --approve-read
~~~

Separately approved **real CPU model forward pass** on the already
active `safetensors` checkpoint with all-zero artificial vectors:
checks whether the actual stored neural network can be loaded and run,
**not** whether it predicts real images or generalizes to new scenes.
A contaminated train/test split remains explicitly reported and is
never silently upgraded to scientific readiness.

~~~powershell
python -m hex_cortex.memory.cortex_active_world_cpu_smoke_cli_v31 --project-root . --approve-read --approve-inference
~~~

Keep V30 data contract comparison separate:
~~~powershell
python -m hex_cortex.memory.cortex_external_latent_cli_v30 --synthetic-example
~~~

## Next decision

- If hashes, registry and candidate agree and no leakage is detected:
  run a **separately approved CPU forward pass** using the already
  promoted checkpoint and valid locally cached DINOv2 embeddings.
  Record latency, hidden dimension, input and output hashes.
- If hashes disagree: investigate without modifying the source artifacts.
- If split overlap is found: preserve the existing training checkpoint
  as experimental, but DO NOT claim independent generalization. Use
  DROID/BridgeData or independently captured, legally permitted,
  calibrated trajectories. Do not auto-download large datasets.
- All future V-JEPA 2.1 and action-conditioned V-JEPA adapters require
  an explicit encoder-identity and feature-dimension contract; DINOv2
  image CLS vectors cannot be treated as V-JEPA video embeddings.

PR remains draft. No merge or physical actuation.
