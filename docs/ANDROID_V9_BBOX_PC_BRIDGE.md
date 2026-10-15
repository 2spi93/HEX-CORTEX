# HEX-CORTEX V9 — Importer une boîte JSON du Huawei dans MobileSAM CPU

Cette fonctionnalité complète le compagnon Android V9 de la PR #61. Elle réutilise **la même implémentation MobileSAM V36 et le même serveur V8**. Elle ne crée pas de nouvelle reconnaissance d'objets.

## Chaîne opérateur réellement fonctionnelle

1. Sur le téléphone, ouvrir l'application compagnon HTTPS depuis GitHub Pages (voir docs/ANDROID_COMPANION_V9_SETUP.md), charger une photo, tracer une bbox, choisir le nom d'objet.
2. Exporter à la fois le fichier JPEG normalisé et le fichier .bbox.json. Le JSON contient une empreinte SHA256 du JPEG exporté.
3. Transférer les deux fichiers par USB/partage explicite sur ton PC Windows.
4. Dans le Command Center V9 local, onglet Photo & caméra, **charger d'abord le même JPEG** via le champ Photo locale.
5. Importer ensuite le .bbox.json via le nouveau champ « Boîte du téléphone ».
6. L'interface vérifie côté navigateur : schéma hex.mobile_manual_bbox.v9, dimensions, XYXY intégralement entiers et dans l'image, nom d'objet borné, SHA256 du JPEG exact, et absence de changement de photo durant l'import.
7. Si tout correspond, le rectangle apparaît automatiquement avec le nom choisi. **Aucune inférence n'est lancée lors de l'import.**
8. Pour demander la segmentation, cliquer sur le bouton existant **Segmenter avec MobileSAM CPU**. L'appel fait appel au moteur V36/V6 déjà vérifié; la photo sera alors transférée au serveur localhost 127.0.0.1 et non à un cloud.

Une image différente ou modifiée, même de mêmes dimensions, est rejetée lorsque l'empreinte diffère. Le JSON n'a pas le droit de définir un prompt système, un modèle, une route réseau ou une commande physique.

## Installer à partir de la branche V8 actuelle

Arrêter d'abord le serveur V8 (Ctrl+C). Dans PowerShell sous C:\Users\2spi\HEX-CORTEX, une commande par ligne :

    git fetch origin
    git switch -c feature/v9-mobile-bbox-import-to-command-center --track origin/feature/v9-mobile-bbox-import-to-command-center
    $VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
    & $VP -m pytest -q tests/test_cortex_android_companion_v9.py tests/test_cortex_command_center_v9.py tests/test_cortex_command_center_v8.py
    & $VP -m ruff check .
    & $VP -m hex_cortex.memory.cortex_command_center_v9 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision

Ouvrir http://127.0.0.1:8777/ puis Ctrl+F5 et suivre les huit étapes ci-dessus. Ce serveur conserve les fonctions précédentes de vision, chat, événements et inventaire DeepSeek.

## Limites et étapes suivantes

Ce transfert n'est pas un contrôle distant du téléphone. Le PC conserve le bind 127.0.0.1 : **ne pas ouvrir le port 8777 sur un réseau public ou le LAN** pour éviter de contourner Host/Origin et les garanties de sécurité locales.

Le compagnon doit être réellement testé sur le téléphone, et la segmentation sur un vrai cliché doit être visuellement inspectée. Aucune vérité terrain IoU, identité d'objet entre images, analyse temporelle, reconstruction 3D ni commande de drone n'est prouvée par cet import.

Chantiers futurs : appairage chiffré par QR et permission par session, streaming vidéo WebRTC caméra→PC avec arrêt immédiat, annotation humaine, World Model temporel, adaptateurs télémétrie robot/drone read-only puis protections physiques avant action.
