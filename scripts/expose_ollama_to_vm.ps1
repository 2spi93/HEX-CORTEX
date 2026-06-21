# One-time, operator-run setup: expose the host Ollama to a VMware guest
# (e.g. the Kali / Hermes VM) so the brain benchmark can run against the host's
# GPU-accelerated model over the VM network -- WITHOUT GPU passthrough, which
# VMware Workstation does not support and which would only steal the GPU from
# the host that is already serving Ollama at 100% GPU.
#
# Local config only. It sets the persistent OLLAMA_HOST user env var and
# restarts Ollama so it rebinds. It deliberately does NOT open the Windows
# firewall: that needs admin and is left to a narrowly scoped, operator-run
# command printed at the end. Until you add that rule, binding to 0.0.0.0 stays
# blocked from the LAN by the default inbound-deny policy, so nothing is exposed
# beyond localhost yet.

param(
    [string]$Bind = '0.0.0.0:11434'
)

$ErrorActionPreference = 'Stop'

Write-Output "Setting OLLAMA_HOST=$Bind (User scope, persistent across reboots)..."
[Environment]::SetEnvironmentVariable('OLLAMA_HOST', $Bind, 'User')
$env:OLLAMA_HOST = $Bind

Write-Output 'Restarting Ollama so it rebinds to the new address...'
Get-Process 'ollama', 'ollama app' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
$app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
$cli = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (Test-Path $app) {
    Start-Process -FilePath $app
} elseif (Test-Path $cli) {
    Start-Process -FilePath $cli -ArgumentList 'serve' -WindowStyle Hidden
} else {
    Write-Output 'ollama executable not found; install Ollama first.'
    exit 1
}
Start-Sleep -Seconds 4

Write-Output ''
Write-Output 'Now listening on:'
Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort | Format-Table -AutoSize | Out-String | Write-Output

# Discover VMware host-side IPs so the firewall rule (and the VM endpoint) can be
# scoped to exactly those subnets instead of the whole network.
$vmnet = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceAlias -like '*VMnet*' -or $_.InterfaceAlias -like '*VMware*' }

if ($vmnet) {
    $subnets = $vmnet | ForEach-Object { ($_.IPAddress -replace '\.\d+$', '.0') + '/24' } | Select-Object -Unique
    $remote = ($subnets -join "','")
    Write-Output '=== NEXT (run once in an ADMIN shell): allow ONLY the VMware subnets through the firewall ==='
    Write-Output "New-NetFirewallRule -DisplayName 'Ollama from VMware' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 11434 -RemoteAddress @('$remote')"
    Write-Output ''
    Write-Output '=== From the Kali / Hermes VM, point the benchmark at the host ==='
    foreach ($n in $vmnet) {
        Write-Output "  python scripts/bench_brain.py --api ollama --endpoint http://$($n.IPAddress):11434"
    }
} else {
    Write-Output 'No VMware virtual adapters found; start VMware (or its network service) first.'
}
