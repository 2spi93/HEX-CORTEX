# HEX-CORTEX — Intégration de bout en bout V43 : pixels vérifiés → cerveau existant

## Sprint prioritaire : intégrer, ne plus dupliquer

Le système existant possède déjà \`ThalamicRouter\`, \`CellRegistry\`, \`GlobalWorkspace\`, \`CognitiveClock\`, \`CognitiveCircuit\`, \`CanonicalSpine\`, \`SleepReplay\`, Cognitive Genome et World Model. La vision originale exige leur coopération sur une même tâche, avec des preuves réelles, avant toute affirmation d'autonomie ou d'amélioration.

V43 **réutilise directement** \`core/cognitive_circuit_v1.CognitiveCircuit\` et les événements persistés dans **la même** \`CanonicalSpineJsonlStore\` locale par V42. Un seul rôle \`CellRole.EVIDENCE\` sain est enregistré, le router sélectionne sa cellule, le workspace reçoit une tâche *hashée*, la clock exécute \`workspace/action/critic\`, le vérificateur revoit les cinq masques PNG en repassant par V39/V40/V41 et la spine reste chaînée. Aucun LLM n'est nécessaire pour la preuve du circuit.

**Important :** les cinq masques sont des prédictions MobileSAM, pas des annotations humaines. Même si le circuit renvoie \`verified\`, cela signifie uniquement que la provenance locale et les octets concordent — **pas** que les noms, contours, actions ou principes physiques sont corrects. Le contrôleur de cellules est déterministe et n'est pas une preuve d'intelligence générale. Le vérificateur partage des dépendances avec V41; ce n'est pas une attestation externe indépendante.

Aucune promotion de skill, aucun retraining, aucun GPU, réseau, modification d'outil ou fusion Git. Le journal V42 reste **isolé** dans \`receipts/v42_canonical_spine/visual_predictions.jsonl\`, et n'est pas la spine active globale de la plateforme.

## Commandes Windows PowerShell : une ligne physique chacune

Depuis la racine HEX-CORTEX, ne pas supprimer \`weights/\`, \`images/\`, \`receipts/\` ni les scripts V38 opérateur :

~~~powershell
git fetch origin
git switch -c feature/v43-real-visual-cognitive-circuit --track origin/feature/v43-real-visual-cognitive-circuit
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_visual_to_canonical_spine_v42.py tests/test_cortex_visual_cognitive_circuit_v43.py
& $VP -m ruff check .
~~~

V42 **à réaliser une fois** après validation du mode sans écriture :

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read
& $VP -m hex_cortex.memory.cortex_visual_to_canonical_spine_cli_v42 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read --persist --approve-write
~~~

Première traversée du circuit **sans persistance** :

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_cognitive_circuit_cli_v43 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read --approve-execution
~~~

**Uniquement si** ce test indique \`visual_cognitive_circuit_verified_in_memory\` avec \`source_mask_count=5\` et \`cognitive_spine_integrity=true\` : ajouter volontairement les événements de clock/circuit au journal V42 dédié.

~~~powershell
& $VP -m hex_cortex.memory.cortex_visual_cognitive_circuit_cli_v43 --project-root . --inspection-run receipts/v40_mask_inspection/run-20261013T181258-825272Z --approve-read --approve-execution --persist-circuit --approve-write
~~~

Vérifier les événements qui existent **effectivement** après écriture :

~~~powershell
& $VP -c "from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore; s=CanonicalSpineJsonlStore('receipts/v42_canonical_spine/visual_predictions.jsonl').load(); print('CHAIN:',s.verify_integrity().ok,'TOTAL:',len(s.events)); print([(e.event_type,e.task_id) for e in s.events])"
~~~

La deuxième exécution avec le même lot retourne un statut *already recorded* ; le circuit n'est pas rejoué silencieusement.

## Définition du véritable « système complet »

Il ne faut plus confondre nombre de PR avec réalisation. L'achèvement du **noyau** exige un test de bout en bout, sur données externes :

1. **Perception vérifiable** : masque CPU → objet sourcé → événement CanonicalSpine → cognitive circuit, avec refus d'hallucination, d'écriture non autorisée et des secrets (V35–V43).
2. **Environnement temporel** : vidéos ou frames consécutives d'une même capture; tests d'identité/mouvement/occlusion avec annotations distinctes; le lot de neuf photos indépendantes n'est pas un exemple temporel.
3. **Monde et décisions** : observation + action connue → prédiction du prochain état → observation indépendante → mesure d'erreur; comparer le World Model actif à une baseline *sans* HEX-CORTEX.
4. **Boucle d'apprentissage vérifiée** : véritable erreur observée → critic + memory residual + procédure de correction candidate → revue explicite → replay et réutilisation sans régression.
5. **Comparaison de cerveau interchangeable** : mêmes tâches et mêmes limites sans/avec Harness, métriques qualité/temps/coût; cloud opt-in et pas de benchmark GPU sur la RX 6700 XT en panne.

Le « core opérationnel » ne veut pas dire CR-JEPA entraîné, intelligence universelle, ou autodéveloppement sûr. Toutes ces capacités doivent rester des jalons scientifiques distincts.
