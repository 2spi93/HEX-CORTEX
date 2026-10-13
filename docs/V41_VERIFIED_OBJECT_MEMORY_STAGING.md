# HEX-CORTEX V41 — Candidats de mémoire visuelle, fondés sur les vrais pixels

## Rappel de l'objectif

HEX-CORTEX est l'**exosquelette cognitif universel** : cerveau/modèle interchangeable, routeur et cellules expertes, perception object-centric, World Model, mémoire CanonicalSpine/Replay, vérification scientifique, apprentissage des erreurs et compétences réutilisables, agentivité sous approbation. V41 ne valide qu'une étape de ce but, pas l'intelligence universelle.

## Évidence opérateur

V40 a réellement relancé le modèle \`mobile_sam_vit_t_cpu\` sur trois scènes (saut, voiture de course, atelier), exportant cinq PNG binaires et cinq aperçus. Toutes les empreintes SHA-256 des **pixels bruts** des cinq masques concordaient avec les tickets V38. V39 a confirmé 9 scènes et 14 boîtes d'origine. Source opérateur : run V40 \`receipts/v40_mask_inspection/run-20261013T181258-825272Z\`.

V41 relit (sans nouvelle inférence) les PNG de ce run, vérifie les dimensions, les pixels uniquement 0/255, les empreintes SHA-256 et comptes de pixels, les invites boîte, les images d'origine et le manifeste validé par V39. Il produit des **candidats non persistés** avec boîtes réelles du masque, informations de source et relations spatiales strictement 2D. Les empreintes d'image et de masque ne suffisent pas à prouver que le masque est un vrai objet : \`human_reference_iou_available=false\`.

Le module REFUSE de déclarer ou inventer des \`CanonicalSpine event IDs\`, une identité suivie d'une image à l'autre, des mouvements physiques, une mémoire consolidée ou une amélioration du modèle. Il conserve \`promotion_to_long_term_memory_permitted=false\` et n'écrit aucun fichier.

## PowerShell : UNE commande par ligne

À la racine du dépôt sous Windows :

~~~powershell
git fetch origin
git switch -c feature/v41-verified-object-memory-staging --track origin/feature/v41-verified-object-memory-staging
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_object_memory_staging_v41.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_object_memory_staging_cli_v41 --dry-run
& $VP -m hex_cortex.memory.cortex_object_memory_staging_cli_v41 --project-root . --approve-read
~~~

Si tu as exécuté d'autres inspections depuis, utilise le run V40 exact :

~~~powershell
& $VP -m hex_cortex.memory.cortex_object_memory_staging_cli_v41 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read
~~~

Statut attendu : \`verified_pixels_pending_memory_lineage\`, \`scene_count=3\`, \`verified_object_masks=5\`, \`model_called=false\`, \`files_written=false\`.

## Jalons suivants : les preuves manquantes

1. **V42**, véritable association temporelle : deux photographies ou frames du même objet, provenance temporelle, analyse du mouvement et des ambiguïtés, refus d'apparier des clichés sans lien. Distinguer ID de détection ponctuelle et identité suivie.
2. **V43**, compatibilité CanonicalSpine : lier des événements visuels à des IDs qui existent vraiment, gates opérateurs et promotion graduelle de la mémoire basée sur le résultat, pas sur le seul hash.
3. **V44**, prédiction vérifiable et résidus du World Model : action + contexte initial → état prédit → nouvel état observé, comparaison à baseline sans HEX-CORTEX, splits indépendants.
4. **V45**, boucle d'apprentissage/correction : stockage des erreurs, récupération utile, skills et non-régression. Une preuve d'amplification doit inclure des tâches où HEX-CORTEX améliore effectivement le même modèle de base, en aveugle ou en comparaison contrôlée.

La segmentation de vrais pixels ne suffit pas à démontrer compréhension causale, suivi fiable ou prédiction du monde. Ne pas fusionner automatiquement les PR V35–V41 ; étudier le diff, l'architecture et la CI avant intégration.
