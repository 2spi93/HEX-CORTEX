# HEX-CORTEX V9 — Gateway, reprise des effets et rejouabilité

## Situation corrigée

Le Gateway lançait un adaptateur puis persistait un reçu. Si HEX-CORTEX
ou l'ordinateur s'arrêtait *après un effet externe mais avant la sauvegarde*,
un nouvel essai pouvait répéter cet effet sans savoir qu'il s'était déjà produit.
Le journal était aussi réécrit sans remplacement atomique.

## Mécanisme V9

Le Gateway écrit un enregistrement minimal `in_flight` **avant**
l'invocation d'un adaptateur autorisé. Il sauvegarde ensuite le résultat
final en remplaçant cette réservation dans la même transaction locale.

- L'ensemble lecture / recherche de doublon / réservation / exécution /
  finalisation utilise le verrou exclusif coopératif JSONL de V7.
- Le journal utilise le même `fsync` + `os.replace` atomique.
- Si le processus tombe ou subit une interruption au milieu de l'effet,
  l'enregistrement `in_flight` subsiste et interdit une répétition
  silencieuse au prochain appel identique.
- L'action suivante est
  `reconcile_unknown_external_effect_before_retry`.
  **Une vérification opérateur est indispensable** pour déterminer
  si l'effet a effectivement eu lieu, avant toute intervention.
- Si une réservation ne peut pas être écrite, l'adaptateur
  **n'est pas appelé**.
- Les effets d'un adaptateur dont la durée observée dépasse son budget
  sont marqués comme non terminés, sans prétendre les annuler.

## Limites et sécurité

Ce mécanisme vise l'idempotence *conservatrice* pour des processus qui
emploient le Gateway, pas une transaction distribuée ou une garantie
matérielle d'« exactly once ». Un adaptateur peut produire un effet
non annulable avant son arrêt. L'horloge mesure après le retour :
un callback Python synchrone bloqué n'est pas préempté.

Le verrou peut rester après une extinction brutale. Ne le supprimer
que lorsque l'absence d'écrivain concurrent est confirmée. Après
un crash, une réservation `in_flight` ne doit pas être éliminée
automatiquement. Les actions produisant des effets réels restent
soumises à des permissions de l'hôte et à une revue humaine.

Aucun LLM local, serveur HEX-CORTEX, benchmark, compte cloud ou
GPU n'est requis pour les tests V9.

## Contrôles

```powershell
git switch main
git pull --ff-only origin main
python -m pytest
ruff check .
hexcortex-readiness --pretty
```

Les tests V9 simulent une interruption brutale, un disque non
disponible, un verrou concurrent et un dépassement de délai.
Les effets réels des adaptateurs ne sont **pas** déclenchés en CI.
