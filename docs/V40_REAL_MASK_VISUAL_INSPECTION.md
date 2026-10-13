# HEX-CORTEX V40 — Rejouer et inspecter les vrais masques MobileSAM

## État scientifique avant V40

L'opérateur a exécuté MobileSAM sur 9 photographies et 14 objets, puis V39 a vérifié la cohérence **locale** de tous les tickets V38 : `v39_receipt_consistency_pass`, `photographic_scenes_consistent=9`, `operator_prompted_objects_consistent=14`. Les tickets historiques contiennent l'empreinte SHA-256 calculée sur les *octets du masque binaire brut* et le nombre de pixels, **pas de PNG de masque**. Aucune IoU terrain, indépendance des captures ou généralisation du World Model n'est démontrée.

V40 rejoue un sous-ensemble choisi des photos et des invites 2D existantes, via le provider MobileSAM V36, et enregistre uniquement sur autorisation :
- un nouveau PNG binaire par objet ;
- une prévisualisation PNG (photo d'origine + masque cyan + bord rouge) ;
- `inspection.json` précisant les empreintes vérifiées, les boîtes d'opérateur et les limites de preuve.

Le PNG de masque est décodé en niveaux de gris ; son SHA-256 est recalculé sur les **octets de pixels** (`mask.tobytes()`), puis comparé au ticket de la véritable exécution V38. Le PNG compressé aura naturellement une empreinte de fichier différente. Si le contour a changé ou que le nombre de pixels ne correspond pas, V40 bloque et supprime uniquement le **nouveau** répertoire de sortie qu'il vient de créer. Les vieux tickets, les photographies et les checkpoints ne sont ni écrasés ni supprimés. Il n'y a pas de falsification de score IoU ni de prétendue compréhension physique.

### Commandes PowerShell — une seule ligne par commande

Depuis `C:\Users\2spi\HEX-CORTEX`, avec tes images et `receipts/` V38 déjà présents :

~~~powershell
git fetch origin
git switch -c feature/v40-mask-visual-inspection --track origin/feature/v40-mask-visual-inspection
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
$env:OMP_NUM_THREADS = "4"
$env:MKL_NUM_THREADS = "4"
$WeightSHA = (Get-FileHash ".\weights\mobile_sam.pt" -Algorithm SHA256).Hash.ToLowerInvariant()
if($WeightSHA -ne "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"){throw "SHA256 inattendu : arrêter"}
& $VP -m pytest -q tests/test_cortex_mask_visual_inspection_v40.py
& $VP -m ruff check .
~~~

**Dry-run :** aucun fichier consulté, aucun modèle chargé.

~~~powershell
& $VP -m hex_cortex.memory.cortex_mask_visual_inspection_cli_v40 --checkpoint-sha256 $WeightSHA --dry-run
~~~

**Vraie exécution CPU sur les 3 scènes sélectionnées par défaut :** saut, voiture de course, transfert d'atelier. Les trois autorisations sont requises et explicites.

~~~powershell
& $VP -m hex_cortex.memory.cortex_mask_visual_inspection_cli_v40 --project-root . --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --approve-read --approve-model-load --approve-write
~~~

Exemple pour **une seule scène** :

~~~powershell
& $VP -m hex_cortex.memory.cortex_mask_visual_inspection_cli_v40 --project-root . --checkpoint weights/mobile_sam.pt --checkpoint-sha256 $WeightSHA --scene scene07_racecar --approve-read --approve-model-load --approve-write
~~~

Si `status=verified_mask_replay_exported`, ouvre le dossier `new_output_dir` renvoyé par le JSON, dans `receipts/v40_mask_inspection/run-.../`. L'ensemble des aperçus est strictement local ; ne commite pas les photos ou masques sans leurs licences et contrôles de confidentialité.

~~~powershell
explorer.exe .\receipts\v40_mask_inspection
~~~

Tous les nouveaux artefacts d'une exécution réussie sont listés dans `inspection.json`. **Le hash identique signifie seulement que la même sortie binaire a été reproduite**, pas que cette sortie décrit correctement les vrais contours.

### La suite

1. Regarder les aperçus (cheveux/mains, contours de voiture, masques qui avalent l'arrière-plan, chevauchement de personnes).
2. Choisir les cas difficiles, enregistrer anomalies et faux positifs. Éviter de ne conserver que des exemples flatteurs.
3. Produire **séparément** des annotations humaines indépendantes en PNG 1 bit ou L, fond noir et objet blanc. Ne jamais utiliser l'ancienne prédiction MobileSAM comme vérité.
4. Exécuter l'évaluation V38 quantitative à partir d'un manifeste `hex.real_photo_benchmark.v38` indépendant, puis seulement faire évoluer la mémoire inter-images, avec les véritables IDs de CanonicalSpine.

Pour rappel, le CPU utilisé évite les plantages de la RX 6700 XT ; V40 ne charge pas DINOv2 et ne modifie pas le World Model actif.
