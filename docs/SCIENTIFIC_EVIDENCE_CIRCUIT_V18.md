# HEX-CORTEX V18 — Circuit scientifique de preuve, sources, Critic et Spine

## Objectif

Le cortex universel ne doit pas être une collection d'outils séparés.
Après MathCell, PhysicsCell, ChemistryCell, le Scientific Knowledge Router
(V16) et la vérification des sources locales (V17), V18 relie le tout
au **vrai circuit cognitif** déjà présent dans HEX-CORTEX :

```text
Operator approval → Task (domaine, revendication, unité)
→ ThalamicRouter / EvidenceCell
→ Documents réels sur disque (bytes SHA-256 vérifiés)
→ Scientific Knowledge Router (conflit, unité, incertitude)
→ Critic : seconde lecture / seconde vérification des preuves
→ CognitiveClock / CanonicalSpine hash-chaînée
→ Reçu redigé, sans extrait de document ni autorisation physique
```

Le programme ne lance aucun modèle LLM, n'exécute aucun code
depuis les documents, ne fait pas de connexion externe et ne
modifie aucun fichier de l'utilisateur ou du projet.

## Démonstration PowerShell, déjà présente dans le dépôt

```powershell
git switch main
git pull --ff-only origin main
python -m pip install -e ".[dev]"

hexcortex-science-circuit --manifest examples/scientific_v17/manifest.json --sources-dir examples/scientific_v17 --claim-id demo_velocity --domain physics --unit m/s --approve-read --pretty
```

Sortie attendue :
`status: verified`,
`selected_cells: ["scientific-evidence"]`,
`verified_cell_count: 1`,
`spine_verified: true`,
`model_used: false`,
`checkout_modified: false`,
`physical_action_authorized: false`.

**ATTENTION au sens de "verified"** : seule l'exécution du
*CognitiveCircuit* et la cohérence des données synthétiques sont
vérifiées, pas la vérité de la mesure, l'indépendance des auteurs,
l'autorité d'un éditeur, ni une performance du cerveau IA.

## Sécurité : l'attaque par changement de fichier entre deux lectures

Une cellule pourrait examiner une source et trouver les valeurs
cohérentes, puis le document peut être modifié **avant que le
Critic ne vérifie son travail**.

Le test `test_sources_are_rechecked_after_cell_proposal_before_final_acceptance`
modifie volontairement les octets entre les deux passages.
La deuxième vérification doit rejeter l'acceptation :
`status: blocked`, événement de refus dans la Spine,
aucune promotion de mémoire ni effet externe.

Cela protège une portion précise du parcours vérifiable,
mais n'offre pas une protection totale contre les attaques de
race ou de substitution de fichiers sur un OS compromis.
Les chemins doivent rester confinés à la racine consentie,
et l'accès aux sources limité à des documents de confiance.

## Garde-fous conservés

- Sans approbation : la cellule ne consulte pas les sources.
- Sans vérificateur de sources : pas d'acceptation.
- Avec des résultats contradictoires ou incohérents :
  pas de verdict vérifié.
- Des domaines, unités ou requêtes JSON imprévus entraînent
  un refus.
- Toute vérification échouée dégrade l'état de confiance de
  la cellule dans son propre registre.
- Pas d'actionneur, pas de shell, pas d'accès arbitraire
  aux fichiers, pas d'activation de skills ni de promotion
  automatique d'une hypothèse.

Les cellules utilisent les preuves pour expliquer et contrôler
leur conclusion, pas pour affirmer une compétence impossible.

## Ce que V18 ne fournit toujours pas

- authentification cryptographique des éditeurs et révocation ;
- consultation automatisée de publications ou bases externes ;
- bibliothèque scientifique persistante interrogeable par vecteurs ;
- capacités indépendantes de chimie réelle, physique expérimentale
  ou biologie ;
- solution scientifique découverte par une IA reliée via API ;
- benchmark du gain apporté à un cerveau IA.

## Vérification

```powershell
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

Le contrôle `scientific_sources_routed_to_verified_cognitive_spine`
démontre l'intégration hors ligne et sans modèle sur des fixtures
synthétiques temporaires.

L'amélioration suivante doit concerner les vrais corpus autorisés,
leur versioning, la distinction entre source originale et copie,
et la propagation d'incertitude jusque dans les décisions et les
compétences apprises.
