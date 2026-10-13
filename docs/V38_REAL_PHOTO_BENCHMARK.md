# HEX-CORTEX V38 — Object mask evaluation on novel natural photos

## Background

V37 ran the **real** MobileSAM `vit_t` on operator hardware with official weights
(`SHA256=6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f`).
The local synthetic smoke reported `reference_iou=0.997313` and `inference_including_load_ms=3548.08`,
`gpu_used=false`. This validates CPU model execution **only on a generated shape**.

V38 adds an optional, read-only *natural-photo dataset* evaluation. It does not
attempt automatic object naming, new object tracking, 3D, causal prediction,
CanonialSpine event creation, training, model promotion or database writes.

## Acceptance contract

An operator supplies **real natural photographs** with declared, accurate
bounding-box prompts and *separately drawn* ground truth foreground masks.
Each binary or 8-bit grayscale PNG must be exactly the same size as its source
photograph: white object, black background. Never use the predicted MobileSAM
mask as its own ground truth.

A manifest (schema `hex.real_photo_benchmark.v38`) groups 1 to 25 scenes.
Every scene includes an origin-group declaration. Exact image duplicates are
blocked even when relabeled. A source-group may not be reused across
train/test/validation. A minimum of 10 distinct source groups is a **candidate
benchmark gate, not proof** of independent or representative sampling. No
near-duplicate, semantic leakage, annotation accuracy or data ownership
is independently attested.

The first photo remains a **single-scene exploratory check**. No percentage
measured there is a quality guarantee for the world model.

## Start on Windows — ONE physical PowerShell line per command

From HEX-CORTEX root:

~~~powershell
git fetch origin
git switch -c feature/v38-real-photo-benchmark --track origin/feature/v38-real-photo-benchmark
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
$env:OMP_NUM_THREADS = "4"
$env:MKL_NUM_THREADS = "4"
$WeightSHA = (Get-FileHash ".\weights\mobile_sam.pt" -Algorithm SHA256).Hash.ToLowerInvariant()
if($WeightSHA -ne "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"){throw "Unexpected weights hash; STOP"}
& $VP -m pytest -q tests/test_cortex_real_cpu_smoke_v37.py tests/test_cortex_real_photo_benchmark_v38.py
& $VP -m ruff check .
~~~

Create directories if needed (these are operator-authorized local artifacts, NOT committed):

~~~powershell
New-Item -ItemType Directory -Force -Path images,masks,research/v38_real_photos | Out-Null
~~~

Copy your own *previously unseen* image to `images/novel_photo01.png`.
Use a graphics editor to manually draw its **reference** object mask into
`masks/novel_photo01_object1.png`; keep exact same pixel dimensions.
Choose one precise box within source-image dimensions and set its actual
coordinates in the manifest. Example sizes below are **placeholders** and must
be replaced. Record which original capture session produced the photo.

~~~powershell
& $VP -c "from PIL import Image; im=Image.open('images/novel_photo01.png'); print('source size',im.size); ref=Image.open('masks/novel_photo01_object1.png'); print('reference size',ref.size,'mode',ref.mode)"
~~~

Create a real photo manifest (single PowerShell command; CHANGE box/paths/labels to your actual photo):

~~~powershell
@{schema='hex.real_photo_benchmark.v38'; samples=@(@{scene_id='scene001';source_kind='operator_real_photo';source_group='photo_session001';split='test';image='images/novel_photo01.png';objects=@(@{object_id='object1';box=@(20,20,180,180);reference_mask='masks/novel_photo01_object1.png'})})} | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 research/v38_real_photos/manifest.json
~~~

Note: `Set-Content -Encoding UTF8` on Windows PowerShell 5.1 writes a UTF-8 BOM, and Python's strict `utf-8` JSON reader may reject it. For Windows PowerShell 5.1, create the manifest using the BOM-free one-line alternative:

~~~powershell
$manifest = @{schema='hex.real_photo_benchmark.v38';samples=@(@{scene_id='scene001';source_kind='operator_real_photo';source_group='photo_session001';split='test';image='images/novel_photo01.png';objects=@(@{object_id='object1';box=@(20,20,180,180);reference_mask='masks/novel_photo01_object1.png'})})} | ConvertTo-Json -Depth 8; [System.IO.File]::WriteAllText((Join-Path (Get-Location) 'research/v38_real_photos/manifest.json'), $manifest, (New-Object System.Text.UTF8Encoding($false)))
~~~

Before loading weights, preflight the manifest, file existence, dimensions,
source groups and exact hash duplication (explicit file read, **no model load**):

~~~powershell
& $VP -m hex_cortex.memory.cortex_real_photo_benchmark_cli_v38 --manifest research/v38_real_photos/manifest.json --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --approve-read --preflight-only
~~~

When the preflight says `manifest_preflight_pass`, run the real CPU model on
your photo with independently drawn reference mask and return JSON to the console:

~~~powershell
& $VP -m hex_cortex.memory.cortex_real_photo_benchmark_cli_v38 --manifest research/v38_real_photos/manifest.json --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --approve-read --approve-model-load
~~~

The receipt includes per-object IoU and input/reference/predicted SHA256,
a mean/min IoU, P50/P95 *per-photo wall time including model reload*,
and split-provenance diagnostics. `files_written=false`; don't confuse
that latency with repeated-warm-model forward time. V38 itself does not export
mask images: use V36-A's explicitly gated `--export-dir` for visual inspection.

## Phase two

Collect at least ten genuinely distinct capture sources, diverse backgrounds,
occlusion, scales and classes, annotated by a human not using MobileSAM's output
as the target. Confirm mask quality and no near duplicates outside code; report
failure cases, not only successful photos. Then build an independent before/after
image/action test against the V33 world model and a baseline without changing
the active V31 model. The V38 visual mask quality is separate from V33 action
prediction generalization.
