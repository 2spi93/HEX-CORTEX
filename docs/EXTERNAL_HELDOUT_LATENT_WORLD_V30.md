# V30 — External Episode-Heldout World Evaluation (CPU Only)

## Real observed need and scope

Operator V29 on Windows: **1,957 tests passed**, Ruff all checks
passed. CPU Qwen Coder still produced four plausible but ungrounded
changes (\`file: null\` and \`grounded_proposal_count: 0\`). The V29
rolling world guard successfully kept the synthetic correction only in
the previously observed stable regime and fell back to baseline on
already-observed vanished/reversed-bias regimes. This says nothing
about first-step safety after an unseen shift.

**V30 is a new DATA CONTRACT and HELD-OUT EVALUATION ADAPTER**, not
a new world-model architecture.

The repository ALREADY has a real, local, trainable image-latent model:

\`\`\`text
ComfyUI/output image(t), approved action, image(t+1)
  -> frozen DINOv2 CPU encoder (same weights + pooling + descriptor)
  -> observed transition JSONL + manifest
  -> compact residual MLP training (train/validation/test)
  -> safetensors candidate, checkpoint hash, metric-gated manual promotion
\`\`\`

Relevant existing modules:
- \`cortex_observed_transition_dataset.py\`
- \`cortex_compact_world_model.py\`
- \`cortex_world_model_eval.py\`
- \`cortex_world_training_cli.py\`
- \`cortex_world_model_completion_audit.py\`

V30 does not create a second train pipeline. It reuses
\`build_world_model_dataset_manifest\`, \`evaluate_world_model_candidate\`
and the same \`_build_model\` residual MLP class that the compact
training module uses, loading only approved \`safetensors\` on CPU.

## Genuine external datasets to prepare OFFLINE

Public research sources:
- **DROID** (robot actions, videos and timed proprioceptive
  trajectories): https://github.com/droid-dataset/droid
  and https://github.com/droid-dataset/droid_policy_learning .
  Its official repository offers a ~2 GB example of 100 episodes and
  a substantially larger full dataset. Neither has been downloaded
  by V30.
- **BridgeData V2** (real robotic manipulation trajectories across
  varied tasks/environments): https://bridgedata-v2.github.io/ .
- Meta **V-JEPA 2.1** was released 2026-03-16. It learns dense,
  temporally coherent video embeddings:
  https://github.com/facebookresearch/vjepa2 .
  **V-JEPA 2-AC** is the separate action-conditioned predictor.
  Do NOT treat either as already installed or compatible with the
  existing DINOv2 image-CLS latent.
  
No external dataset, image/video, model weights, or external
licence terms are automatically accepted, downloaded or verified.

## Approved local JSONL contract

Supply an operator-prepared **JSONL with one independent action-conditioned
transition per line**, using the very same frozen DINOv2 encoder
descriptor used to train the candidate model. A conceptual example:

\`\`\`json
{"sample_id":"episodeA-step0001","source_dataset":"my_measured_dataset","episode_id":"episodeA","environment_id":"lab_A","split":"train","timestamp_seconds":0.25,"encoder_descriptor_hash":"<64-character sha256>","state_latent":[0.13,0.22],"action":[0.1],"next_state_latent":[0.14,0.25]}
\`\`\`

This two-dimensional vector is for illustrating the **format only**;
the real DINOv2 embedding dimension is determined by the chosen
encoder. The numbers in this example are NOT real data. DO NOT pass
a DROID robot joint-state vector as though it were a DINOv2 image
embedding or compare unrelated encoder backends.

Admission checks:
- bounded finite vectors, consistent latent/action dimensions and
  single encoder descriptor identity;
- true episode-level and **environment-level** train/validation/test
  isolation — the same episode/environment may NOT occur in multiple
  splits;
- duplicate sample IDs, identical latent/action/next-latent tuples,
  malformed timestamps and contradictory split memberships refused;
- at least two training episodes, two test episodes and two distinct
  held-out test environments; all three partitions required;
- an operator-selected external file only, size-bounded, no implicit
  network/download; raw vectors remain transient for evaluation, not
  included in the report and never persisted by the evaluator.

**Warning:** declared source, timestamps, splits and hashes are not
publisher signatures. Even a structurally accepted JSONL is NOT
independently attested real-world data. Dataset licensing, calibration,
timestamp synchrony, image preprocessing and the candidate's exposure
to the test set need independent external validation. The policy
here blocks basic leakage, but not all forms of semantic contamination.

## Evaluating the EXISTING trained compact world model

The option to use actual safetensors checks the candidate JSON
integrity digest, \`predictor.safetensors\` weight SHA256, residual MLP
architecture, latent dimension, action dimension and encoder
descriptor. It loads the same network on **cpu**, inference mode,
weights frozen. NO new training, writes, deployment or activation.

V30 scores actual held-out output vs the **identity baseline** and
calls the existing \`evaluate_world_model_candidate\` criterion.
Additionally reports per-environment mean-squared error and refuses
manual-review qualification if ANY environment regresses, even when
the mean improves.

The claim is **only** comparison within the supplied test data;
\`independent_test_origin_attested=false\`,
\`training_test_independence_independently_attested=false\`,
\`real_world_generalization_proven=false\`, and
\`model_activated=false\`. Qualification is for human review,
NOT automatic promotion.

## Windows PowerShell commands — each ONE physical line

Update, test, lint:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

No-read/no-model dry run:

~~~powershell
python -m hex_cortex.memory.cortex_external_latent_cli_v30 --dry-run --jsonl "datasets/external_transitions.jsonl"
~~~

Synthetic contract example, created **in memory only**,
not a real scientific experiment:

~~~powershell
python -m hex_cortex.memory.cortex_external_latent_cli_v30 --synthetic-example
~~~

Audit an ACTUAL preprocessed user-owned local JSONL (will not exist
until the user prepares it):

~~~powershell
python -m hex_cortex.memory.cortex_external_latent_cli_v30 --jsonl "datasets/external_transitions.jsonl" --approve-read
~~~

Compare a REAL, already-trained compact checkpoint, assuming both
the user-owned external JSONL and the existing local candidate actually
exist and use exactly matching encoder/action contracts. This is an
EXPLICIT CPU-only checkpoint inference authorization:

~~~powershell
python -m hex_cortex.memory.cortex_external_latent_cli_v30 --jsonl "datasets/external_transitions.jsonl" --candidate ".hex-cortex/world-model/candidate/candidate.json" --approve-read --approve-inference
~~~

Existing project readiness audit (does not train):

~~~powershell
python -m hex_cortex.memory.cortex_world_training_cli audit --project-root .
~~~

**No device/GPU:** RX 6700 XT remains entirely outside this work.

## Next verified engineering gates

1. Operator provides a *small and legally usable* source dataset.
2. Convert real image/video frames to the same frozen encoder domain
   using a separately approved offline preprocessing run.
3. Validate frame timing, action correspondence, camera calibration,
   source licensing, train/test contamination by trajectory and room.
4. Run CPU-only actual checkpoint comparison, publish failure cases
   and per-environment regressions; keep test partition fixed.
5. Only then consider a proper **V-JEPA 2.1 feature backend** or
   **V-JEPA 2-AC predictor backend** with an explicit encoding/action
   compatibility adapter, no network by default.
6. Independently evaluate single-step and long-horizon latent prediction,
   confidence calibration, partial observability, intervention
   counterfactuals and physical-world validity, with completely
   separate approval/safety gates.
