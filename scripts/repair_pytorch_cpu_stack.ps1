param(
    [switch]$SkipComfyStop
)

$ErrorActionPreference = "Stop"

if (-not $SkipComfyStop) {
    try {
        comfy stop | Out-Null
    }
    catch {
        Write-Host "No background ComfyUI instance to stop."
    }
}

Write-Host "Current installed package versions:"
python -c "from importlib.metadata import version, PackageNotFoundError; names=['torch','torchvision','torchaudio']; [print(f'{n}=' + (version(n) if True else '')) for n in names]"

Write-Host "Removing the incompatible PyTorch family..."
python -m pip uninstall -y torch torchvision torchaudio

Write-Host "Installing a matched CPU-only trio..."
python -m pip install --no-cache-dir --force-reinstall `
  torch==2.4.1 `
  torchvision==0.19.1 `
  torchaudio==2.4.1 `
  --index-url https://download.pytorch.org/whl/cpu

Write-Host "Verifying imports and binary compatibility..."
python -c "import torch, torchvision, torchaudio; print('torch=', torch.__version__); print('torchvision=', torchvision.__version__); print('torchaudio=', torchaudio.__version__); print('cuda_available=', torch.cuda.is_available()); print('stack_ok=true')"
if ($LASTEXITCODE -ne 0) {
    throw "PyTorch stack verification failed."
}

Write-Host "PyTorch CPU stack repair completed successfully."
