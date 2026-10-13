# HEX-CORTEX — Command Center V3 : conversation CPU à contexte borné

## Pourquoi cette étape

L'opérateur a exécuté V2 sur son PC : plusieurs modèles Qwen2.5 via Ollama CPU, cinq masques MobileSAM, 13 événements d'une chaîne CanonicalSpine locale vérifiée, et un probe LocalHarness / repo_manifest terminé sans écriture. Les captures prouvent que V2 répond aux messages, mais elles ne prouvent **pas** une continuité conversationnelle, car chaque requête de V2 est isolée.

V3 ajoute une mémoire **temporaire du dialogue**, distincte de la mémoire CanonicalSpine, sans modifier le modèle ou créer de nouveau système de mémoire durable.

## Composants repris de l'architecture

- LocalOllamaBrain existant : transmet des messages correctement séparés system / user / assistant / user au vrai Ollama local. En absence d'historique, le comportement reste celui de V2.
- LocalHarness : mêmes permissions, un appel de modèle approuvé à la fois, aucun outil, commande, fichier ou déploiement.
- CommandCenterV2Server : mêmes restrictions Host/Origin/Fetch-Site et loopback uniquement ; nouveau endpoint explicitement autorisé, sans ouvrir les autres routes POST.
- Trois échanges complets précédents au maximum (6 messages, 600 caractères chacun) et 1 600 caractères pour la nouvelle question. Le modèle reçoit les rôles exacts, pas un journal textuel non typé.
- Bouton « Nouvelle conversation », effacement automatique du contexte au changement de modèle, statut indiquant le nombre d'échanges réellement réutilisés. Correction du faux bandeau « Aucun modèle exécuté ».
- État conservé uniquement dans l'onglet navigateur. Aucun chat sur disque, aucun historique durable, aucun identifiant CanonicalSpine inventé. L'historique est fourni par le navigateur et n'est pas une preuve vérifiée.

Cette version ne prétend toujours pas intégrer le streaming, la vraie interruption de calcul en cours, STT/TTS local, le wake-word, les outils MCP, la télécommande Windows, le World Model ou la mémoire longue durée.

## Installation — PowerShell (une commande par ligne)

Arrêter le serveur V2 avec Ctrl+C avant de changer de branche :

~~~powershell
git fetch origin
git switch -c feature/command-center-v3-conversation-continuity --track origin/feature/command-center-v3-conversation-continuity
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_local_ollama_brain.py tests/test_cortex_command_center_v1.py tests/test_cortex_command_center_v2.py tests/test_cortex_command_center_v3.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_command_center_v3 --project-root . --port 8777 --enable-cpu-chat --dry-run
& $VP -m hex_cortex.memory.cortex_command_center_v3 --project-root . --port 8777 --enable-cpu-chat
~~~

Ouvrir ensuite http://127.0.0.1:8777/ et choisir Chat CPU, Rechercher les modèles Ollama et un modèle déjà installé de préférence qwen2.5:3b.

Test : envoyer successivement « Mon projet s'appelle HEX-CORTEX. », puis « Quel est le nom de mon projet ? » ; le deuxième appel transmet le premier échange sous ses vrais rôles. Cliquer « Nouvelle conversation » ou changer de modèle et reposer la deuxième question : le contexte n'est plus transmis. Ces réponses d'IA ne sont pas des mesures indépendantes de mémoire à long terme.

## Trajectoire suivante

1. Streaming Ollama mesuré, interruption et budget, sans contourner le Harness.
2. Voix française locale STT/TTS, micro sur demande uniquement, sans écoute permanente.
3. Catalogue d'outils MCP effectivement installés, permissions séparées read/suggest/execute, inspection de signatures/licences.
4. Vue opérationnelle du pipeline Router, Workspace, Clock, Critic et Spine (réelles traces et replay).
5. World Model temporel, baseline et apprentissage des corrections sur séquences indépendantes.

Attention : le GPU RX 6700 XT de l'opérateur reste instable. V3 transmet num_gpu=0 à Ollama et continue le mode CPU. Les modèles 14B peuvent être lents ; commencer par Qwen 3B. Aucun composant tiers Jarvis n'a été recopié dans la base HEX-CORTEX.
