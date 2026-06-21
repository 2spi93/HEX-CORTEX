# Ensure the local Ollama model runtime is up so HEX-CORTEX has model choice.
#
# Idempotent and local-only: it probes the localhost Ollama API and starts
# `ollama serve` (detached, hidden) only if nothing is already listening. It
# never mutates the repo, touches secrets, or makes a network call off-box.
# Wired as a Claude Code SessionStart hook so the operator gets model choice
# the moment a session opens, without leaving a second `serve` process behind.

$ErrorActionPreference = 'SilentlyContinue'

try {
    # Probe IPv4 explicitly: on Windows PowerShell 5.1 'localhost' resolves to
    # ::1 first, but Ollama binds 127.0.0.1, so a localhost probe falsely fails
    # and would spawn a redundant `serve`.
    Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop | Out-Null
    Write-Output 'ollama: already running'
    exit 0
} catch {
    $exe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path $exe) {
        Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden
        Write-Output 'ollama: started (serve)'
    } else {
        Write-Output "ollama: executable not found at $exe"
    }
    exit 0
}
