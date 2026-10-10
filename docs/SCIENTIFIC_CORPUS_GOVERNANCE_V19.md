# HEX-CORTEX V19 — Gouvernance versionnée et révocation du corpus scientifique

## Objet

V16 sait comparer les données scientifiques et détecter les contradictions.
V17 sait contrôler les octets de sources locales, et V18 sait les faire
vérifier par le Critic au sein du CognitiveCircuit.

La V19 ajoute un **registre de gouvernance** à historique chaîné :
elle décide quelles versions de sources sont **admises** ou **révoquées**.
Un document parfaitement intact ne doit plus servir de preuve
si son admission a été retirée ou si une nouvelle révision remplace
celle sur laquelle le système s'appuyait.

Cette approche s'inspire notamment de la mémoire immunitaire : le
cortex doit pouvoir conserver un signal de méfiance à propos d'une
source auparavant utilisée. C'est une analogie d'ingénierie ; aucune
efficacité biologique n'est revendiquée.

## Mécanisme exact

Le registre JSON contient au maximum 128 événements typés :
`sequence`, `operation` (`admit` ou `revoke`), `source_id`,
`revision`, `record_sha256`, `previous_hash` et `event_hash`.

- **Admettre** associe une version croissante à une empreinte
  complète de l'`EvidenceRecord` (incluant le hash des octets
  source, sa version, son URL, sa licence, sa date, sa valeur
  et l'incertitude).
- **Nouvelle révision** : un même identifiant peut recevoir une
  version numérotée supérieure, mais son ancienne version n'est
  alors plus acceptée.
- **Révoquer** : exige une source admise et les identifiants,
  version et empreinte exacts de cette admission.
- **Vérifier la chaîne** : rejoue tout l'historique, recalcule les
  hashes, vérifie l'ordre et les transitions.
- **Empreinte de tête épinglée hors registre** : le programme exige
  un hash final donné séparément par l'opérateur. Modifier,
  tronquer ou remplacer le registre sans mise à jour du hash
  de confiance produit un refus.
- **Vérification finale** : chaque lecture de preuve par V18, y
  compris lors du passage du Critic, revérifie ce registre
  et les octets réels des sources.

Les hashes rendent le changement d'historique *détectable
si la tête de confiance a été protégée séparément*. Ils ne
constituent **ni une signature numérique, ni une autorité
institutionnelle, ni une garantie de vérité scientifique**.

## Commande de démonstration Windows

Un registre **synthétique** correspondant exactement aux deux
documents d'exemple de V17 a été créé dans
`examples/scientific_v19/ledger.json`.

Depuis le dépôt après `git pull` et
`python -m pip install -e ".[dev]"` :

```powershell
hexcortex-science-governed --ledger examples/scientific_v19/ledger.json --pin 8eadc291e08d7292c07519c955fa4e52611577dc57f25a16f962c2c42c6a44c5 --manifest examples/scientific_v17/manifest.json --sources-dir examples/scientific_v17 --claim-id demo_velocity --domain physics --unit m/s --approve-read --pretty
```

Attendu : `status=verified`,
`corpus_external_pin_verified=true`,
`spine_verified=true`,
`scientific_truth_certified=false`,
`physical_action_authorized=false`.

**Important :** le hash indiqué dans cette documentation est
correct pour le *jeu d'exemples versionné*. Le fait de stocker
le pin dans le même dépôt que le registre reste une démonstration,
**pas une protection contre un adversaire pouvant remplacer tout
le dépôt**. Dans un usage réel, l'empreinte attendue doit être
protégée dans une infrastructure de confiance séparée,
avec gestion des changements autorisés.

Une variante avec empreinte erronée doit retourner
`corpus_externally_pinned_head_mismatch`.

## Simulation de révocation et de retour arrière

Les tests de V19 vérifient réellement :

1. Deux sources valides avec octets locaux corrects et politique
   admise → circuit V18 vérifié.
2. Révocation de la source beta dans le registre, sans altérer
   ses octets → refus de la preuve.
3. Ancien registre réintroduit alors que le pin externe correspond
   à une révision plus récente → refus de la tentative de rollback.
4. Admission d'une nouvelle révision → l'ancien contenu n'est
   plus admis.
5. Révocation **entre les deux passages de la cellule et du
   Critic** → verdict final bloqué, sans modifier la Spine.
6. Événement ancien modifié, réordonné, de source inconnue,
   double révocation, révision non croissante → refus.
7. Sans approbation, la CLI ne lit aucun document ; sans fichier,
   avec lien symbolique ou avec registre trop volumineux → refus.

Ces résultats sont des simulations de politique de gouvernance
et des contrôles sur fichiers locaux, pas des essais en
laboratoire, une validation de corpus institutionnel ni un
benchmark de gain intellectuel du modèle IA.

## Périmètre et prochaines étapes

- Le registre est **en lecture seule** pour ce parcours. Le module
  permet de fabriquer des événements candidats en mémoire, mais
  ne fournit pas encore de workflow authentifié d'administration
  ni de signature des admissions/révocations.
- Aucun serveur, modèle local, GPU, API payante ou accès réseau
  n'est nécessaire.
- Des copies d'une même publication peuvent correspondre à deux
  `source_id` distincts : l'indépendance des producteurs
  **n'est pas vérifiée**.
- Les droits de redistribution et l'authenticité des licences
  **ne sont pas prouvés** par la simple présence de métadonnées.
- Il restera à apporter des signatures d'éditeurs ou attestations,
  une politique de révocation distribuée, un catalogue
  scientifique réel autorisé et une propagation d'incertitude
  vers les décisions des autres organes.
- La V19 ne modifie jamais automatiquement un fichier du projet,
  ne promeut pas de compétence ni ne commande un appareil.

## Validation opérateur

```powershell
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

Deux nouveaux contrôles seront visibles :
`scientific_corpus_revocation_blocks_valid_source` et
`scientific_corpus_external_pin_denies_history_rollback`.

La `production_ready` globale doit demeurer `false` ;
elle exige notamment les validations de sécurité et
d'interopérabilité indépendantes encore manquantes.
