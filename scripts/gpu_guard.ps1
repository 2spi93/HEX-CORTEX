<#
.SYNOPSIS
  HEX-CORTEX GPU guard — watch the accelerator and stop before overload.

.DESCRIPTION
  The sensor + actuator layer for the GPU governor. It reads real metrics
  (Ollama /api/ps for resident-model VRAM, the Windows \GPU Adapter Memory
  Dedicated Usage counter for total VRAM in use, GPU engine utilization),
  hands them to the pure governor via the probe CLI, and prints the decision.

  With -Enforce, if the governor returns defer/reject or recommends reclaiming
  memory (VRAM heading toward the "screen turns all green" TDR crash), the guard
  unloads Ollama models (keep_alive 0) to bring VRAM back down. Single shot by
  default; -Watch loops every -IntervalSeconds. This is operator-invoked tooling,
  not an autonomous scheduler.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gpu_guard.ps1
  powershell ... -File scripts/gpu_guard.ps1 -Tier large -Enforce -Watch
#>
[CmdletBinding()]
param(
  [ValidateSet('small','large')] [string] $Tier = 'small',
  [switch] $IsBenchmark,
  [switch] $Enforce,
  [switch] $Watch,
  [int] $IntervalSeconds = 15,
  [double] $TotalVramMb = 12288.0,
  [string] $Endpoint = 'http://127.0.0.1:11434'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

function Get-DedicatedVramMb {
  try {
    $samples = (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction Stop).CounterSamples
    $max = ($samples | Measure-Object -Property CookedValue -Maximum).Maximum
    return [math]::Round($max / 1MB, 1)
  } catch { return $null }
}

function Get-GpuUtilization {
  try {
    $samples = (Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop).CounterSamples
    return [math]::Round(($samples | Measure-Object -Property CookedValue -Maximum).Maximum, 1)
  } catch { return 0.0 }
}

function Invoke-GpuAssessment {
  $psFile = Join-Path $env:TEMP ("hexcortex_ollama_ps_{0}.json" -f $PID)
  try {
    $ps = Invoke-RestMethod -Uri "$Endpoint/api/ps" -TimeoutSec 8
    ($ps | ConvertTo-Json -Depth 6) | Out-File -FilePath $psFile -Encoding utf8
  } catch {
    '{"models": []}' | Out-File -FilePath $psFile -Encoding utf8
  }
  $dedicated = Get-DedicatedVramMb
  $util = Get-GpuUtilization

  $inv = [System.Globalization.CultureInfo]::InvariantCulture
  $cliArgs = @('-m','hex_cortex.memory.cortex_gpu_probe_cli',
    '--ollama-ps', $psFile,
    '--total-mb', $TotalVramMb.ToString($inv),
    '--gpu-util', $util.ToString($inv),
    '--tier', $Tier)
  if ($null -ne $dedicated) { $cliArgs += @('--dedicated-mb', $dedicated.ToString($inv)) }
  if ($IsBenchmark) { $cliArgs += '--is-benchmark' }

  Push-Location $repo
  try { $out = & $python @cliArgs; $code = $LASTEXITCODE } finally { Pop-Location }
  Remove-Item $psFile -ErrorAction SilentlyContinue

  $decision = ($out | ConvertFrom-Json).decision
  $usedMb = ($out | ConvertFrom-Json).snapshot.vram_used_mb
  $pct = [math]::Round(100.0 * $usedMb / $TotalVramMb, 1)
  Write-Host ("[gpu-guard] VRAM {0}/{1} MB ({2}%) util {3}% -> {4} ({5})" -f `
    $usedMb, $TotalVramMb, $pct, $util, $decision.action, ($decision.reasons -join ','))

  if ($Enforce -and ($decision.recommend_unload_idle -or $decision.action -in @('defer','reject'))) {
    Write-Host "[gpu-guard] reclaiming VRAM: unloading resident models (keep_alive=0)" -ForegroundColor Yellow
    try {
      $loaded = (Invoke-RestMethod -Uri "$Endpoint/api/ps" -TimeoutSec 8).models
      foreach ($m in $loaded) {
        $body = @{ model = $m.name; keep_alive = 0; prompt = '' } | ConvertTo-Json
        Invoke-RestMethod -Uri "$Endpoint/api/generate" -Method Post -TimeoutSec 15 -Body $body -ContentType 'application/json' | Out-Null
      }
    } catch { Write-Host "[gpu-guard] unload failed: $_" -ForegroundColor Red }
  }
  return $code
}

if ($Watch) {
  Write-Host "[gpu-guard] watching every $IntervalSeconds s (Ctrl+C to stop)"
  while ($true) { Invoke-GpuAssessment | Out-Null; Start-Sleep -Seconds $IntervalSeconds }
} else {
  exit (Invoke-GpuAssessment)
}
