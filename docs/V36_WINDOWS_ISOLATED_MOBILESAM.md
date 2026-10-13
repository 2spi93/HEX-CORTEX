# HEX-CORTEX — V36 MobileSAM CPU environment on Windows (optional)

**Safety:** Run in PowerShell in the HEX-CORTEX repo root **after switching to V36-C integrated evaluation branch**. CPU only. This setup creates a **second, isolated virtual environment** in `%LOCALAPPDATA%`; it does NOT change your established `.venv`, DINOv2 or world-model checkpoint. It downloads/install third-party software and weights **only when the operator runs the respective commands**. Inspect the source/license before executing it. Pinning hashes prevents accidental changes but is not a safety or authenticity certificate. Never run GPU benchmarks on the unstable RX 6700 XT.

Primary sources: https://github.com/ChaoningZhang/MobileSAM, https://pytorch.org/get-started/previous-versions/

The official MobileSAM setup.py declares **no runtime install_requires**, but actual `tiny_vit_sam.py` imports `timm`; therefore provide it explicitly. No need for full `[all]` visualization/server stack. A 2026 verified upstream weight object is `weights/mobile_sam.pt`, Git blob object id `7ef2d090979fd9853adf17b7a99c8b94a1c5a6a7`, 40,728,226 bytes. Git blob SHA-1 identity plus locally computed SHA-256 must be recorded. If upstream changes, stop and review, do not disable the integrity check.

## One **physical PowerShell command per line**

Create isolated Python environment, install matching official CPU-only PyTorch wheels and local project in editable mode:

~~~powershell
python -m venv "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36"
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pip install --upgrade pip
& $VP -m pip install "torch==2.12.0" "torchvision==0.27.0" --index-url https://download.pytorch.org/whl/cpu
& $VP -m pip install -e ".[dev]" "Pillow>=10,<13" "numpy" "timm==0.9.16"
$MobileSAMRev = (git ls-remote https://github.com/ChaoningZhang/MobileSAM.git HEAD).Split()[0]
$MobileSAMRev
& $VP -m pip install --no-deps "git+https://github.com/ChaoningZhang/MobileSAM.git@$MobileSAMRev"
& $VP -c "import torch,mobile_sam; print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'SAM models',list(mobile_sam.sam_model_registry))"
~~~

If the above produces a CUDA-capable environment or any import error, **stop before loading weights**. Source install requires network access and executes third-party Python installation code. Pin the returned commit and review it before long-term deployment.

Fetch the official *versioned* checkpoint and compare the bytes with the Git upstream blob identity:

~~~powershell
New-Item -ItemType Directory -Force -Path weights | Out-Null
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/$MobileSAMRev/weights/mobile_sam.pt" -OutFile ".\weights\mobile_sam.pt"
if((git hash-object ".\weights\mobile_sam.pt").Trim() -ne "7ef2d090979fd9853adf17b7a99c8b94a1c5a6a7"){throw "Unexpected MobileSAM checkpoint blob: STOP"}
$WeightSHA = (Get-FileHash ".\weights\mobile_sam.pt" -Algorithm SHA256).Hash.ToLowerInvariant()
$WeightSHA
~~~

`*.pt` is already git-ignored. The file is ~40.7 MB; no checkpoint should be committed to Git.

Operator-selected **real image** must be saved in-project, for example `images\novel_scene.png`. First inspect its actual pixel dimensions before specifying bounding boxes. This is a human prompted segmentation experiment, **not** an automatic object-recognition demonstration.

~~~powershell
& $VP -c "from PIL import Image; im=Image.open('images/novel_scene.png'); print(im.size)"
& $VP -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/novel_scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --box cup=10,10,100,100 --dry-run
& $VP -m hex_cortex.memory.cortex_cpu_segmentation_cli_v36 --image images/novel_scene.png --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --box cup=10,10,100,100 --approve-read --approve-model-load
~~~

**Replace** box with pixel coordinates for your real chosen object. If the right/lower coordinate exceeds the dimensions, the operation must reject; **do not** treat that as a model failure. Loading may take time on CPU. Genuine score claims require operator-supplied hand-drawn masks and independent scenes; one successful inference only verifies functioning software.

For separate V35 RGBA visible-only compositing and V36-C object receipt join, follow `docs/V36_CPU_MOBILESAM_SEGMENTATION.md` and `docs/V36_INTEGRATED_CPU_SCENE.md`. Never merge PRs automatically; run CI and direct CPU benchmarking first.
