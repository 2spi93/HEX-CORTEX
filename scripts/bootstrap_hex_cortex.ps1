[CmdletBinding()]
param(
    [string]$Branch = "screen-lab-policy-v2",
    [switch]$RunTests,
    [switch]$InstallVision
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is not available on PATH"
}

$Dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect git status"
}
if ($Dirty) {
    throw "Working tree is not clean. Commit, discard, or manually stash changes before bootstrap."
}

git fetch origin
if ($LASTEXITCODE -ne 0) {
    throw "git fetch origin failed"
}

$LocalBranch = git branch --list $Branch
if ($LocalBranch) {
    git switch $Branch
} else {
    git switch --track -c $Branch "origin/$Branch"
}
if ($LASTEXITCODE -ne 0) {
    throw "Unable to switch to $Branch"
}

git pull --ff-only origin $Branch
if ($LASTEXITCODE -ne 0) {
    throw "Fast-forward pull failed for $Branch"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
}
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment creation failed"
}

& $VenvPython -m pip install --upgrade pip
$InstallTarget = if ($InstallVision) { ".[dev,vision]" } else { ".[dev]" }
& $VenvPython -m pip install -e $InstallTarget
if ($LASTEXITCODE -ne 0) {
    throw "Editable installation failed"
}

$Doctor = Join-Path $ProjectRoot ".venv\Scripts\hexcortex-doctor.exe"
if (-not (Test-Path $Doctor)) {
    throw "hexcortex-doctor was not generated; package metadata is not aligned"
}

& $Doctor --project-root . --expected-branch $Branch --collect-tests --pretty
if ($LASTEXITCODE -ne 0) {
    throw "HEX-CORTEX environment doctor reported blockers"
}

if ($RunTests) {
    & $VenvPython -m ruff check .
    if ($LASTEXITCODE -ne 0) {
        throw "Ruff failed"
    }
    & $VenvPython -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw "Pytest failed"
    }
}

Write-Host "HEX-CORTEX bootstrap complete on branch $Branch" -ForegroundColor Green
