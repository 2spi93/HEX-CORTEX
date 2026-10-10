# HEX-CORTEX V7 — mémoire durable et apprentissage contrôlé

## Portée

Cette étape ne nécessite ni Ollama, ni GPU, ni benchmark IA, ni serveur.
Elle fiabilise les quatre historiques déjà existants :

- `cortex-learning-event.jsonl` ;
- `cortex-skill-candidate.jsonl` ;
- `cortex-skill-library.jsonl` ;
- `cortex-skill-library-promotion-gate.jsonl`.

## Garantie de sauvegarde locale

Les opérations modifiées utilisent une exclusivité locale par répertoire
`.write-lock`, un fichier temporaire dans **le même dossier**, un
`flush`, un `fsync` et `os.replace`. Ainsi, une panne survenant
avant le remplacement conserve les octets précédents et élimine les
fichiers temporaires en cas d'exception ordinaire. Sur Windows et Linux,
l'intégrité de la sauvegarde est couverte par des tests de panne simulée.

La modification de l'historique n'est pas rendue atomique **entre
plusieurs fichiers différents** : chaque JSONL possède sa transaction
individuelle. Les processus qui ignorent le verrou ne sont pas protégés.
`fsync` et `os.replace` ne remplacent pas des sauvegardes externes.
Une coupure électrique extrême et des limites des systèmes de fichiers
ne sont pas équivalentes à une base SQL transactionnelle.

Un blocage `jsonl_writer_already_active_or_crash_lock` indique
qu'un autre écrivain coopératif utilise le dossier ou qu'un ancien
verrou subsiste après un crash. **Ne supprimer le verrou qu'après avoir
vérifié qu'aucun processus n'écrit actuellement**. Il n'est jamais
« automatiquement volé ».

Les événements d'apprentissage sont dédupliqués par `learning_id`,
les candidats par `candidate_hash`, et la création de bibliothèque
et de gate vérifie l'unicité pendant l'opération verrouillée.

## Apprentissage vérifiable, pas autopromotion

Les anciennes fonctions peuvent inscrire un candidat ou une entrée
de bibliothèque **inactive** après un seul épisode conforme. Leurs
noms historiques `promote_to_skill` et `promote_to_library`
désignent ici une *éligibilité de proposition*, pas une promotion
prouvée ni une activation autonome.

Le nouveau contrôle
`memory/cortex_skill_evidence_review_v7.py` exige, par défaut :

1. une autorisation opérateur de consulter le profil ;
2. un candidat unique et un chaînage source IDs / hashes intègre ;
3. au moins **3 observations distinctes** d'une même règle de travail ;
4. au moins **2 contextes identifiés** par des références source distinctes ;
5. des événements admis, cohérents, positifs/corrigés et dans le même profil ;
6. un vérificateur externe *injecté par l'hôte* qui confirme chaque
   observation d'après une preuve réelle.

Le résultat maximal est **`reviewable_not_promoted`** avec
`skill_promoted=false` et `skill_activated=false`. Aucune écriture
n'est effectuée par ce contrôle, même si toutes les étapes passent.

**Limites épistémiques :** le format historique ne prouve pas
l'indépendance de deux modèles différents, ni la provenance d'une
référence externe simplement déclarée. Un callback acceptant toujours
`True` est une simulation, pas une certification. Seul un hôte
extérieur disposant de résultats de tests indépendants peut attester
réellement les observations.

## Commandes de vérification

PowerShell depuis `C:\Users\2spi\HEX-CORTEX` :

```powershell
git switch main
git pull --ff-only origin main
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
hexcortex-readiness --pretty
```

Dans le rapport de préparation, rechercher deux nouveaux contrôles :

- `atomic_learning_memory_roundtrip: true` ;
- `unapproved_learning_review_denied: true`.

Ils ne nécessitent aucun modèle, compte externe ou benchmark.

## Suite nécessaire avant clôture de la release

- isolation effective des actions de codage/worktree et contrôle d'accès
  indépendant des callbacks ;
- reprise sur incident à l'échelle de **plusieurs** fichiers (transaction,
  recovery journal ou base adaptée), restauration/versioning et sauvegardes ;
- intégration réelle de l'observateur, du critic, des compétences, du
  replay et de la recherche mémoire sur des mêmes cas de développement ;
- interopérabilité MCP/A2A contre clients de référence ;
- audit de release et tests système Windows non simulés.

Ne pas déclarer « `production_ready: true` » avant l'acceptation
documentée de ces points.
