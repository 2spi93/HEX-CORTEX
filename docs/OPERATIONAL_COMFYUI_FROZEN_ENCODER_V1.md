# Operational ComfyUI and Frozen Encoder v1

This wave turns the media and latent contracts into a local operational path.

## Invariants

- ComfyUI endpoints must use explicit localhost HTTP with a port.
- Workflow imports require operator approval.
- Workflow templates may contain reviewed placeholders; runnable workflows may not.
- Network execution requires operator approval.
- Raw prompts, raw ComfyUI history, raw images, and embedding vectors are not persisted by receipts.
- The visual encoder is frozen, placed in evaluation mode, and runs under inference mode.
- Model downloads are disabled by default.
- A model download requires both `--allow-model-download` and `--operator-approved`.

## 1. Install and start ComfyUI locally

Use an official ComfyUI installation method. A typical CLI path is:

```powershell
python -m pip install comfy-cli
comfy install
comfy launch
```

The default HEX-CORTEX endpoint is:

```text
http://127.0.0.1:8188
```

Verify all three required API surfaces:

```powershell
hexcortex-operational comfyui-probe
```

The probe checks:

- `/system_stats`
- `/queue`
- `/object_info`

## 2. Validate the reviewed API template

```powershell
hexcortex-operational workflow-validate `
  workflows/comfyui/txt2img_basic_api_v1.workflow.json `
  --allow-placeholders
```

The template uses the standard API graph pattern:

```text
CheckpointLoaderSimple
→ CLIPTextEncode positive / negative
→ EmptyLatentImage
→ KSampler
→ VAEDecode
→ SaveImage
```

## 3. Import the homologated workflow bundle

```powershell
hexcortex-operational workflow-import `
  workflows/comfyui/txt2img_basic_api_v1.workflow.json `
  workflows/comfyui/txt2img_basic_api_v1.profile.json `
  --registry-root .hex-cortex/comfyui-workflows `
  --operator-approved
```

This writes a normalized local bundle under:

```text
.hex-cortex/comfyui-workflows/txt2img_basic_api_v1/
```

The local registry is ignored by Git.

## 4. Run the workflow

Replace the checkpoint with a filename actually present in the local ComfyUI `models/checkpoints` directory.

```powershell
$values = @{
  checkpoint = "your-model.safetensors"
  prompt = "A precise technical diagram of HEX-CORTEX"
  negative_prompt = "blurry, illegible text, distorted geometry"
  seed = 42
  width = 1024
  height = 1024
  filename_prefix = "HEX-CORTEX"
} | ConvertTo-Json -Compress

hexcortex-operational workflow-run `
  txt2img_basic_api_v1 `
  $values `
  --registry-root .hex-cortex/comfyui-workflows `
  --endpoint http://127.0.0.1:8188 `
  --operator-approved
```

The result contains an output manifest rather than embedding image bytes in the receipt.

## 5. Prepare the frozen DINOv2 encoder

Install the lightweight adapter dependencies:

```powershell
python -m pip install -e ".[dev,vision]"
```

Install the correct PyTorch build for the local hardware separately.

Inspect the plan without loading a model:

```powershell
hexcortex-operational encoder-plan path\to\image.png
```

The first approved run may populate the local model cache:

```powershell
hexcortex-operational encoder-run path\to\image.png `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device auto `
  --allow-model-download `
  --operator-approved
```

Later runs remain local-cache-only by omitting the two download flags:

```powershell
hexcortex-operational encoder-run path\to\image.png
```

The default receipt contains:

- input image hash;
- normalized embedding hash;
- embedding dimension;
- device and tensor metadata;
- proof that the model was frozen and in evaluation mode;
- no raw image and no persisted vector.

Use `--include-vector` only for an in-memory pipeline that immediately feeds the volatile vector into the latent world-model loop.

## 6. Audit

```powershell
hexcortex-operational audit --project-root .
python -m pytest
ruff check .
```

The audit is filesystem-only. Runtime readiness is established separately through the ComfyUI probe and encoder runtime checks.
