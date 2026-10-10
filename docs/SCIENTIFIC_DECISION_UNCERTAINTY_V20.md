# HEX-CORTEX V20 — Propagation de l'incertitude aux décisions scientifiques

## Objectif

Après :
- V13 : MathCell, calcul rationnel borné ;
- V14 : PhysicsCell, unités SI et lois classiques ;
- V15 : ChemistryCell, stœchiométrie et conservation ;
- V16–V18 : preuves, sources locales, Critic et CanonicalSpine ;
- V19 : admissions, versions et révocations contrôlées du corpus ;

la V20 évite un défaut dangereux : **transformer une connaissance
incomplète en décision apparemment certaine**.

Elle introduit la décision *provisoire* à partir d'intervalles
rationnels conservateurs, ou l'abstention explicite, sans fabriquer
de pourcentage de confiance.

## 1. Le principe : utiliser l'enveloppe de toutes les incertitudes

Dans les exemples synthétiques précédents :

- Source A : 100 ± 2 m/s → [98 ; 102]
- Source B : 1/10 ± 1/1000 km/s → [99 ; 101] m/s.

La V16 établit que ces sources sont compatibles puisque leurs
**intervalles se croisent** : l'intersection vaut [99 ; 101].
La V20 refuse de prendre ce croisement pour une garantie plus
précise. Pour une décision de seuil, elle considère l'**enveloppe
conservatrice** [98 ; 102], c'est-à-dire le minimum des bornes
basses et le maximum des bornes hautes.

Exemples de politiques `at_least` (au moins) :

| Seuil | Statut V20 | Interprétation |
|---|---|---|
| 95 m/s | `provisionally_supported` | Toutes les valeurs de l'enveloppe atteignent le minimum |
| 100 m/s | `indeterminate` | Le seuil est à l'intérieur de l'enveloppe |
| 105 m/s | `provisionally_refuted` | Toutes les valeurs de l'enveloppe sont sous le minimum |

Pour `at_most` (au plus), les comparaisons sont inversées.

Un `guard_band` facultatif crée une zone de retenue autour
du seuil ; un `max_span` limite la largeur de l'enveloppe
admissible. Si l'enveloppe est trop large ou traverse une
zone d'incertitude, le résultat reste `indeterminate`.

Ce sont des règles de décision par **bornes déclarées**,
pas des intervalles statistiques calibrés, intervalles de
confiance fréquentistes, probabilités bayésiennes ou garanties
de précision expérimentale. Leur conservatisme est relatif
aux données et erreurs fournies par les sources : si toutes
les sources sont biaisées, le calcul ne supprime pas le biais.

## 2. Exemple PowerShell directement utilisable

Depuis ton dépôt après `git pull` et
`python -m pip install -e ".[dev]"` :

```powershell
hexcortex-science-decision --ledger examples/scientific_v19/ledger.json --pin 8eadc291e08d7292c07519c955fa4e52611577dc57f25a16f962c2c42c6a44c5 --manifest examples/scientific_v17/manifest.json --sources-dir examples/scientific_v17 --claim-id demo_velocity --domain physics --unit m/s --relation at_least --threshold 100 --approve-read --pretty
```

Attendu :

- `status: indeterminate` ;
- `cognitive_evidence_status: verified` ;
- `conservative_lower: "98"`, `conservative_upper: "102"`
  dans `scientific_decision` ;
- `confidence_probability: null`,
  `calibrated_confidence_available: false` ;
- `scientific_truth_certified: false`,
  `physical_action_authorized: false`.

Cette commande retourne **code de sortie 2** parce que
la conclusion ne peut pas être considérée comme satisfaisant
le seuil, même si le circuit de vérification a correctement
fonctionné. Ce choix est intentionnel pour les scripts.

Change seulement `--threshold 95` :
le résultat devient `provisionally_supported`, avec un
code de sortie 0 — **ce n'est pas** une permission d'agir sur
un appareil, un robot ou une machine réelle.

