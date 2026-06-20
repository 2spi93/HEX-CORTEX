# Claude dans PowerShell - Configuration Complétée

## Status: ✓ CONFIGURÉ

Claude Desktop est maintenant accessible dans PowerShell.

## Modifications Apportées

### 1. PATH utilisateur (Windows)
Claude a été ajouté au PATH utilisateur de Windows:
```
C:\Users\2spi\AppData\Roaming\Claude\claude-code\2.1.181
```

**Vérification**:
```powershell
[Environment]::GetEnvironmentVariable("Path", "User")
```

### 2. PowerShell Profile Créé
**Fichier**: `C:\Users\2spi\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`

Ce fichier se charge automatiquement à chaque démarrage de PowerShell et:
- Ajoute Claude au PATH de la session
- Crée un alias `claude` pour accès facile
- Configure HEX-CORTEX avec une fonction `Use-HexCortex`
- Affiche un message de démarrage

### 3. Script Setup (Optionnel)
**Fichier**: `C:\Users\2spi\HEX-CORTEX\setup_claude_powershell.ps1`

Pour reconfigurer manuellement:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\2spi\HEX-CORTEX\setup_claude_powershell.ps1"
```

## Utilisation

### Session Actuelle
Claude est disponible immédiatement dans cette session PowerShell:
```powershell
claude --version
# Output: 2.1.181 (Claude Code)
```

### Nouvelles Sessions
À chaque nouveau PowerShell, Claude est automatiquement dans le PATH.

### Alias PowerShell
```powershell
# Utiliser claude (sans le .exe)
claude --version

# Aller à HEX-CORTEX
Use-HexCortex

# Affiche: HEX-CORTEX environment activated
```

## Fichiers Modifiés/Créés

| Chemin | Type | Contenu |
|--------|------|---------|
| `[HKEY_CURRENT_USER]\Environment\Path` | Registre Windows | Claude répertoire ajouté |
| `~/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1` | Script | Profil de démarrage PowerShell |
| `C:\Users\2spi\HEX-CORTEX\setup_claude_powershell.ps1` | Script | Setup manuel (optionnel) |

## Vérification

### Tester Claude
```powershell
claude --version
# Output: 2.1.181 (Claude Code)
```

### Tester HEX-CORTEX
```powershell
Use-HexCortex
# Output: HEX-CORTEX environment activated
# Location change: C:\Users\2spi\HEX-CORTEX
```

### Vérifier PATH
```powershell
# Vérifier le PATH utilisateur
[Environment]::GetEnvironmentVariable("Path", "User")

# Vérifier le PATH de la session
$env:Path -split ";" | Where-Object { $_ -like "*Claude*" }
```

## Prochaines Étapes

1. **Fermez et rouvrez PowerShell** pour charger le profil
2. **Testez**: `claude --version`
3. **Utilisez**: `Use-HexCortex` pour accéder au projet avec l'environnement activé

## Notes Importantes

- Le PATH a été modifié au niveau **utilisateur** (persistent à travers les redémarrages)
- Le profil PowerShell se charge automatiquement à chaque démarrage
- Si Claude met à jour sa version, vous devrez mettre à jour le chemin dans le profil
- Pour revenir à une version antérieure, consultez le fichier `.backup` du profil

## Troubleshooting

### Claude n'est pas trouvé
```powershell
# Vérifier le chemin complet
Test-Path -LiteralPath "C:\Users\2spi\AppData\Roaming\Claude\claude-code\2.1.181\claude.exe"

# Exécuter manuellement le setup
powershell -ExecutionPolicy Bypass -File "C:\Users\2spi\HEX-CORTEX\setup_claude_powershell.ps1"
```

### Profile ne se charge pas
```powershell
# Vérifier que le profil existe
Test-Path -LiteralPath $PROFILE.CurrentUserCurrentHost

# Afficher le chemin attendu
$PROFILE.CurrentUserCurrentHost

# Charger manuellement
& $PROFILE.CurrentUserCurrentHost
```

### Erreur ExecutionPolicy
```powershell
# Autoriser les scripts locaux
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

**Résumé**: Claude est maintenant accessible dans PowerShell comme une commande standard. ✓
