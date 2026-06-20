# Script d'installation de Claude dans PowerShell
# Exécutez: powershell -ExecutionPolicy Bypass -File setup_claude_powershell.ps1

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Claude Desktop PowerShell Configuration Setup             ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Configuration
$ClaudeExe = "C:\Users\2spi\AppData\Roaming\Claude\claude-code\2.1.181\claude.exe"
$ClaudeDir = Split-Path -Parent $ClaudeExe
$ProfilePath = $PROFILE.CurrentUserCurrentHost
$ProfileDir = Split-Path -Parent $ProfilePath

Write-Host "Configuration détectée:" -ForegroundColor Yellow
Write-Host "  Claude Exe: $ClaudeExe"
Write-Host "  Claude Dir: $ClaudeDir"
Write-Host "  PowerShell Profile: $ProfilePath"
Write-Host ""

# Vérifier que Claude existe
if (-not (Test-Path -LiteralPath $ClaudeExe)) {
    Write-Host "ERREUR: Claude Code introuvable à $ClaudeExe" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Claude Code trouvé" -ForegroundColor Green

# Étape 1: Ajouter au PATH utilisateur
Write-Host ""
Write-Host "Étape 1: Ajouter Claude au PATH utilisateur..." -ForegroundColor Yellow

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$UserParts = @(
    $UserPath -split ";" |
    Where-Object {
        $_ -and $_ -ne $ClaudeDir
    }
)

[Environment]::SetEnvironmentVariable(
    "Path",
    (($UserParts + $ClaudeDir) -join ";"),
    "User"
)
Write-Host "✓ Claude ajouté au PATH utilisateur" -ForegroundColor Green

# Étape 2: Mettre à jour PATH pour la session actuelle
Write-Host ""
Write-Host "Étape 2: Mettre à jour le PATH de la session actuelle..." -ForegroundColor Yellow

$CurrentParts = @($env:Path -split ";" | Where-Object { $_ })
if ($CurrentParts -notcontains $ClaudeDir) {
    $env:Path = "$ClaudeDir;$env:Path"
}
Write-Host "✓ PATH de la session mis à jour" -ForegroundColor Green

# Étape 3: Créer/Mettre à jour le PowerShell Profile
Write-Host ""
Write-Host "Étape 3: Créer/Mettre à jour le PowerShell Profile..." -ForegroundColor Yellow

if (-not (Test-Path -LiteralPath $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
    Write-Host "✓ Répertoire du profil créé" -ForegroundColor Green
}

if (Test-Path -LiteralPath $ProfilePath) {
    Write-Host "! Profile existant détecté" -ForegroundColor Yellow
    $backup = "$ProfilePath.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item -Path $ProfilePath -Destination $backup
    Write-Host "  Sauvegarde créée: $backup" -ForegroundColor Gray
}

# Créer le nouveau profile
$profileContent = @'
# PowerShell Profile - HEX-CORTEX & Claude Setup
# Ce fichier se charge automatiquement au démarrage de PowerShell

# ============================================================================
# Claude Desktop Setup
# ============================================================================

$ClaudeExe = "C:\Users\2spi\AppData\Roaming\Claude\claude-code\2.1.181\claude.exe"
$ClaudeDir = Split-Path -Parent $ClaudeExe

if (Test-Path -LiteralPath $ClaudeExe) {
    # Ajouter au PATH si pas déjà présent
    $CurrentPath = $env:Path -split ";"
    if ($CurrentPath -notcontains $ClaudeDir) {
        $env:Path = "$ClaudeDir;$env:Path"
    }
    
    # Alias pour accès facile
    Set-Alias -Name claude -Value $ClaudeExe -Force
}

# ============================================================================
# HEX-CORTEX Setup
# ============================================================================

$HexCortexRoot = "C:\Users\2spi\HEX-CORTEX"
if (Test-Path -LiteralPath $HexCortexRoot) {
    # Fonction pour activer l'environnement virtuel
    function Use-HexCortex {
        Set-Location $HexCortexRoot
        if (Test-Path ".venv\Scripts\Activate.ps1") {
            & ".\.venv\Scripts\Activate.ps1"
            Write-Host "HEX-CORTEX environment activated" -ForegroundColor Green
        }
    }
}

# ============================================================================
# Message de démarrage
# ============================================================================

Write-Host "PowerShell Profile Loaded - Claude and HEX-CORTEX ready" -ForegroundColor Green
'@

$profileContent | Out-File -LiteralPath $ProfilePath -Encoding UTF8 -Force
Write-Host "✓ PowerShell Profile créé/mis à jour" -ForegroundColor Green

# Étape 4: Vérifier que Claude fonctionne
Write-Host ""
Write-Host "Étape 4: Vérifier que Claude fonctionne..." -ForegroundColor Yellow

try {
    $version = & $ClaudeExe "--version" 2>&1
    if ($version) {
        Write-Host "✓ Claude fonctionne: $version" -ForegroundColor Green
    }
}
catch {
    Write-Host "! Impossible de vérifier Claude: $_" -ForegroundColor Yellow
}

# Résumé
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  Configuration Terminée                                    ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaines étapes:" -ForegroundColor Yellow
Write-Host "  1. Fermez et rouvrez PowerShell"
Write-Host "  2. Testez: claude --version"
Write-Host "  3. HEX-CORTEX: Use-HexCortex"
Write-Host ""
