# Media to Latent Pipeline v1

This wave connects a real ComfyUI output to the frozen visual encoder and the latent world-model baseline.

## Data flow

```text
ComfyUI execution receipt or observed output
→ safe output-manifest resolution
→ DINOv2 frozen encoder
→ normalized volatile latent state
→ deterministic action-conditioned residual baseline
→ optional observed-next-image encoding
→ surprise evaluation
→ one hash-only pipeline receipt
```

The baseline transition is intentionally not described as learned. It exists to validate lineage, dimensions, action conditioning, evaluation, and storage boundaries before training a predictor.

## Invariants

- Only files under `<ComfyUI>/output` may be resolved from a ComfyUI manifest.
- Relative path traversal and absolute filenames are rejected.
- Only bounded image files are accepted.
- The encoder remains frozen and local-cache-first.
- Raw images, embeddings, and latent vectors are not persisted in receipts.
- The pipeline receipt contains hashes, dimensions, runtime metadata, and optional surprise metrics.
- Model downloads still require explicit operator approval.
- A blocked pipeline receipt cannot be appended to the JSONL evidence stream.

## Install

```powershell
python -m pip install -e ".[dev,vision]"
```

## Validate the already generated image

```powershell
$ComfyRoot = "C:\Users\2spi\Documents\comfy\ComfyUI"
$ImagePath = Join-Path $ComfyRoot "output\HEX-CORTEX_00001_.png"

hexcortex-media-latent from-image `
  "$ImagePath" `
  --comfy-root "$ComfyRoot" `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device cpu `
  --action "0,0,0,0" `
  --receipt-jsonl .hex-cortex\media-to-latent-receipts.jsonl `
  --pretty
```

Because DINOv2 is already cached, this command should report:

```text
network_call_performed = false
pipeline_completed = true
latent_dim = 768
predictor_trained = false
embedding_vector_persisted = false
latent_vector_persisted = false
```

Use `--source-receipt-hash <hash>` when linking an existing image back to a previously observed ComfyUI execution receipt.

## Evaluate an observed transition

Generate or select a second image, then provide it as the observed next state:

```powershell
$ObservedImage = Join-Path $ComfyRoot "output\HEX-CORTEX_00002_.png"

hexcortex-media-latent from-image `
  "$ImagePath" `
  --comfy-root "$ComfyRoot" `
  --device cpu `
  --action "0.25,0,0,0" `
  --observed-image "$ObservedImage" `
  --surprise-threshold 0.25 `
  --receipt-jsonl .hex-cortex\media-to-latent-receipts.jsonl `
  --pretty
```

This performs two frozen encoder calls, predicts the next latent state, compares it with the observed latent, and emits normalized error plus surprise score.

## Run from a saved ComfyUI execution receipt

Store the JSON object returned by `hexcortex-operational workflow-run` in a UTF-8 JSON file, then run:

```powershell
hexcortex-media-latent from-receipt `
  .hex-cortex\receipts\comfyui-execution.json `
  --comfy-root "$ComfyRoot" `
  --device cpu `
  --action "0,0,0,0" `
  --receipt-jsonl .hex-cortex\media-to-latent-receipts.jsonl `
  --pretty
```

## Inspect evidence

```powershell
Get-Content .hex-cortex\media-to-latent-receipts.jsonl | Select-Object -Last 1
```

## Validation

```powershell
python -m pytest
ruff check .
hexcortex-operational audit --project-root .
```

The next development wave is an observed transition dataset builder. It will group current image, action, next image, encoder identity, and surprise measurement without persisting raw latent vectors.
