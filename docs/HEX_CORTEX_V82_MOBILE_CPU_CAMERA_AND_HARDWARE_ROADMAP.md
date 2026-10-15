# HEX-CORTEX V8.2 — console Android privée, caméra locale et feuille de route hardware

## Ce qui est livré sur cette branche (pas encore fusionné)

- Un **petit serveur CPU autonome**, `cortex_mobile_console_v82`, en Python standard : une interface web adaptative, états réduits, authentification HTTP Basic, liste blanche stricte de l'hôte, en-têtes anti-cache/anti-cadrage/CSP, port d'écoute **127.0.0.1 uniquement**.
- Un **aperçu caméra Android/PC** : l'opérateur clique explicitement « Autoriser la caméra ». La vidéo reste dans le navigateur. Un second clic capture une photo en mémoire locale et permet un téléchargement local ; aucune photo, vidéo ou voix n'est envoyée au PC, à GitHub ou à DeepSeek.
- Une API `GET /api/mobile/status` n'exposant que quelques booléens et l'état expurgé d'un éventuel reçu V8. Aucun historique de prompts ni données personnelles.
- Aucune route permettant de décoller, déplacer ou commander un drone ; aucune écriture dans CanonicalSpine, aucun contrôle d'un appareil distant.
- Tests et CI GitHub Actions CPU. Cette interface **n'est pas** DeepSeek connecté : la PR V8.1 atteste seulement la présence/import des paquets officiels dans un runner Ubuntu. La connexion des agents et plugins reste à faire.

### Architecture réelle

```text
Huawei P20 / Android
     navigateur HTTPS privé + auth opérateur + permission caméra
            |
         Tailscale Serve (tailnet PRIVÉ, pas Funnel)
            |
    127.0.0.1:8788 (serveur mobile limité GET)
            |
  états expurgés V8 — PAS de proxy vers /api/chat ni /api/vision/cpu/segment

     127.0.0.1:8777 — Command Center V8 sur Windows, séparé
     GitHub Actions — CI et tests SDK, pas de serveur permanent
     DeepSeek agent — pas connecté, sandbox distante requise
     Drone — aucun pilotage, simulation/lecture seule d'abord
```

## Tester gratuitement sur Windows 11, sans GPU

Arrêter uniquement les sessions de test concernées. Depuis le dépôt HEX-CORTEX :

```powershell
git fetch origin
git switch -c feature/v8-mobile-cpu-remote-console-plan --track origin/feature/v8-mobile-cpu-remote-console-plan
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_mobile_console_v82.py
& $VP -m ruff check .
```

Créer un mot de passe de **32 octets aléatoires** dans PowerShell, et le conserver hors des dépôts et des chats :

```powershell
$secretBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
$env:HEX_CORTEX_MOBILE_PASSWORD = [Convert]::ToBase64String($secretBytes)
& $VP -m hex_cortex.memory.cortex_mobile_console_v82 --project-root . --port 8788 --dry-run
& $VP -m hex_cortex.memory.cortex_mobile_console_v82 --project-root . --port 8788
```

Depuis **le navigateur du PC**, aller à `http://127.0.0.1:8788/`. La boîte de connexion HTTP Basic demande l'identifiant `operator` et le mot de passe généré. Pour obtenir le mot de passe sur ce PC, inspecter la variable PowerShell ; **ne pas le coller dans le chat ni le commit**. La caméra ne s'active qu'après clic. Arrêter avec `Ctrl+C` ; effacer la variable de l'environnement PowerShell après la session si souhaité.

## Utilisation depuis le Huawei P20 — accès privé uniquement

La console est volontairement inaccessible depuis le téléphone tant que le canal privé n'est pas configuré. `127.0.0.1` sur le P20 désigne **le téléphone**, pas le PC.

