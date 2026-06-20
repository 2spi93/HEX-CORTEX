# HEX-CORTEX: Claude Desktop Auto-Detection

## Modifications Apportées

Vous avez demandé que `hex-cortex` détecte automatiquement Claude Desktop, même si l'exécutable `claude` n'est pas dans le PATH. Voici ce qui a été fait:

### 1. Nouveau Module: `claude_detector.py`

**Emplacement**: `src/hex_cortex/memory/claude_detector.py`

Module Python complet qui cherche l'exécutable `claude` via plusieurs moyens:

- **Variables d'environnement**: `CLAUDE_BIN`
- **Fichier de configuration**: `~/.hex-cortex/claude-config.json`
- **Registre Windows**: Clés d'installation Anthropic (Windows uniquement)
- **Chemins standard**: Emplacements classiques par OS
- **PATH système**: Recherche classique dans le PATH

**Fonctions disponibles**:
- `find_claude_executable()` → `Path | None`: Localise l'exécutable
- `is_claude_available()` → `bool`: Vérifie disponibilité rapide
- `get_claude_version()` → `str | None`: Récupère la version
- `create_claude_config()` → `bool`: Crée le fichier de config
- `get_claude_path_hint()` → `str | None`: Conseil utilisateur

### 2. Mise à Jour: `cortex_runtime_probe.py`

**Emplacement**: `src/hex_cortex/memory/cortex_runtime_probe.py`

- Import du module `claude_detector`
- **Ligne 26**: Condition `claude_project_configured` devient:
  ```python
  "claude_project_configured": (root / ".mcp.json").is_file() and is_claude_available(),
  ```

Maintenant le système marque Claude comme "configuré" SEULEMENT si:
1. Le fichier `.mcp.json` existe (config MCP), ET
2. L'exécutable `claude` est réellement disponible

### 3. Script de Configuration: `configure_claude.py`

**Emplacement**: `C:\Users\2spi\HEX-CORTEX\configure_claude.py`

Script interactif qui aide l'utilisateur à:
- Vérifier si Claude est déjà disponible
- Localiser l'installation manuelle
- Valider le chemin (test de `--version`)
- Sauvegarder la configuration
- Vérifier la configuration finale

**Utilisation**:
```bash
cd C:\Users\2spi\HEX-CORTEX
python configure_claude.py
```

### 4. Fichier de Configuration: `~/.hex-cortex/claude-config.json`

**Emplacement**: `C:\Users\2spi\.hex-cortex\claude-config.json`

Pour ajouter manuellement le chemin à Claude:

```json
{
  "claude_bin": "C:\\Program Files\\Claude Desktop\\claude.exe",
  "detected_at": "2024-01-01T00:00:00Z",
  "platform": "Windows"
}
```

### 5. Documentation: `CLAUDE_SETUP.md`

**Emplacement**: `C:\Users\2spi\HEX-CORTEX\CLAUDE_SETUP.md`

Guide complet d'installation et de configuration.

## Comment Utiliser

### Scénario 1: Claude est installé normalement
- Aucune configuration nécessaire
- Le détecteur le trouvera automatiquement

### Scénario 2: Claude n'est pas dans le PATH
**Option A - Configuration auto**:
```bash
python configure_claude.py
```

**Option B - Configuration manuelle**:
Modifiez `~/.hex-cortex/claude-config.json` avec le chemin complet vers `claude.exe`

**Option C - Variable d'environnement**:
```powershell
$env:CLAUDE_BIN = "C:\Program Files\Claude Desktop\claude.exe"
```

### Scénario 3: Vérifier la détection

```python
from src.hex_cortex.memory.claude_detector import (
    find_claude_executable,
    is_claude_available
)

if is_claude_available():
    exe = find_claude_executable()
    print(f"✓ Claude trouvé: {exe}")
else:
    print("✗ Claude non trouvé")
```

## Architecture de Recherche (Windows)

```
Détection Claude Desktop (Windows)
│
├─ 1. Variable CLAUDE_BIN
├─ 2. Fichier ~/.hex-cortex/claude-config.json
├─ 3. Registre Windows (HKEY_CURRENT_USER et HKEY_LOCAL_MACHINE)
├─ 4. Chemins standards:
│   ├─ %APPDATA%\Local\Programs\Claude\claude.exe
│   ├─ %APPDATA%\Local\Claude\claude.exe
│   ├─ C:\Program Files\Claude\claude.exe
│   ├─ C:\Program Files (x86)\Claude\claude.exe
│   ├─ %APPDATA%\scoop\apps\claude\current\claude.exe
│   └─ ... (autres emplacements)
├─ 5. Commande `where claude` dans PATH
│
└─ Résultat: Path | None
```

## Points Clés

✅ **Automatique**: Cherche dans 10+ emplacements sans config
✅ **Flexible**: 5 méthodes de configuration (env var, registry, fichier, PATH, etc)
✅ **Windows-Smart**: Cherche dans le Registre Windows
✅ **Cross-platform**: Fonctionne sur Windows, macOS, Linux
✅ **Sûr**: Vérifie que le chemin existe avant de le retourner
✅ **Utile**: Fournit des conseils si non trouvé

## Fichiers Créés/Modifiés

| Fichier | Type | Action |
|---------|------|--------|
| `src/hex_cortex/memory/claude_detector.py` | NOUVEAU | Module de détection |
| `src/hex_cortex/memory/cortex_runtime_probe.py` | MODIFIÉ | Intègre la détection |
| `configure_claude.py` | NOUVEAU | Assistant interactif |
| `CLAUDE_SETUP.md` | NOUVEAU | Documentation |
| `~/.hex-cortex/claude-config.json` | NOUVEAU | Fichier config utilisateur |

## Tests

Pour tester:

```bash
# Test basique
python -c "from src.hex_cortex.memory.claude_detector import is_claude_available; print(is_claude_available())"

# Test complet avec chemin
python -c "from src.hex_cortex.memory.claude_detector import find_claude_executable; print(find_claude_executable())"

# Test de configuration
python configure_claude.py
```

## Prochaines Étapes (Optionnel)

1. **Installer Claude Desktop** si ce n'est pas déjà fait: https://claude.ai/download
2. **Exécuter configure_claude.py** pour configuration auto
3. **Ou** éditer manuellement `~/.hex-cortex/claude-config.json`
4. **Vérifier** que `cortex_runtime_probe` retourne `"claude_project_configured": true`

## Questions?

Consultez:
- `CLAUDE_SETUP.md` pour les détails complets
- `src/hex_cortex/memory/claude_detector.py` pour l'API
- `configure_claude.py` pour voir les étapes de détection
