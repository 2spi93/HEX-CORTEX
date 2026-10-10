# HEX-CORTEX V21 — Évaluation comparée cerveau seul vs cerveau + cortex

## Mission

Tester de façon reproductible si notre **armure cognitive
universelle** améliore un modèle IA quelconque, sans confondre
une simulation de test avec une expérience réelle.

Ce module n'appelle aucun modèle ; il accepte seulement des
captures d'évaluations **appariées** provenant de deux
configurations du **même fournisseur, modèle, révision,
question et paramètres de génération**.

## Essai synthétique inclus

```powershell
git switch main
git pull --ff-only origin main
python -m pip install -e ".[dev]"

hexcortex-amplification-eval --pairs examples/paired_science_v21_synthetic.json --approve-read --pretty
```

Le jeu contient **trois paires complètement fabriquées** par
les tests, avec des « réponses » math/physique/chimie, coûts
et latences factices. Il démontre la **fonction de scoring
et les refus**, **pas** une amplification de modèle réel.
Même un `delta_accuracy` positif dans cet exemple ne
doit pas être présenté comme un progrès d'HEX-CORTEX.

Les champs garantissent l'honnêteté :
`capture_mode: synthetic_fixture`,
`real_model_amplification_measured: false`,
`real_model_calls_independently_attested: false`,
`causal_effect_certified: false`.

Sans `--approve-read`, aucun fichier n'est consulté.

## Format des données

`PairedEvaluation` possède :
- `protocol_version` et `dataset_id` ;
- `dataset_sha256` déclaré (non preuve d'intégrité
  indépendante) ;
- `items[]` : `task_id`, domaine, hash de la **même
  question**, corrigé tenu à l'écart du modèle, méthode
  d'évaluation `rational`, `exact_text`, `abstain`,
  découpage `held_out` déclaré ;
- `observations[]` : exactement deux réponses par item,
  `baseline` et `cortex`, même `provider`,
  `model_id`, `model_revision`,
  `task_sha256`, `settings_sha256`, coûts/jetons/latences.

Les captures peuvent être `synthetic_fixture` ou
`operator_supplied`. Même la seconde catégorie est
**non attestée**, faute de signature indépendante de
fournisseur, vérification de prompts cachés et revue des
résultats. Le rapport n'annonce **aucune amplification
réellement mesurée**.

## Métriques

- exactitude baseline et cortex par domaine ;
- cas résolus uniquement par cortex et uniquement par
  baseline (régressions) ;
- taux de justesse et différence appariée en fractions ;
- tokens, coûts déclarés et latence totale de chaque bras ;
- `mcnemar_exact_two_sided_p` : valeur p exacte pour
  les désaccords, **indicative** — ne corrige pas les
  dépendances, multiples tests, fuite du corrigé,
  sélection des questions ou provenance incertaine.

## Étape pour obtenir un vrai résultat scientifique

Le protocole et le code de scoring étant prêts, il faut :

1. pré-enregistrer des tâches nouvelles et leurs oracles,
   idéalement gérés par un évaluateur indépendant ;
2. capturer la même version exacte d'un modèle avec et
   sans cortex, fixer les paramètres (ou employer des
   paires randomisées de seeds) et contrôler l'ordre ;
3. enregistrer les coûts complets, latences, appels outils
   et refus ; ne pas utiliser les réponses attendues comme
   contexte de l'agent ;
4. rendre plusieurs essais et diverses familles de tâches ;
5. examiner les erreurs, les régressions et les différences
   d'intensité calculatoire ; publier les cas où le cortex
   **n'aide pas** ;
6. ne pas prétendre à un effet causal avant attestation,
   contrôle de contamination et revue indépendante.

Le modèle local n'est **pas obligatoire** : des captures
de fournisseurs hébergés avec consentement peuvent être
évaluées ultérieurement. La V21 ne sollicite aucune API,
n'occasionne aucun coût cloud et n'exécute jamais du
code non fiable.

## JEPA sans fausse implémentation

`cortex_jepa_latent_contract_v21.py` apporte une interface
de vecteurs latents `predicted_latent` / `observed_latent`
bornés, avec identité SHA-256 des encodeurs/prédicteurs
déclarée, horizon explicite et erreurs MAE/MSE exactes.

C'est un **contrat de mesure**, **pas** une implémentation
de I-JEPA, V-JEPA 2.1 ou LeWorldModel. La suite nécessitera
l'exécution d'un vrai modèle externe, des observations,
des splits, des métriques de collapse, un contrôle de
provenance des poids et des essais indépendants.

Voir la revue stratégique :
`docs/OPENAI_MATH_2026_LECUN_WORLD_MODELS_V21.md`.

## Validation

```powershell
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

La readiness peut valider les invariants d'appariement et
l'absence de gain artificiellement certifié, mais **elle
ne peut pas** valider de véritable gain de cognition
sans faire appel à un modèle et à une évaluation externe.
`production_ready` reste `false`.
