# HEX-CORTEX V16 — Scientific Knowledge Router, preuves et contradictions

## Objet

V13/V14/V15 ont introduit trois organes calculants : MathCell, PhysicsCell,
ChemistryCell. V16 leur donne un **contrat commun de connaissances
scientifiques** avec provenance, contrôle dimensionnel, incertitude et
détection explicite des désaccords entre sources.

Ce mécanisme est inspiré de :
- **W3C PROV-O**, classes de provenance Entity, Activity et Agent,
  https://www.w3.org/TR/prov-o/ ;
- les principes **FAIR** : données trouvables, accessibles,
  interopérables et réutilisables, notamment licences et provenance,
  https://www.nature.com/articles/sdata201618 ;
- les pratiques métrologiques **NIST** de séparation entre valeurs,
  unités, incertitudes et conventions d'expression :
  https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values

Le routeur n'implémente **pas** toutes les classes PROV-O ni ne
certifie qu'une ressource est FAIR. C'est un sous-ensemble de contrats
de sélection et de comparaison, hors ligne.

## Principes de conception

1. **Une connaissance n'est pas seulement une réponse.** Une
   `EvidenceRecord` contient domaine, concept, valeur, unité,
   incertitude absolue, catégorie (mesure, calcul, définition,
   hypothèse), source, version, empreinte, licence, date et URL HTTPS.
2. **Une source déclarée n'est pas une source authentifiée.**
   L'empreinte SHA-256 fournie par une IA ne prouve rien seule.
   Un vérificateur injecté par l'hôte doit contrôler les octets
   de la source, leur empreinte et leur correspondance avec
   la valeur revendiquée. Ce callback est une frontière de confiance :
   si l'hôte fournit `lambda _: True`, nous avons une simulation
   et **aucune preuve externe**.
3. **Les valeurs se comparent dans une unité canonique.**
   V16 autorise seulement quelques conversions rationnelles
   exactes entre unités de même dimension : m/cm/km, s/ms,
   kg/g, m/s et km/s, g/mol et kg/mol et certaines unités SI
   directes. Les conversions de température affine, les
   unités arbitraires ou ambiguës ne sont pas autorisées.
4. **L'incertitude est un intervalle**, `valeur ± erreur
   absolue`, exprimé en fractions exactes. Une mesure prétendue
   sans erreur est refusée. Les hypothèses sont distinguées
   des observations et ne peuvent compter comme preuve.
5. **Deux intervalles sans intersection sont contradictoires.**
   Le routeur retourne `conflict` au lieu d'inventer une
   moyenne ou de choisir le résultat à la majorité.
6. **Une seule référence ne suffit pas pour corroborer.**
   Deux identifiants de source distincts sont nécessaires.
   Ils ne garantissent **pas** que les organismes ou les données
   sources sont réellement indépendants.
7. **Même en cas d'accord**, l'état est
   `consistent_evidence_not_certified` : on constate une
   cohérence déclarative contrôlée par un hôte, pas
   la vérité scientifique ou la validité d'une expérience.

Les reçus ne contiennent ni URL source, ni texte brut des
prompts, ni licences privées, ni valeurs non vérifiées qui
pourraient être utilisées comme instructions. Ils possèdent
une empreinte déterministe de manifeste, des nombres
rationnels et des codes d'état.

## États déterministes

| Statut | Interprétation |
|---|---|
| `blocked` | Permission, source, dimension, date/format ou confiance insuffisants |
| `insufficient` | Un seul identifiant de source exploitable |
| `conflict` | Les intervalles des sources contrôlées ne se recouvrent pas |
| `consistent_evidence_not_certified` | Les intervalles se recouvrent ; aucun certificat de vérité |

Toutes ces sorties ont `truth_certified=false`,
`physical_action_authorized=false`, `model_used=false`.

## Trois raccordements de simulation

Les tests créent des **sources synthétiques**, non de vraies
publications de laboratoires, pour vérifier le contrat :

- **MathCell :** calcul réel de `1/3 + 1/6 = 1/2` et
  comparaison à une seconde écriture `2/4`.
- **PhysicsCell :** calcul réel de `100 m / 1 s = 100 m/s`
  puis conversion d'une seconde source `1/10 km/s`.
- **ChemistryCell :** calcul de masse molaire conventionnelle
  `H2O = 18.015 g/mol` et équivalence
  `0.018015 kg/mol`.

Les calculs sont exécutés, pas simulés par un modèle IA.
L'authentification des sources dans ces tests est, en
revanche, **un callback synthétique** (on ne prétend
pas valider une valeur en laboratoire).

## Simulation de contradictions (289 cas)

La grille explore **17 × 17 = 289 couples de sources**
aux valeurs comprises entre 92 et 108, avec
une incertitude absolue de ±1 pour chaque source.

Le résultat doit être `conflict` si la différence
de valeurs excède 2, et `consistent_evidence_not_certified`
sinon. On teste aussi les valeurs d'unités incompatibles,
les liens non HTTPS, les données mal formées, les nombres
illimités, les sources dupliquées, les exceptions arbitraires
et l'absence de permissions.

## Usage dans le noyau

`src/hex_cortex/core/cortex_scientific_knowledge_v16.py`

```python
from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceQuery, EvidenceRecord, review_scientific_knowledge,
)

# Une application hôte fournit les EvidenceRecord et un VRAI
# vérificateur de fichiers/source, pas un booléen fabriqué par le LLM.
result = review_scientific_knowledge(
    EvidenceQuery(claim_id="reference_speed", domain="physics", result_unit="m/s"),
    records=[],
    operator_approved=True,
    verify_source=trusted_host_verifier,  # défini par l'application hôte
)
# Aucun accès réseau et aucun acte physique. Liste vide => blocked.
```

La V16 n'effectue **ni téléchargement web, ni lecture automatique
de base documentaire, ni authenticité cryptographique garantie,
ni revue de publications par les pairs, ni recherche sémantique**.
Elle prépare l'orchestration de sources contrôlées par les futures
interfaces MCP, fournisseurs de données autorisés ou corpus local.
Les clés API ne sont pas nécessaires.

## Sécurité et limites

- Les callbacks de l'hôte sont considérés comme *de confiance* ;
  ils doivent eux-mêmes être isolés ou audités s'ils traitent
  du contenu externe. Leur seule valeur booléenne ne suffit
  jamais à prouver une indépendance institutionnelle.
- Deux sources différentes pouvant copier la même erreur,
  un résultat cohérent n'est pas un résultat vrai.
- Les résultats ne donnent aucun droit d'agir sur un drone,
  une machine, un laboratoire ou un système logiciel.
- Les dates et licences sont des métadonnées déclarées,
  pas une vérification d'authenticité.
- Pas de modèle local, pas de VPS, pas de réseau, pas de
  benchmark LLM, pas d'exécution arbitraire dans V16.

## Critère de validation

`hexcortex-readiness --pretty` ajoute :
- `scientific_provenance_conflict_detected`
- `unverified_scientific_source_denied`

`hexcortex-release-audit --pretty` référence le fichier
du routeur et ce dossier. La CI doit réussir sous Windows
et Ubuntu avec Ruff avant fusion.

Le prochain pas consiste à connecter un **véritable corpus
de sources documentaires contrôlées** et un lecteur en sandbox,
avec empreintes calculées sur les octets, licences et mises à
jour versionnées. L'index ou RAG ne doit jamais être confondu
avec une validation de vérité.