1. Installer/ouvrir **Tailscale** sur Windows et Android, connecter uniquement les appareils autorisés au même tailnet et configurer les ACL appropriées. Pour le site HTTPS privé, Tailscale demande MagicDNS et les certificats HTTPS activés.
2. Sur Windows, utiliser `tailscale serve --bg 8788` après vérification de la syntaxe avec la version installée. `tailscale serve status` affiche alors l'URL privée HTTPS, généralement `https://nom-machine.nom-tailnet.ts.net`. Ne **pas** utiliser `tailscale funnel`.
3. **Relancer** le serveur mobile en lui passant l'hôte exact indiqué par Tailscale, **sans** `https://`, par exemple :
   ```powershell
   & $VP -m hex_cortex.memory.cortex_mobile_console_v82 --project-root . --port 8788 --tailnet-host pc.mon-tailnet.ts.net
   ```
4. Depuis le P20 connecté à Tailscale, ouvrir l'URL privée HTTPS dans le navigateur ; saisir `operator` et le mot de passe. L'accès exige le tunnel privé **et** le mot de passe.
5. Autoriser la caméra au clic. La photo reste sur le P20 ; elle peut être enregistrée localement. Les navigateurs modernes exigent un **contexte sécurisé** (HTTPS ou localhost) pour `getUserMedia`. Les versions anciennes d'Android/browser peuvent limiter les options.
6. Fermer l'accès lorsque non utilisé : `tailscale serve --https=443 off` (vérifier avec `tailscale serve status`) et arrêter le serveur avec `Ctrl+C`.

**Attention au stockage du mot de passe HTTP Basic dans le navigateur :** utiliser un mot de passe dédié, unique, ne pas le réutiliser sur GitHub ou ailleurs, et révoquer/renouveler les accès du tailnet si le téléphone est perdu. Un mot de passe HTTP Basic sans HTTPS n'est pas approprié pour les échanges sur un réseau extérieur.

## Ce qui manque pour l'objectif complet et dans quel ordre

| Priorité | Capacité | Statut V8.2 | Preuve avant activation |
| --- | --- | --- | --- |
| 1 | Interface téléphone + caméra en prévisualisation/capture locale | Code livré, tests CI à vérifier | Test réel Chrome/Android + permission utilisateur |
| 2 | Vision CPU sur photo provenant du P20 | Non raccordée à la console mobile | Endpoint image authentifié, taille limitée, traitement éphémère, contrôle origine et consentement ; V6 possède déjà MobileSAM CPU local |
| 3 | Chat vocal et outils du Command Center sur mobile | Non connecté | API authentifiée, quotas, schéma d'entrée borné et contrôle d'accès |
| 4 | DeepSeek Harness (outils + agents) | SDK importé en CI, **aucun agent certifié** | Exécution de tâche fictive, journaux revus, manifeste des plugins réellement disponibles ; `sdk-minimal` **n'inclut pas** la gamme complète d'outils |
| 5 | Développement/CI assistés par agent | Non connecté | Repository fixture, patch/diff, pytest indépendant, approbation avant GitHub write |
| 6 | Caméra distante temps réel | Non connecté | Authentification, contrôle permanent de consentement, latence/débit, aucune conservation implicite |
| 7 | Drone — télémétrie et simulation | Aucun appareil connecté | Identifier l'API réelle (MAVLink/ROS 2/SDK fabricant), simuler l'état et tester kill switch |
| 8 | Drone — action réelle | **Interdit dans V8.2** | Préflight matériel, règles géographiques, mode manuel prioritaire, fail-safe perte de liaison, arrêt d'urgence testé, conformité applicable |
| 9 | Mémoire cognitive, replay, expertise multi-domaines | Noyaux HEX-CORTEX déjà développés, pas exposés au mobile | Contrôle des schémas et provenance, API minimale, benchmarks reproductibles |

Le but est de conserver **HEX-CORTEX comme cerveau cognitif**, DeepSeek comme **runtime agentique optionnel**, le P20 comme **capteur et console privée**, et les drones comme **périphériques fortement gouvernés**, sans transformer une preuve d'installation en fausse « intégration totale ».

Références :
- DeepSeek SDK : https://github.com/deepseek-ai/deepseek-harness/tree/master/python/sdk
- Sécurité du profil `sdk-minimal` : https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/bundle/sdk-minimal/README.md
- Tailscale Serve : https://tailscale.com/docs/reference/tailscale-cli/serve
- Accès privé HTTPS : https://tailscale.com/docs/use-cases/application-testing/share-local-dev-server-with-team
- Camera browser (HTTPS) : https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
