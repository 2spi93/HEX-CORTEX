# HEX-CORTEX V13 — Biomimétisme vérifiable et premier MathCell fonctionnel

## Sens de la démarche

Le fondateur demande de s'inspirer de la création et de son organisation.
HEX-CORTEX peut étudier des mécanismes observables dans les organismes
vivants — cellule, mémoire immunitaire, rétroaction, redondance,
vérification, régulation — sans affirmer qu'ils sont infaillibles,
que le logiciel est vivant, ou que l'analogie suffit à démontrer une
augmentation de l'intelligence.

La croyance du fondateur sur Dieu et la création est respectée ;
les **justifications techniques** utilisent séparément des phénomènes
biologiques documentés et des critères de test reproductibles.

## Mécanismes d'inspiration et conséquences vérifiables

| Inspiration de l'organisation biologique | Règle d'ingénierie |
|---|---|
| Organes / cellules spécialisées | CellRole dédié par discipline et activation sélective |
| Homéostasie / rétroaction négative | Mesurer la dérive, dégrader le statut, protéger le noyau |
| Défense immunitaire et mémoire | Conserver les erreurs, exiger plusieurs observations avant une réhabilitation |
| Correction et contrôle de l'information | Deux chemins de calcul, hash de preuve, replay intègre |
| Adaptation sans perte d'identité | Apprendre sous surveillance sans autocertifier une nouvelle capacité |
| Capteurs et effecteurs du vivant | Séparer observation, recommandation et commande physique indépendante |

Références biologiques publiques :
- https://www.ncbi.nlm.nih.gov/books/NBK559138/ — Homéostasie,
  setpoint, rétroaction et contrôle physiologique.
- https://www.ncbi.nlm.nih.gov/books/NBK26921/ — Systèmes de
  mémoire immunitaire et signaux de co-stimulation.
- https://www.ncbi.nlm.nih.gov/books/NBK539801/ — Immunité innée
  et adaptative.

**Limite des analogies :** la reproduction des formes du vivant
n'est pas l'équivalent d'un avantage mesurable; des algorithmes
plus simples peuvent être meilleurs selon la tâche.

## Premier véritable organe scientifique : MathCell

`src/hex_cortex/core/cortex_exact_math_v13.py` exécute réellement
des calculs **rationnels exacts** sans aucun LLM :

- littéraux **entiers**, parenthèses, +, −, ×, ÷, puissances entières
  bornées et signes unaires ;
- `fractions.Fraction`, résultats numérateur/dénominateur sans
  erreurs dues à l'arithmétique flottante ;
- AST vérifié et borné (taille source, nombre de nœuds, profondeur,
  taille des valeurs et puissances) ;
- pas de `eval`, `exec`, imports, attributs, noms, appels de
  fonctions, accès aux fichiers ou au réseau ;
- second calcul du même arbre par un parcours non récursif
  indépendant du premier traversée récursive ;
- `MathCell` typé pour le routeur `CognitiveCircuit`, avec
  preuve de résultat recalculée par `verify_math_cell_result`.

**Limites :** ce module n'est **ni SymPy, ni un solveur symbolique,
ni une preuve formelle**. Il ne prend pas les nombres décimaux,
sinus, dérivées, intégrales ou équations à inconnues. Les deux
parcours utilisent le même AST validé : ils ne sont pas une preuve
mathématique indépendante d'un autre moteur ou d'un tiers.

Étendre avec des solveurs tiers d'abord en mode confiné, sans
appeler `sympify` ou un parseur évaluant des expressions non fiables
sans validation. Le calcul exact d'expressions rationnelles est une
première brique exploitable par MathCell, PhysicsCell, ChemistryCell.

### Calcul utilisable immédiatement dans PowerShell

```powershell
python -m pip install -e ".[dev]"
hexcortex-math --expression "1 / 3 + 1 / 6" --approve-calculate --pretty
```

Résultat attendu : `numerator: 1`, `denominator: 2`,
`independent_traversal_agrees: true`. Sans
`--approve-calculate`, le calcul est refusé ; aucune API
ou connexion réseau n'est sollicitée. La grammaire exacte accepte
uniquement des littéraux entiers : `0.1 + 0.2` sera refusé,
et non arrondi silencieusement.

## Homéostasie du cortex

`src/hex_cortex/core/cortex_homeostasis_v13.py` reçoit une
`HealthObservation` **typée** avec taux d'erreur, rapport
de latence, nombre de pannes, vérification de la spine et preuves
de récupération.

- État normal : stable ; quelques erreurs : degraded ;
- ≥ 3 échecs consécutifs ou taux d'erreur ≥ 0,50 : quarantine ;
- hash-chain / spine corrompue : quarantine immédiate ;
- une cellule quarantinée ne se réhabilite pas automatiquement ;
- récupération : au moins 5 échantillons vérifiés par un contrôle
  externe, baisse mesurée de la dérive, puis **revue humaine**.

C'est un **avis de sûreté**, pas un pilote capable de modifier le
CellRegistry ou de commander du matériel. Il ne réactive pas les
actuateurs de drones ou de robots.

Les seuils ci-dessus sont des paramètres d'ingénierie initiaux.
Ils **ne sont pas des seuils biologiques observés** ni une
certification de fiabilité. Les seuils doivent être calibrés sur
des données d'erreur réelles.

## Pourquoi les unités viennent ensuite

Pour passer de MathCell à PhysicsCell, il faudra imposer des unités
dimensionnelles SI, des contrôles d'homogénéité des équations et
une quantification des incertitudes. Une réponse numérique correcte
sans bonne unité peut être dangereusement fausse dans l'ingénierie.

Références publiques :
- https://www.nist.gov/pml/owm/metric-si/si-units
- https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values

## Vérification sur le PC actuel

```powershell
git switch main
git pull --ff-only origin main
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

Deux nouveaux contrôles doivent apparaître :
`independently_checked_exact_math` et
`homeostatic_integrity_quarantine_advisory`.

Aucun modèle local, Docker, GPU, VPS, requête cloud ou
benchmark de modèle n'est nécessaire.

## Vers l'armure universelle

1. MathCell exact, puis variables, solveurs et vérification indépendante
2. PhysicsCell : unités SI, bilans de matière/énergie, conservation
3. ChemistryCell : stœchiométrie et provenance moléculaire réelle
4. Régulation : homeostasis liée en lecture seule à la santé des cellules
5. Prévention des régressions : mémoire immunitaire des erreurs
6. Robots/drones : simulateurs et contrôleurs de sûreté indépendants
7. Comparaison d'amplification du modèle seul vs modèle + HEX-CORTEX
   sur problèmes scientifiques nouveaux, et non par nombre de modules

**Il n'existe pas de gain x2/x10 prouvé en V13.** Le progrès se mesure
par la précision des résultats, la résilience aux erreurs, la sécurité
et la réutilisation de connaissances vérifiées.
