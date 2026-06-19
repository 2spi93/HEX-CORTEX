param(
    [string]$ProjectRoot = ".",
    [string]$ComfyRoot = "C:\Users\2spi\Documents\comfy\ComfyUI",
    [string]$ImageName = "HEX-CORTEX_00001_.png",
    [int]$SampleCount = 36,
    [int]$Seed = 42,
    [int]$HiddenDim = 128,
    [int]$Epochs = 100,
    [switch]$OperatorApproved
)

$ErrorActionPreference = "Stop"

if (-not $OperatorApproved) {
    throw "Explicit approval required. Re-run with -OperatorApproved."
}

Push-Location $ProjectRoot
try {
    $ProjectRootResolved = (Get-Location).Path
    $ImagePath = Join-Path $ComfyRoot "output\$ImageName"
    $StateRoot = Join-Path $ProjectRootResolved ".hex-cortex\world-model"
    $Dataset = Join-Path $StateRoot "transitions.jsonl"
    $Manifest = Join-Path $StateRoot "manifest.json"
    $Plan = Join-Path $StateRoot "plan.json"
    $CandidateDir = Join-Path $StateRoot "candidate"
    $CandidateManifest = Join-Path $CandidateDir "candidate.json"
    $RegistryDir = Join-Path $StateRoot "registry"
    $ActiveRegistry = Join-Path $RegistryDir "active.json"

    if (-not (Test-Path $ImagePath)) {
        throw "Base image not found: $ImagePath"
    }

    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null

    Write-Host "[1/8] Architecture audit"
    hexcortex-world-train audit --project-root $ProjectRootResolved --state-root (Join-Path $ProjectRootResolved ".hex-cortex")
    if ($LASTEXITCODE -ne 0) { throw "Architecture audit failed." }

    Write-Host "[2/8] Controlled transition bootstrap ($SampleCount samples)"
    python scripts\bootstrap_controlled_transitions.py `
        $ImagePath `
        --comfy-root $ComfyRoot `
        --dataset-jsonl $Dataset `
        --count $SampleCount `
        --seed $Seed `
        --device cpu `
        --operator-approved
    if ($LASTEXITCODE -ne 0) { throw "Controlled transition bootstrap failed." }

    Write-Host "[3/8] Dataset manifest"
    hexcortex-world-train manifest `
        $Dataset `
        --output $Manifest `
        --min-train 8 `
        --min-validation 2 `
        --min-test 2
    if ($LASTEXITCODE -ne 0) { throw "Dataset manifest is not allowed." }

    Write-Host "[4/8] Bounded training plan"
    hexcortex-world-train plan `
        $Manifest `
        --hidden-dim $HiddenDim `
        --epochs $Epochs `
        --batch-size 8 `
        --learning-rate 0.001 `
        --weight-decay 0.0001 `
        --seed $Seed `
        --device cpu `
        --max-seconds 1800 `
        --output $Plan
    if ($LASTEXITCODE -ne 0) { throw "Training plan failed." }

    Write-Host "[5/8] Compact predictor training"
    hexcortex-world-train train `
        $Manifest `
        $Plan `
        --comfy-root $ComfyRoot `
        --output-dir $CandidateDir `
        --model-ref facebook/dinov2-base `
        --pooling cls `
        --device cpu `
        --operator-approved
    if ($LASTEXITCODE -ne 0) { throw "Training failed." }

    if (-not (Test-Path $CandidateManifest)) {
        throw "Candidate manifest missing: $CandidateManifest"
    }
    $Candidate = Get-Content -Raw $CandidateManifest | ConvertFrom-Json

    Write-Host "[6/8] Promotion gate"
    if ($Candidate.promotion_allowed -ne $true) {
        Write-Warning "Candidate trained but not promotable. It has been retained for analysis."
        Write-Host "Promotion blockers: $($Candidate.promotion_blockers -join ', ')"
        hexcortex-world-train audit --project-root $ProjectRootResolved --state-root (Join-Path $ProjectRootResolved ".hex-cortex")
        exit 3
    }

    hexcortex-world-train promote `
        $CandidateManifest `
        --registry-dir $RegistryDir `
        --operator-approved
    if ($LASTEXITCODE -ne 0) { throw "Promotion failed." }

    Write-Host "[7/8] Active predictor smoke prediction"
    hexcortex-world-train predict `
        $ActiveRegistry `
        $ImagePath `
        --comfy-root $ComfyRoot `
        --action "0.25,0,0,0" `
        --model-ref facebook/dinov2-base `
        --pooling cls `
        --device cpu
    if ($LASTEXITCODE -ne 0) { throw "Active predictor smoke test failed." }

    Write-Host "[8/8] Final completion audit"
    hexcortex-world-train audit `
        --project-root $ProjectRootResolved `
        --state-root (Join-Path $ProjectRootResolved ".hex-cortex")
    if ($LASTEXITCODE -ne 0) { throw "Final audit failed." }

    Write-Host "World-model lab cycle completed and active predictor registered."
}
finally {
    Pop-Location
}
