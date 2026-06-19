param(
    [string]$ComfyRoot = "C:\Users\2spi\Documents\comfy\ComfyUI",
    [string]$RepoId = "stable-diffusion-v1-5/stable-diffusion-v1-5",
    [string]$FileName = "v1-5-pruned-emaonly.safetensors",
    [long]$MinimumBytes = 4000000000
)

$ErrorActionPreference = "Stop"

$CheckpointDir = Join-Path $ComfyRoot "models\checkpoints"
$CheckpointFile = Join-Path $CheckpointDir $FileName
New-Item -ItemType Directory -Force -Path $CheckpointDir | Out-Null

if (Test-Path $CheckpointFile) {
    $existing = Get-Item $CheckpointFile
    if ($existing.Length -ge $MinimumBytes) {
        Write-Host "Checkpoint already present: $CheckpointFile"
        Write-Host "Size bytes: $($existing.Length)"
        exit 0
    }
    Write-Warning "Removing incomplete checkpoint: $CheckpointFile"
    Remove-Item -Force $CheckpointFile
}

$hf = Get-Command hf -ErrorAction SilentlyContinue
if ($null -ne $hf) {
    Write-Host "Downloading with the official Hugging Face CLI..."
    & hf download $RepoId $FileName --local-dir $CheckpointDir
    if ($LASTEXITCODE -ne 0) {
        throw "Hugging Face CLI download failed."
    }
}
else {
    $url = "https://huggingface.co/$RepoId/resolve/main/$FileName?download=true"
    Write-Host "Hugging Face CLI not found; falling back to curl with Schannel best-effort revocation."
    & curl.exe `
        --location `
        --fail `
        --retry 3 `
        --retry-all-errors `
        --ssl-revoke-best-effort `
        --output $CheckpointFile `
        $url
    if ($LASTEXITCODE -ne 0) {
        throw "curl download failed."
    }
}

if (-not (Test-Path $CheckpointFile)) {
    throw "Checkpoint was not created: $CheckpointFile"
}

$file = Get-Item $CheckpointFile
if ($file.Length -lt $MinimumBytes) {
    Remove-Item -Force $CheckpointFile
    throw "Downloaded checkpoint is incomplete: $($file.Length) bytes"
}

Write-Host "Checkpoint download completed."
$file | Select-Object Name, Length, FullName
