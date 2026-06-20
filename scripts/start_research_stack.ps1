param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$Start,
    [switch]$PullImages
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ComposeRoot = Join-Path $Root "deploy\research"
$ComposeFile = Join-Path $ComposeRoot "docker-compose.yml"
$EnvFile = Join-Path $ComposeRoot ".env"

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Research compose file not found: $ComposeFile"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available in PATH."
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    $Bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($Bytes)
    $Secret = [Convert]::ToHexString($Bytes).ToLowerInvariant()
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $EnvFile,
        "SEARXNG_SECRET=$Secret`n",
        $Utf8NoBom
    )
    Write-Host "Created local secret file: $EnvFile"
} else {
    Write-Host "Using existing local secret file: $EnvFile"
}

Push-Location $ComposeRoot
try {
    docker compose config | Out-Null
    Write-Host "Research compose configuration is valid."

    if ($PullImages) {
        docker compose pull
    }

    if ($Start) {
        docker compose up -d
        docker compose ps
        Write-Host "Research stack started on localhost ports 8888 and 11235."
    } else {
        Write-Host "No containers started. Re-run with -Start after review."
    }
} finally {
    Pop-Location
}
