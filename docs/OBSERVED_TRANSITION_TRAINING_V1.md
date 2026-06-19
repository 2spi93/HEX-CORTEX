# Observed Transition Training v1

This sprint closes the gap between the validated media-to-latent rail and a compact trainable world-model candidate.

## Fast path

Use `docs/WORLD_MODEL_LAB_FINISH_RUNBOOK.md` and `scripts/run_world_model_lab_finish.ps1` to run the complete guarded local lab cycle with one command.

## What is now implemented

```text
image_t + action_t + image_t+1
→ frozen DINOv2 re-encoding
→ observed transition record
→ append-only JSONL dataset
→ train / validation / test manifest
→ compact residual MLP candidate
→ baseline comparison
→ fail-closed promotion gate
→ active predictor registry
→ hash-only runtime prediction receipt
```

## Important boundary

The current predictor is domain-specific. A candidate trained on `controlled_visual_transform_v1` is only a predictor for that controlled transform domain. It is not a general physical world model.

A general action-conditioned world model still requires genuine sequential observations and meaningful actions from the target environment.

## Storage doctrine

Persisted:

- relative image references under `ComfyUI/output`;
- file hashes;
- action schema and bounded action values;
- encoder identity;
- latent hashes;
- evaluation metrics;
- safetensors model weights;
- candidate and promotion receipts.

Not persisted:

- raw image bytes inside receipts;
- raw DINOv2 vectors;
- raw predicted latent vectors;
- arbitrary pickle checkpoints.

## Install

```powershell
python -m pip install -e ".[dev,vision]"
python -m pytest
ruff check .
```

## Completion audit

```powershell
hexcortex-world-train audit --project-root .
```

The audit distinguishes:

- engineering completion;
- dataset readiness;
- candidate readiness;
- active predictor readiness.

## Fast controlled bootstrap

The bootstrap creates a small controlled visual-transform dataset from the already generated ComfyUI image. It applies bounded brightness, contrast, and translation changes and captures each transition through the frozen encoder.

```powershell
$ComfyRoot = "C:\Users\2spi\Documents\comfy\ComfyUI"
$ImagePath = Join-Path $ComfyRoot "output\HEX-CORTEX_00001_.png"
$StateRoot = Join-Path $PWD ".hex-cortex\world-model"
$Dataset = Join-Path $StateRoot "transitions.jsonl"

New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null

python scripts\bootstrap_controlled_transitions.py `
  "$ImagePath" `
  --comfy-root "$ComfyRoot" `
  --dataset-jsonl "$Dataset" `
  --count 12 `
  --device cpu `
  --operator-approved
```

Expected split counts for 12 samples:

```text
train       8
validation  2
test        2
```

## Build the manifest

```powershell
$Manifest = Join-Path $StateRoot "manifest.json"

hexcortex-world-train manifest `
  "$Dataset" `
  --output "$Manifest" `
  --min-train 8 `
  --min-validation 2 `
  --min-test 2
```

Expected:

```text
manifest_allowed = true
training_ready   = true
promotion_ready  = true
```

## Build a bounded training plan

```powershell
$Plan = Join-Path $StateRoot "plan.json"

hexcortex-world-train plan `
  "$Manifest" `
  --hidden-dim 128 `
  --epochs 40 `
  --batch-size 8 `
  --learning-rate 0.001 `
  --weight-decay 0.0001 `
  --device cpu `
  --max-seconds 900 `
  --output "$Plan"
```

## Train the compact predictor

```powershell
$CandidateDir = Join-Path $StateRoot "candidate"

hexcortex-world-train train `
  "$Manifest" `
  "$Plan" `
  --comfy-root "$ComfyRoot" `
  --output-dir "$CandidateDir" `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device cpu `
  --operator-approved
```

The candidate contains:

```text
candidate.json
predictor.safetensors
```

Promotion remains blocked unless the candidate improves over the identity baseline on the held-out test split and no required metric regresses.

## Promote only when the gate is green

```powershell
$CandidateManifest = Join-Path $CandidateDir "candidate.json"
$RegistryDir = Join-Path $StateRoot "registry"

hexcortex-world-train promote `
  "$CandidateManifest" `
  --registry-dir "$RegistryDir" `
  --operator-approved
```

Expected active files:

```text
active.json
active_candidate.json
active_predictor.safetensors
```

## Run the active predictor

```powershell
$ActiveRegistry = Join-Path $RegistryDir "active.json"

hexcortex-world-train predict `
  "$ActiveRegistry" `
  "$ImagePath" `
  --comfy-root "$ComfyRoot" `
  --action "0.25,0,0,0" `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device cpu
```

The prediction receipt contains only hashes and dimensions.

## Capture a real observed transition later

```powershell
hexcortex-world-train capture `
  "C:\path\inside\ComfyUI\output\state_t.png" `
  "C:\path\inside\ComfyUI\output\state_t_plus_1.png" `
  --comfy-root "$ComfyRoot" `
  --action "0.1,0,0,0" `
  --action-schema "control_1,control_2,control_3,control_4" `
  --split auto `
  --domain real_environment_v1 `
  --dataset-jsonl "$Dataset" `
  --device cpu
```

Do not mix controlled synthetic transitions and real-environment transitions in the same manifest. The manifest rejects mixed domains, encoder identities, latent dimensions, or action schemas.

## End-state audit

```powershell
hexcortex-world-train audit `
  --project-root . `
  --state-root .hex-cortex
```

The engineering rail is complete when `architecture_ready=true`.

The learned local rail is complete only when:

```text
dataset_exists         = true
manifest_allowed       = true
training_ready         = true
candidate_trained      = true
candidate_promotable   = true
active_predictor_ready = true
```
