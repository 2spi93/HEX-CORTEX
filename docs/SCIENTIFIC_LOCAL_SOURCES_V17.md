# HEX-CORTEX V17 — Sources scientifiques locales réellement vérifiées

V16 a apporté le classement par sources, la normalisation des unités SI,
les intervalles d'incertitude et la gestion des contradictions.

**V17 va plus loin :** le moteur peut vérifier réellement les **octets
d'un document local**, son SHA-256 et la concordance exacte avec les
champs de son `EvidenceRecord`. Il le fait sans accès au réseau,
sans modèle local ni externe et sans exécution de code dans le
document. Un hash calculé depuis des octets réels vaut davantage
qu'un hash simplement déclaré par l'IA ; mais il **ne constitue pas
une preuve d'authenticité de l'éditeur**.

## 1. Démonstration utilisable dans PowerShell

Depuis le dépôt, après `git pull` et
`python -m pip install -e ".[dev]"` :

```powershell
hexcortex-knowledge --manifest examples/scientific_v17/manifest.json --sources-dir examples/scientific_v17 --claim-id demo_velocity --domain physics --unit m/s --approve-read --pretty
```

Attendu :

- `status: consistent_evidence_not_certified` ;
- `interval_lower: 99` et `interval_upper: 101` ;
- `host_checked_source_count: 2` ;
- `truth_certified: false`,
  `source_independence_certified: false`,
  `physical_action_authorized: false`.

**Les fichiers `examples/scientific_v17/` sont des exemples
synthétiques et ne représentent pas de vraies mesures.** Le premier
indique `100 ± 2 m/s` et le second `1/10 ± 1/1000 km/s`.
La valeur et l'incertitude de la deuxième source sont converties
exactement en m/s ; l'intersection est [99, 101].

Pour constater le refus initial :

```powershell
hexcortex-knowledge --manifest examples/scientific_v17/manifest.json --sources-dir examples/scientific_v17 --claim-id demo_velocity --domain physics --unit m/s --pretty
```

Sans `--approve-read`, la commande refuse avant de lire le manifeste.

## 2. Contrat local

`LocalScientificEvidenceVerifier` choisit par son hôte
une racine de sources ; seul `<source_id>.json` peut être lu,
après vérification de la forme du nom. Un témoin est un document
JSON canonique avec les métadonnées du résultat.

Pour chaque source :
- fichier ordinaire ; refus des liens symboliques ;
- lecture plafonnée à 16 Kio ; manifeste plafonné à 64 Kio
  et 32 enregistrements ;
- empreinte des **octets** comparée à
  `source_digest_sha256` issu du manifeste ;
- comparaison intégrale des champs structurés de l'enregistrement
  avec le document stocké ;
- refus des sources manquantes, altérées, incohérentes,
  trop volumineuses et des identifiants non conformes ;
- aucune ouverture de `source_uri`, aucun import ou eval,
  aucune mutation du checkout.

Il s'agit d'une validation de **cohérence et intégrité des sources
locales**. Les identifiants, URLs, licences, révisions et dates
sont fournis par le détenteur du corpus. Un fichier malveillant
auto-signé par son auteur peut toujours avoir un hash valide ;
**V17 ne prouve pas la vérité ni l'indépendance scientifique**.

Les sources réellement utilisées nécessiteront une gouvernance
des corpus (accès, versioning, validation indépendante,
licences, mises à jour, révocation et contrôles de provenance).

## 3. Test de reprise et altération

La CI crée ses propres sources temporaires et couvre :
- octets intacts → vérification locale ;
- modification d'une valeur après empreinte → refus ;
- manifeste altéré, digest faux → refus ;
- lien symbolique → refus ;
- source absente, grande taille → refus ;
- identifiant de fichier malveillant après `model_copy(update=...)`
  → refus au niveau de la frontière fichier ;
- désaccord entre deux documents cohérents mais incompatibles
  → `conflict` ;
- sortie JSON de la CLI et absence d'autorité sur matériels.

Les exemples suivis par Git sont préservés en octets exacts
par une règle `.gitattributes` pour éviter les transformations CRLF.

## 4. Normes et limites

Le contrat reste inspiré de la structuration de la provenance W3C
PROV-O et du champ provenance/licence des principes FAIR.
Il ne prétend pas valider toutes leurs spécifications.

- https://www.w3.org/TR/prov-o/
- https://www.nature.com/articles/sdata201618
- https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values

**Pas de lecture web implicite, pas de credentials, pas de modèle local,
pas de VPS, pas de calcul chimique ou physique additionnel dans V17,
pas de commande physique.**

Prochaine intégration scientifique : organiser une bibliothèque
versionnée de sources sélectionnées et des révocations, puis
les relier aux organes scientifiques par leurs identifiants
de revendications et des outils externes *explicitement* autorisés.
