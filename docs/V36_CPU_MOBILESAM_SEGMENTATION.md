# HEX-CORTEX V36-A — MobileSAM CPU, deliberately permission-gated

This branch adds a **real callable third-party MobileSAM CPU provider**, not model weights and not an automatic detector. It can extract a mask for each **operator-supplied bounding box** and compare masks with human reference PNGs. The existing V35 visible-only RGBA composer remains unchanged. This PR is based on draft V35 PR #39; no merge into `main` yet.

## Operator prerequisites

1. Use a separate, trusted optional Python environment; install a compatible CPU PyTorch/torchvision, NumPy, Pillow and audited MobileSAM code from the [official repository](https://github.com/ChaoningZhang/MobileSAM). Check the installed MobileSAM source/dependency versions and licensing; **do not blindly install into your functioning base environment**. See the official `sam_model_registry["vit_t"]` + `SamPredictor` API.
2. Obtain `mobile_sam.pt` from a trusted official source yourself, keep it locally inside the project root (for example `weights/mobile_sam.pt`), record/check its SHA-256 and do **not** commit the large checkpoint. A SHA-256 pin detects unexpected file changes, but **does not establish trust in the weights or loader**. Some PyTorch model loaders can deserialize unsafe checkpoint formats: audit provenance and loader before explicitly granting `--approve-model-load`.
3. Supply a real image under the repo, plus one or more accurately measured bounding boxes in **pixel coordinates** (`x1,y1,x2,y2`, half-open). A box is not semantic object detection. A separate human-drawn same-sized grayscale PNG may be supplied to measure IoU.
4. Do not use the crashing RX 6700 XT. The provider sets `device=cpu` and `eval()`, performs no downloads and does not write by default.

## One physical PowerShell line per command

On your original V35 local branch, don't lose untracked receipts or personal files. Fetch, then switch to this opt-in branch:

~~~powershell
git fetch origin
git switch -c feature/v36-cpu-mobilesam-gated --track origin/feature/v36-cpu-mobilesam-gated
python -m pytest -q tests/test_cortex_cpu_segmentation_v36.py
ruff check .
~~~

Dry-run — cannot read files or load a model:

~~~powershell
python -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 0000000000000000000000000000000000000000000000000000000000000000 --box cup=10,10,100,100 --dry-run
~~~

Measure your **actual locally trusted** model checksum first, and substitute real paths/coordinates:

~~~powershell
(Get-FileHash .\weights\mobile_sam.pt -Algorithm SHA256).Hash.ToLowerInvariant()
~~~

Example real CPU inference, read-only, without saving masks (replace hash and pixel boxes):

~~~powershell
python -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 REPLACE_WITH_64_HEX --box cup=10,10,100,100 --approve-read --approve-model-load
~~~

Optional measured human reference mask:

~~~powershell
python -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 REPLACE_WITH_64_HEX --box cup=10,10,100,100 --reference-mask cup=masks/cup_truth.png --approve-read --approve-model-load
~~~

Only when you want to feed V35 with actual V36 masks, use **a new** in-project output folder. It must have an existing parent directory and cannot already exist.

~~~powershell
python -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 REPLACE_WITH_64_HEX --box cup=10,10,100,100 --export-dir outputs/v36-sample-001 --approve-read --approve-model-load --approve-write
~~~

Then recompose using the existing V35 path:

~~~powershell
python -m hex_cortex.memory.cortex_object_layers_cli_v35 --project-root . --image images/scene.png --mask cup=outputs/v36-sample-001/cup.png --approve-read
~~~

The CPU receipt reports image/checkpoint digests, provider type, boxes, per-mask content hash, foreground pixels, IoU (when reference supplied), wall-clock inference time and explicit booleans. It **does not** prove independently validated visual understanding, latency distributions, memory peaks, automatic object naming or physical causality. Fake injected predictor unit tests are not real MobileSAM tests; actual local inference remains a required milestone. 

Next: measured multiscene benchmark with independent annotations, optional Florence-2 detection provider, exact V35 recomposition and eventual V36-B metadata contract (PR #41). Keep provider source and model weights distinct from the active DINOv2/world-model checkpoint.
