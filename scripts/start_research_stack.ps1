param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$Start,
    [switch]$PullImages,
    [int]$ReadyTimeoutSeconds = 90
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ComposeRoot = Join-Path $Root "deploy\research"
$ComposeFile = Join-Path $ComposeRoot "docker-compose.yml"
$EnvFile = Join-Path $ComposeRoot ".env"
$SearxngProbe = "http://127.0.0.1:8888/search?q=health&format=json&language=all&safesearch=1&categories=general"

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Research compose file not found: $ComposeFile"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available in PATH."
}

if ($ReadyTimeoutSeconds -lt 5 -or $ReadyTimeoutSeconds -gt 600) {
    throw "ReadyTimeoutSeconds must be between 5 and 600."
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    $Bytes = New-Object byte[] 32
    $Random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $Random.GetBytes($Bytes)
    }
    finally {
        $Random.Dispose()
    }
    $Secret = ([System.BitConverter]::ToString($Bytes)).Replace("-", "").ToLowerInvariant()
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
    if ($LASTEXITCODE -ne 0) {
        throw "Research compose configuration is invalid."
    }
    Write-Host "Research compose configuration is valid."

    if ($PullImages) {
        docker compose pull
        if ($LASTEXITCODE -ne 0) {
            throw "Research image pull failed."
        }
    }

    if ($Start) {
        docker compose up -d
        if ($LASTEXITCODE -ne 0) {
            throw "Research stack startup failed."
        }
        docker compose ps

        $Deadline = [DateTime]::UtcNow.AddSeconds($ReadyTimeoutSeconds)
        $Ready = $false
        do {
            try {
                $Response = Invoke-RestMethod -Uri $SearxngProbe -Method Get -TimeoutSec 5
                if ($null -ne $Response.results) {
                    $Ready = $true
                    break
                }
            }
            catch {
                Start-Sleep -Seconds 2
            }
        } while ([DateTime]::UtcNow -lt $Deadline)

        if (-not $Ready) {
            docker compose ps
            throw "SearXNG did not expose a JSON search endpoint within $ReadyTimeoutSeconds seconds."
        }

        Write-Host "Research stack started and SearXNG JSON API is ready on 127.0.0.1:8888."
        Write-Host "Crawl4AI container is bound to 127.0.0.1:11235."
    } else {
        Write-Host "No containers started. Re-run with -Start after review."
    }
} finally {
    Pop-Location
}
