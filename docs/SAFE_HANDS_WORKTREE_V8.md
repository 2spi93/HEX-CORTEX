# HEX-CORTEX — Hands V8 : worktree et vérification sûrs par défaut

## Pourquoi ce changement

Le code de `hexcortex-code` permettait de lancer `pytest` dans un
worktree Git après une autorisation opérateur. Un worktree **isole les
changements Git**, mais n'est pas un environnement d'exécution isolé.
Un test Python peut ouvrir les fichiers de la machine ou exécuter du code.

Le mode automatique garde donc uniquement une vérification **statique**
(`ruff`) ; `pytest` et `compileall` sont désormais refusés
par `run_allowlisted_checks`, même lorsque l'opérateur a autorisé
une exécution. Cela évite qu'une autorisation d'outil générique soit
assimilée à un consentement éclairé à l'exécution de code non fiable.

Les tests Python du projet HEX-CORTEX que l'opérateur déclenche lui-même
dans son propre dépôt **de confiance** ne changent pas. Une future
exécution de tests générés ou externes nécessitera un bac à sable OS
explicite, par exemple une VM dédiée validée, pas simplement un worktree.

## Garanties ajoutées

1. `build_worktree_plan` choisit `["ruff"]` par défaut.
2. `create_isolated_worktree` **recalcule la totalité du plan** et
   vérifie le hash, les chemins, le nom de candidat et la référence ;
   un JSON modifié ou stale est refusé avant `git worktree add`.
3. `apply_reviewable_patch` et `run_allowlisted_checks` refusent
   un dépôt principal doté d'un dossier `.git`. Ils exigent un marqueur
   `.git` *fichier*, typique d'un worktree lié.
4. Aucun merge automatique ni accès shell arbitraire n'est accordé.
5. Les réponses de refus ne contiennent pas de contenu source de patch.

## Limites connues

Un marqueur `.git` de worktree n'est **pas une preuve d'isolation OS** :
des métadonnées Git pourraient être falsifiées par un acteur qui possède
déjà un accès local en écriture. Le contrôle ne signifie pas qu'un patch
est sûr sémantiquement. Il faut encore un avis humain, un rollback et des
tests réels dans un environnement sûr. La validation de la provenance
du worktree et des liens Git est à renforcer avant de fournir une
capacité complète à du code généré par un LLM.

## Vérification sans modèle ni sandbox

Depuis Windows PowerShell :

```powershell
git switch main
git pull --ff-only origin main
python -m pytest
ruff check .
hexcortex-readiness --pretty
```

`hexcortex-code worktree-plan` et `worktree-create` gardent leurs
validations. En revanche, la commande `worktree-check --check pytest`
doit maintenant **refuser** la demande pour absence de sandbox.

Cela n'interdit pas les tests du projet de confiance via `python -m pytest`
lancés manuellement depuis le dépôt de l'opérateur.
