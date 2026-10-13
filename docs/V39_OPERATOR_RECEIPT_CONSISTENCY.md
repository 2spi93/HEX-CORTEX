# HEX-CORTEX V39 — Audit READ-ONLY des résultats MobileSAM V38

## Preuve opérateur du 13 octobre 2026

Les journaux locaux partagés montrent que le vrai provider MobileSAM `vit_t` CPU a traité **9 photographies**, avec **14 invites d'objets**, lors de deux exécutions successives. Le dernier résumé est `receipts/v38_uploaded_exploration/run-20261013T173800-031171Z/summary.json`. Aucune IoU contre un masque de référence n'a encore été mesurée. Ces deux exécutions reprennent **les mêmes neuf images** et ne représentent pas dix-huit captures indépendantes.

Durées signalées par le dernier journal (ms, premier chargement inclus): `3398.26, 759.32, 582.26, 548.47, 587.70, 597.68, 543.60, 542.02, 566.92`.

V39 vérifie en lecture seule la cohérence entre:
- `research/v38_uploaded/boxes.json` (13 images initiales, 9 `photographic`), dimensions, boîtes, image SHA-256 ;
- `summary.json` du run choisi (exactement 9 scènes terminées) ;
- chacun des neuf JSONs bruts `scene*.json` (provider MobileSAM CPU, état, empreinte source et poids, 14 masques signalés, identifiants/boîtes et pixels cohérents).

La sortie est un tableau de **candidats de métadonnées**, jamais une nouvelle mémoire persistée: sans masque PNG réel ni événement existant dans CanonicalSpine, une mémoire objet validée et un audit de sa provenance seraient mensongers. Les noms ont été saisis par un opérateur, non reconnus par le modèle. Les recettes locales ne sont pas des signatures cryptographiques d'exécution, et les droits sur les photos ne sont pas attestés.

## Commandes PowerShell — une seule ligne chacune

Depuis la racine du dépôt, conserver `images/`, `research/v38_uploaded/`, `receipts/` et `weights/`, sans `git clean`.

~~~powershell
git fetch origin
git switch -c feature/v39-readonly-operator-receipt-audit --track origin/feature/v39-readonly-operator-receipt-audit
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_operator_receipt_audit_v39.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_operator_receipt_audit_cli_v39 --project-root . --latest --dry-run
& $VP -m hex_cortex.memory.cortex_operator_receipt_audit_cli_v39 --project-root . --latest --approve-read
~~~

Pour choisir explicitement un ancien run (plutôt que le plus récent):

~~~powershell
& $VP -m hex_cortex.memory.cortex_operator_receipt_audit_cli_v39 --project-root . --run-dir receipts/v38_uploaded_exploration/run-20261013T173800-031171Z --approve-read
~~~

Le contrôle relit le contenu local des neuf photos et vérifie leurs empreintes avec les sources et les tickets, sans télécharger de poids ni recalculer les segmentations. Il affiche le JSON sur la console; aucun fichier créé ou modifié. En cas de refus, vérifier `reason` avant de changer quoi que ce soit.

## Prochain chantier indépendant

Les tickets V38 ne contiennent **pas les pixels de masque**, uniquement SHA/pixels comptés. On ne peut donc pas reconstruire les contours simplement en lisant les anciens rapports. Pour observer visuellement la qualité:
1. Exécuter à nouveau MobileSAM **sur un sous-ensemble choisi** avec `--export-dir` et `--approve-write`, sans écraser aucun dossier.
2. Afficher, superposer puis inspecter le masque PNG pour les jambes, cheveux, objets partiellement cachés, voiture et personnes qui se chevauchent.
3. Faire annoter séparément 3–10 vraies photos pour un score IoU crédible; les prédictions du modèle ne doivent jamais servir de référence.
4. Ensuite seulement envisager V40 identité temporelle, association inter-images et scènes durables, avec véritables IDs CanonicalSpine déjà existants.

Ni la segmentation ni la vérification V39 ne démontrent une compréhension du mouvement, un raisonnement physique, un World Model généraliste ou la généralisation DINOv2.
