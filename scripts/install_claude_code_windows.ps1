param(
    [ValidateSet("native", "winget", "npm")]
    [string]$Method = "native",

    [ValidateSet("stable", "latest")]
    [string]$Channel = "stable",

    [switch]$SkipDoctor
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[HEX-CORTEX] $Message" -ForegroundColor Cyan
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

if ($Method -eq "native") {
    Write-Step "Installing Claude Code from Anthropic's native Windows installer ($Channel channel)..."
    $installer = Invoke-RestMethod "https://claude.ai/install.ps1"
    if ($Channel -eq "latest") {
        & ([scriptblock]::Create($installer)) latest
    }
    else {
        & ([scriptblock]::Create($installer)) stable
    }
}
elif ($Method -eq "winget") {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is not available. Use -Method native or install App Installer first."
    }
    Write-Step "Installing Claude Code with WinGet..."
    winget install --id Anthropic.ClaudeCode --exact --accept-package-agreements --accept-source-agreements
}
else {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm is not available. Install Node.js 18+ or use -Method native."
    }
    Write-Step "Installing Claude Code with npm..."
    npm install -g @anthropic-ai/claude-code@latest
}

Refresh-ProcessPath

$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    $nativePath = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path (Join-Path $nativePath "claude.exe")) {
        $env:Path = "$nativePath;$env:Path"
        $claude = Get-Command claude -ErrorAction SilentlyContinue
    }
}

if (-not $claude) {
    throw "Claude Code was installed but 'claude' is not visible in this PowerShell session. Close and reopen PowerShell, then run: claude --version"
}

Write-Step "Claude Code detected at $($claude.Source)"
claude --version

if (-not $SkipDoctor) {
    Write-Step "Running claude doctor..."
    claude doctor
}

Write-Step "Installation complete. From the HEX-CORTEX repository, run: claude"
