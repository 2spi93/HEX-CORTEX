# HEX-CORTEX — V42 intégration réelle des observations V41 avec CanonicalSpine

## Pourquoi nous accélérons

La vision cible est un **exosquelette cognitif universel** et pas un moteur de segmentation isolé. HEX-CORTEX dispose déjà de CanonicalSpine, CognitiveClock, router, workspace, memory/replay/skills, World Model et Harness. Le chaînon manquant après V41 est une **connexion opérationnelle** des masques visuels prouvés avec le journal commun du système, suivie de l'évaluation de leur utilité.

V42 réutilise strictement les classes existantes :
- \`hex_cortex.spine.canonical_spine.CanonicalSpine\` avec ses vraies chaînes de hashes et ses vrais \`event_id\` ;
- \`hex_cortex.spine.jsonl_store.CanonicalSpineJsonlStore\` pour snapshots durables contrôlés et refus d'une écriture sur une ancienne version ;
- \`stage_verified_object_candidates_v41\` pour relire/re-hasher le vrai PNG, remonter au manifeste V38, vérifier V39 et le ticket V40.

Il n'ajoute **pas** de deuxième index mémoire ou moteur de replay.

### Ce qui est réellement appris ou reconnu

Chaque événement \`vision.object_mask_predicted.v42\` ne déclare **qu'une prédiction de masque existante**, les empreintes SHA-256 des pixels et de la source, la boîte visible et sa boîte de prompt, et un nom provenant de l'opérateur. Il ne contient ni secrets, ni pixels de photo, ni texte de conversation, ni scores inventés.

Le journal ne prouve **pas** la catégorie visuelle reconnue par le modèle, l'identité d'un objet entre plusieurs photos, son mouvement ou une IoU humaine. \`confidence=None\`. Il n'y a ni promotion de skill, ni modification de poids, ni confiance automatique accordée au modèle. L'événement CanonicalSpine lui-même est réel et peut être relu/vérifié; **cela n'est pas un événement de vérité terrain**.

### Commandes PowerShell — une commande par ligne

Sur le dépôt où existent encore les 3 scènes V40 et 5 vrais PNG audités :

~~~powershell
git fetch origin
git switch -c feature/v42-real-evidence-to-canonical-spine --track origin/feature/v42-real-evidence-to-canonical-spine
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_visual_to_canonical_spine_v42.py
& $VP -m ruff check .
~~~

**Dry-run** sans aucune lecture ni écriture :

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 --dry-run
~~~

**Lecture des 5 PNG existants + création d'une chaîne CanonicalSpine temporaire en mémoire, aucune écriture :**

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read
~~~

Résultat attendu : \`canonical_spine_visual_predictions_staged_in_memory\`, \`candidate_count=5\`, \`new_event_count=5\`, \`spine_integrity_ok=true\`, \`files_written=false\`.

**UNIQUEMENT après inspection de la sortie précédente**, écriture volontaire dans un **journal local nouveau et séparé** :

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read --persist --approve-write
~~~

Ce mode écrit uniquement dans \`receipts/v42_canonical_spine/visual_predictions.jsonl\`. Il ne remplace pas la spine centrale d'autres tâches, ne modifie pas les anciennes recettes V38–V41, et ne charge aucun modèle. Il réemploie les mécanismes d'intégrité et de snapshot existants. Si le même lot est présenté une seconde fois, les événements existants sont retrouvés par une clé déterministe et **aucun doublon n'est ajouté**.

Inspecter les événements effectivement durables :

~~~powershell
& $VP -c "from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore; s=CanonicalSpineJsonlStore('receipts/v42_canonical_spine/visual_predictions.jsonl').load(); print('integrity',s.verify_integrity().ok,'events',len(s.events)); print([(e.event_id,e.event_type,e.task_id) for e in s.events])"
~~~

**Important :** le journal du test est local, dédié aux événements visuels vérifiés. Une éventuelle insertion dans la spine active de l'application nécessitera une revue de la politique de confidentialité, des chemins et des transactions concurrentes, et n'est pas réalisée par V42.

## Prochaine série de tâches sur le même circuit

La fin opérationnelle ne se mesure plus aux numéros V. Elle se mesure à un test de bout en bout :

1. **Admission/signalement** : entrée réelle vérifiée → CanonicalSpine existant, sans événement fictif (V42).
2. **Interprétation de scène temporelle** : deux frames du **même objet** avec ordre observé, segmentation et politique d'appariement, y compris refus d'une identité ambiguë. Les neuf photographies V38 non liées ne peuvent pas constituer une vérité temporelle.
3. **Cognitive Circuit** : la cellule de perception alimente le Router/Workspace/Clock, un critique externe vérifie le résultat, CanonicalSpine conserve l'incertitude et SleepReplay peut relire les événements.
4. **Évaluation contrôlée** : un vrai avant/après/action nouveau contre le checkpoint V31 existant et une baseline simple (sans recouvrir les anciens 108 cas connectés). Pas d'amélioration revendiquée sans séparation de sources et métrique.
5. **Feedback utile** : erreurs réelles → MemoryCompression/Skill candidate → review → replay → comparaison contrôlée du même modèle de base avec et sans HEX-CORTEX. Promote/revoke explicites.

Ne pas fusionner automatiquement dans \`main\`, ne pas changer DINOv2 ni exécuter de benchmark GPU sur la RX 6700 XT instable.