Change `--threshold 105` :
la sortie devient `provisionally_refuted`, code 2.

Ajoute `--guard-band 2` pour une marge de décision
ou `--max-span 3` pour demander l'abstention si
l'incertitude collective est trop large.

## 3. Connexion au cerveau du cortex

`cortex_scientific_decision_v20.py` :

1. recueille une **politique typée** (domaine,
   revendication, unité, relation, seuil, marge) ;
2. demande les mêmes preuves et validations qu'en V16 ;
3. confirme l'intégrité du corpus via le vérificateur
   de source injecté (V17/V19) ;
4. calcule **les bornes en fractions exactes** après
   conversion des unités compatibles ;
5. retourne une issue provisoire ou l'abstention,
   sans production de probabilités artificielles.

`cortex_scientific_decision_circuit_v20.py` :

1. soumet une `Task` au **ThalamicRouter** ;
2. propose un `CellResult` scientifique typé ;
3. fait relire les sources et **recalculer la décision**
   par le vérificateur du **Critic** ;
4. enregistre le parcours dans la **CanonicalSpine** ;
5. sépare le statut des sources (`cognitive_evidence_status`)
   et la décision scientifique (`status`) :
   une décision `indeterminate` peut provenir
   d'un pipeline parfaitement vérifié ;
6. ne promeut aucun skill, ne modifie aucun fichier,
   ne contacte aucun modèle et ne commande aucun
   dispositif matériel.

`workspace_confidence: 0.0` demeure le score générique
non calibré du noyau : il ne représente pas la probabilité
que la conclusion scientifique soit vraie. Les champs
`calibrated_confidence_available: false` et
`confidence_probability: null` rendent cette
limitation explicite.

## 4. Simulations et validation négative

- **625 scénarios** combinant 25 niveaux de seuil relatif
  et 25 rayons d'incertitude : une décision provisoirement
  favorable n'est rendue que si toute l'enveloppe valide
  satisfait le seuil.
- Comparaison directe entre la V16, plus étroite (intersection),
  et la V20, plus conservatrice (enveloppe).
- Tests de conversion m/s ↔ km/s et de bornes exactes.
- Politique invalide, expression Python injectée, marge
  négative, seuil ambigu : refus ou abstention.
- Sources scientifiques contradictoires, absentes ou
  non vérifiées : aucune conclusion provisoire.
- Source altérée **entre la première lecture et le Critic** :
  décision bloquée, spine intègre.
- Empreinte V19 invalide : aucune conclusion.
- Sans consentement : aucun document lu.

Ces simulations concernent une **politique de décision
numérique et documentaire**, pas la validité d'un phénomène
physique ou un essai de performance d'une IA.

## 5. Limites strictes

- Les identifiants de sources ne certifient pas que leurs
  producteurs sont indépendants.
- Les valeurs et incertitudes déclarées peuvent être
  incomplètes ou biaisées : cohérence mathématique ≠ vérité.
- Le calcul par enveloppe peut être très conservateur ;
  il ne combine pas statistiquement des mesures indépendantes.
- L'état `provisionally_supported` ne permet aucune
  intervention réelle, transaction, déclenchement d'un
  robot ou exécution informatique dangereuse.
- Aucune requête cloud, aucun Ollama, aucun VPS,
  aucun GPU, aucune action extérieure.
- La compatibilité mathématique et les contrôles sur les
  documents restent insuffisants pour certifier
  `production_ready=true`.

## 6. Vérification

```powershell
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

La readiness inclut :

- `scientific_uncertainty_requires_abstention_near_threshold`
- `scientific_decision_critic_reverifies_sources`

Le prochain jalon scientifique doit relier des mesures
**réellement autorisées et vérifiées** à des politiques
de décision explicables, puis mesurer par expérimentation
contrôlée l'amélioration apportée par HEX-CORTEX à
plusieurs cerveaux IA interchangeables, sans confondre
la robustesse d'un outil avec la vérité scientifique.
