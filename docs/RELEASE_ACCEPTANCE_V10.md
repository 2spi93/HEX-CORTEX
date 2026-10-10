# HEX-CORTEX — dossier de livraison V10 et critères d'acceptation

**Décision opérateur du 10 octobre 2026 :** finir l'ingénierie logicielle sans
utiliser de modèle local, sans benchmarking IA, sans nouveau PC et sans serveur
HEX-CORTEX. Les modèles OpenAI/Anthropic restent optionnels, consentis et
facturés séparément; aucune clé n'est nécessaire pour le noyau.

## Commande de vérification et dossier de preuves

La commande `hexcortex-release-audit --pretty` lit une liste **fixe** des
composants indispensables, calcule leurs empreintes SHA-256, exécute les
smokes déterministes hors ligne déjà utilisés par
`hexcortex-readiness`, et affiche l'état des preuves.

Le rapport distingue :
- `core_offline_verified` : présence des composants et smokes fonctionnels ;
- `overall_release_certified` : **false** tant que les exigences externes
  et l'isolation réelle ne sont pas validées ;
- `pytest_ruff_windows_linux` : nécessitent une preuve distincte de CI
  GitHub, car la commande ne lance pas les tests ;
- les contrats logiciels simulés, les APIs cloud non testées, la recherche
  avancée différée, et les fonctions désactivées par sécurité.

Il n'envoie aucun prompt, ne charge aucun modèle et n'exécute aucun
correctif de code produit par un LLM.

## Matrice d'acceptation : six jalons explicites

| Bloc | État vérifiable | Critère pour passage à « validé » |
|---|---|---|
| Clock, Router, Registry, Workspace, Spine | Tests et intégration hors ligne | Tests unitaires et CI verts; chaîne d'événements intègre |
| Historique d'apprentissage et Gateway | Journaux atomiques par fichier | Tests d'interruption et refus de rejouer un effet incertain |
| Mémoire multi-fichiers | **Non certifiée** | Transaction ou journal de reprise cohérent entre fichiers et test de restauration |
| Coding/Hands | Ruff statique autorisé; Python non fiable bloqué | Environnement OS réellement isolé, contrôle de provenance et de patch, test end-to-end |
| MCP et A2A | Sous-ensembles locaux, fixtures déterministes | Tests de conformité avec SDK officiels et protocole dans les deux sens |
| API cloud | Adaptateurs/mocks testés | Appels réels sous consentement avec clé, coûts, quotas et gouvernance de confidentialité |

Les modules CR-JEPA, V-JEPA, distillation, LoRA, entraînement de petits modèles
et benchmarking local appartiennent à la **recherche**, pas à la validation
bloquante de ce noyau.

## Durabilité de CanonicalSpine (V10)

La spine persistante :
- sérialise maintenant chaque snapshot via fichier temporaire + fsync +
  remplacement atomique, sous verrou coopératif exclusif ;
- rejette la sauvegarde d'une chaîne corrompue ou d'un snapshot qui
  remplacerait un historique plus récent ou divergent ;
- vérifie la continuité du chaînage avant d'ajouter un événement ;
- accepte un retry idempotent d'un *même* event_id à contenu identique,
  mais refuse une collision entre identifiants.

Les tests simulent une panne de remplacement et une altération sur disque.
Ce n'est pas une garantie cryptographique d'origine des événements (un
attaquant pouvant réécrire et recalculer toute une chaîne peut la falsifier),
ni une sauvegarde multi-fichiers transactionnelle.

## Nouvelles normes à intégrer aux futurs rails

Au 10 octobre 2026, la documentation MCP officielle a publié la révision
**2026-07-28** (noyau stateless, demandes multi-round-trip, gestion de tâches
en extension, autorisation renforcée, dépréciations). A2A publie une
spécification **1.0.0** avec des modèles de données et bindings plus riches.
Le sous-ensemble A2A local actuel n'est **pas certifié 1.0.0**, et
l'utilisation du nom d'une méthode MCP ne démontre pas la conformité.

Sources primaires :
- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://a2a-protocol.org/latest/specification/

## Procédure opérateur finale

Depuis PowerShell dans le dépôt de confiance :

```powershell
git switch main
git pull --ff-only origin main
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
hexcortex-readiness --pretty
hexcortex-release-audit --pretty
```

Le dernier rapport doit comporter `core_offline_verified=true` lorsque
le code source attendu et tous les smokes sont présents, ainsi que
`production_ready=false` et `overall_release_certified=false`
jusqu'à la fin des preuves externes.

Ne pas supprimer les `.write-lock` sans confirmer qu'aucun écrivain
ne tourne. Ne pas réexécuter une intention Gateway `in_flight` sans
reconcilier son effet. Ne pas lancer automatiquement pytest sur un
worktree contenant du code non fiable.

## Procédure de fermeture du chantier

Une release hors ligne peut être candidate lorsque le manifeste local
est vert, que les deux CI sont verts, que les limites sont documentées et
que l'opérateur possède un plan de restauration. Le label « produit
autonome terminé », lui, attend une preuve spécifique des interactions
réelles avec les outils, les SDK, un environnement isolé, et les
résultats du code. **Ne pas inférer une capacité d'intelligence ou
une supériorité concurrentielle à partir du nombre de tests.**
