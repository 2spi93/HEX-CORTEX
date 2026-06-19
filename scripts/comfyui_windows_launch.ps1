param(
    [switch]$ForceCpu,
    [switch]$Background,
    [int]$Port = 8188
)

$ErrorActionPreference = "Stop"

$cudaAvailable = $false
try {
    $probe = python -c "import torch; print('true' if torch.cuda.is_available() else 'false')"
    $cudaAvailable = ($probe.Trim().ToLowerInvariant() -eq "true")
}
catch {
    Write-Warning "PyTorch probe failed; forcing CPU mode."
    $cudaAvailable = $false
}

$launchArgs = @("--recent", "launch")
if ($Background) {
    $launchArgs += "--background"
}

$comfyArgs = @("--listen", "127.0.0.1", "--port", "$Port", "--disable-api-nodes")
if ($ForceCpu -or -not $cudaAvailable) {
    Write-Host "Launching ComfyUI in CPU mode on 127.0.0.1:$Port"
    $comfyArgs = @("--cpu") + $comfyArgs
}
else {
    Write-Host "CUDA is available; launching ComfyUI with GPU acceleration on 127.0.0.1:$Port"
}

& comfy @launchArgs -- @comfyArgs
exit $LASTEXITCODE
