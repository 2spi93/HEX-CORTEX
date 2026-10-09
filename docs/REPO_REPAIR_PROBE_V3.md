# HEX-CORTEX Repository Repair Probe V3 — mode local uniquement

Objectif : distinguer la capacite a repondre aux 13 questions historiques
du benchmark et la capacite a proposer une correction de plusieurs fichiers
Python. Ce module est **un prototype de validation comportementale**,
pas une certification de programmation autonome.

## Contenu

Quatre situations de programmation dans un depot virtuel :
- P&L : les frais doivent etre soustraits du profit ;
- risk floor : le reliquat de risque ne doit jamais etre negatif ;
- correction sur deux fichiers : une fonction de risque et son appelant ;
- division par zero : gestion des cas sans trades.

Les jeux de test sont deterministes avec `--seed` (par defaut 20261009).
Chaque situation dispose de 15 entrees d'evaluation, dont des cas aux
limites. Les resultats sont ventiles entre `validation` et `holdout`.

**Important :** les exercices et les oracles sont dans un depot public,
donc ils sont inspectables. Le mot `holdout` signifie uniquement que les
valeurs de test ne figurent pas dans les prompts. Ce n'est PAS un examen
prive ou une preuve d'absence de fuite de benchmark.

## Securite

- Le candidat fournit strictement un objet JSON avec `files` contenant
  le texte complet de chaque fichier autorise.
- Le code modele est analyse en AST puis evalue uniquement dans un
  interpreteur tres limite, supportant les operations arithmetiques et
  logiques simples, les fonctions pures et quelques builtins allowlistes.
- Aucun code modele n'est lance par `exec`, `eval`, Python subprocess,
  shell, pytest ou un runner de patch.
- Aucune modification du depot, aucun clonage ni ecriture temporaire.
- La limite d'entree est de 32 Ko par reponse, 12 Ko par fichier.
- Les rapports ne contiennent ni prompts ni sources generes ;
  pas de remontée automatique dans les priorites de routage.
- Les chemins des fichiers remplaces doivent correspondre exactement au
  manifeste de l'exercice.

## Utilisation

Installer les nouveaux points d'entree une seule fois apres git pull :

    python -m pip install -e ".[dev]"

Lister les situations :

    hexcortex-repo-eval --model-id local --digest sha256:DEMO --quantization Q4 --show-tasks

Avec le modele reellement installe dans Ollama, sous Windows :

    ollama list

    hexcortex-repo-eval --model-id qwen2.5-coder:7b --digest sha256:REEL --quantization Q4_K_M --hardware ryzen9900x-cpu --approve-model

Le nom, l'empreinte et la quantification sont des exemples a remplacer
par des donnees verifiees. Cette commande appelle localhost Ollama de
maniere explicite, une fois par exercice. La collecte n'ecrit aucun
fichier local et ne requiert aucun GPU.

Pour mesurer des reponses pre-existantes, sans faire tourner de modele :

    hexcortex-repo-eval --model-id offline --digest sha256:DEMO --quantization Q4 --responses path/to/responses.json

Le fichier JSON en entree doit associer chaque identifiant de tache a une
chaine JSON de la forme :

    {
      "fees_sign": "{\"files\": {\"calc/pnl.py\": \"def net_pnl(gross, fees):\\n    return gross - fees\\n\"}}"
    }

Les autres cas sont evalués en echec lorsqu'ils sont absents. Rien n'est
execute depuis le fichier de reponses.

## Lectures du score

- `passed_count` et `overall_score` : tests completement reussis.
- `holdout_score` : proportion de cas `holdout` reussis.
- `correct_cases` : nombre de jeux d'entree dont la valeur retour
  correspond a l'oracle.
- `routing_prior_authorized: false` : aucune utilisation automatique
  par le routeur. C'est volontaire.
- `quality_label` : `restricted_ast_repository_probe_not_certified`.

## Ce que ce benchmark n'evalue PAS

- edition reelle de depots, worktrees ou gestion de conflits Git ;
- execution de tests Python arbitraires fournis par le modele ;
- algorithmes complexes, Pydantic, pytest, lectures de gros depots ;
- attaques de contexte, recherche ou autonomie prolongée ;
- memoire, consommations VRAM sur materiel reel et cout total.

La prochaine evolution pourra examiner des reparations sur un depot
isole par un bac a sable OS pour executer de vrais tests, uniquement
apres audit des permissions. Aucun serveur n'est envisage.
