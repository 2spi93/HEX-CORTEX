# HEX-CORTEX V37 — First REAL MobileSAM CPU smoke (synthetic, non-independent)

The operator on Windows 11 already established:
- PyTorch 2.12.0+cpu, torchvision 0.27.0+cpu, MobileSAM 1.0 installed at git commit `f706ad9c4eb7f219c00d9050e46328518ffb65d2`;
- `torch.cuda.is_available() == False`, model registry includes `vit_t`;
- a checkpoint at `weights/mobile_sam.pt` matches official upstream Git blob `7ef2d090979fd9853adf17b7a99c8b94a1c5a6a7`;
- its **operator-reported** SHA256 is `6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f`.

These are operator observations, **not yet independently repeated by the V37 smoke**.

## V37 test intent

Smoke only: automatically create a small *synthetic* ellipse + background distractor, plus its ground-truth binary mask, inside an operator-approved temporary folder, then execute the real MobileSAM `vit_t` predictor using a bounding-box prompt on CPU. Compare foreground IoU against synthetic ground truth. Always delete temp scene/mask on normal exit or caught exceptions. No weights overwrite, no automatic internet access, no DINOv2 load, no GPU.

This smoke is a technical proof of execution, not evidence of natural-image generalization, automatic detection, classification, 3D reasoning, or longitudinal object tracking. A low IoU on synthetic geometry is not sufficient evidence of a general MobileSAM failure. Model-load time is included in this one-shot latency; it is not steady-state P50/P95.

## ONE physical PowerShell line per command

Run in project root, from an existing local branch; preserve untracked user files:

~~~powershell
git fetch origin
git switch -c feature/v37-real-cpu-smoke-evidence --track origin/feature/v37-real-cpu-smoke-evidence
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
$WeightSHA = (Get-FileHash ".\weights\mobile_sam.pt" -Algorithm SHA256).Hash.ToLowerInvariant()
if($WeightSHA -ne "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"){throw "Unexpected MobileSAM checkpoint SHA: STOP"}
& $VP -m pytest -q tests/test_cortex_real_cpu_smoke_v37.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_real_cpu_smoke_cli_v37 --project-root . --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --dry-run
& $VP -m hex_cortex.memory.cortex_real_cpu_smoke_cli_v37 --project-root . --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --approve-read --approve-model-load --approve-temp-write
~~~

Read the last JSON receipt carefully:
- `status=synthetic_smoke_executed` and `actual_mobile_sam_inference_called=true` means a real provider attempt executed through the source (as reported locally). It does **not** demonstrate independent model authenticity or visual generalization.
- `synthetic_reference_iou` reflects just this generated image and exact reference mask.
- `checkpoint_modified=false` and `files_persisted=false`: source code does not alter checkpoint and uses an ephemeral image+mask.
- On `status=blocked`, stop and inspect `reason`; do not disable the SHA check or switch to GPU.

## After successful smoke: actual photograph

Choose a photo of **two ordinary objects**, ideally one object with a clear outline. Save it locally under the HEX-CORTEX project, e.g. `images/novel_scene.png`. Record actual pixel size:

~~~powershell
& $VP -c "from PIL import Image; im=Image.open('images/novel_scene.png'); print('size:',im.size)"
~~~

Choose bounding box x1,y1,x2,y2 **by inspecting the photo**. The following coordinates are placeholders, not guaranteed to fit:

~~~powershell
& $VP -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/novel_scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --box object1=20,20,180,180 --approve-read --approve-model-load
~~~

Run read-only first; optional mask exports and human reference IoU later. The integrated V36-C bridge needs a saved truthful JSON receipt and source_event_ids that the operator can substantiate; do not invent CanonicalSpine event IDs. Only independent, annotated scenes qualify for a generalization benchmark.

## Limits and precautions

The official MobileSAM loader `torch.load` deserializes PyTorch weights. Local checksum matching is necessary but not a trust guarantee; inspect source and provenance before approving load. The source imports `timm`, and possible duplicate TinyViT registry warnings did not prevent the operator's import. CPU-only PyTorch 2.12.0+cpu avoids the unstable RX 6700 XT. Use branch review/CI and never merge automatically.
