# HEX-CORTEX Command Center V2 — Audit Jarvis + intégration fonctionnelle

## État précédent (preuve opérateur 13 octobre 2026)

La V1 Command Center fonctionne réellement sur Windows : captures de l'utilisateur montrant **3 scènes, 5 aperçus MobileSAM et 13 événements dans un CanonicalSpine local vérifié** (V42 : 5, V43 : 8). Le probe du dépôt est encore à tester par l'opérateur. La V1 est un cockpit **lecture seule sans chat**, et non un Jarvis complet.

V2 est **une nouvelle tranche dans une branche dépendante de la PR #51**. Pas de copie aveugle des autres assistants.

## Recherche de composants Jarvis et décisions

| Projet | Capacités documentées pertinentes | Décision HEX-CORTEX |
| --- | --- | --- |
| open-jarvis/OpenJarvis (Apache 2.0) | registre de modèles/engines, agents, outils à spécifications, skills, traces et benchmarks coût/énergie | adopter les **principes** de catalogue, activation contrôlée, observabilité et comparaison, sans dupliquer l'architecture existante |
| sosoj92/jarvis-assistant-vocal (MIT selon son dépôt) | STT Whisper français, mot d'activation, TTS, permissions par niveau, intégrations Windows, panel local, budgets | prévoir une extension STT/TTS et outils Windows isolée; ne pas copier ses secrets ou son agent noyau |
| Gladiator07/JARVIS (MIT) | inspirations visuelles HUD et commandes système | inspiration graphique seulement |
| isair/jarvis (usage personnel/non-commercial par défaut) | chat/voix combinés, tray desktop, mémoire, catalogue MCP | idées d'UX seulement; **aucune réutilisation de code commercial sans licence** |

Les fonctionnalités amont sont documentées par leurs mainteneurs ; leur sécurité, leur maturité et leurs benchmarks ne sont pas approuvés par HEX-CORTEX.

## Nouvelles capacités V2

- Interface **par onglets**, responsive : il n'est plus nécessaire de faire défiler toute la page pour accéder aux fonctions; tous les composants V1 demeurent disponibles.
- **Catalogue de 10 composants** : connectés, code existant non exposé, désactivés, ou absents. Recherche instantanée. Aucun faux outil actif.
- **Chat réel Ollama CPU** : branche directement le `LocalOllamaBrain` et `LocalHarness` existants. Liste des modèles Ollama **uniquement après clic**; choix d'un modèle déjà installé, une requête par envoi volontaire, maximum 1 600 caractères, 256 tokens de sortie, 45 s, et une seule inférence CPU simultanée, `num_gpu=0`, `keep_alive=0`. Aucune commande, appel outil, mémoire durable ou envoi cloud. Les messages affichés restent uniquement dans le navigateur le temps de l'onglet.
- Pas de connexion automatique à Ollama au chargement, pas de démarrage de sous-processus, pas d'accès GPU. `--enable-cpu-chat` est **nécessaire** au lancement du serveur pour exposer les requêtes CPU, en plus de l'accord pour chaque envoi.

Le serveur est hérité du Command Center V1 pour conserver la restriction localhost `127.0.0.1`, les protections Host/Origin/Fetch-Site, CSP, et le refus des autres POST. V2 n'active pas les routes mutantes du serveur API HEX-CORTEX.

## PowerShell Windows — UNE commande par ligne

Dans `C:\Users\2spi\HEX-CORTEX`, arrêter l'ancien serveur par **Ctrl+C** dans son terminal avant de changer de branche. Conserver tous les dossiers `images/`, `weights/`, `receipts/`, et les scripts V38.

~~~powershell
git fetch origin
git switch -c feature/command-center-v2-cpu-chat-and-extensions --track origin/feature/command-center-v2-cpu-chat-and-extensions
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_command_center_v1.py tests/test_cortex_command_center_v2.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_command_center_v2 --project-root . --port 8777 --dry-run
~~~

Vérifier qu'Ollama fonctionne et qu'un modèle **texte** est déjà installé :

~~~powershell
ollama list
~~~

Vérification du statut de l'API de l'hôte local (sans lancer de modèle) :

~~~powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags | Select-Object -ExpandProperty models | Select-Object name
~~~

**Command Center V2, sans chat (mode par défaut) :**

~~~powershell
& $VP -m hex_cortex.memory.cortex_command_center_v2 --project-root . --port 8777
~~~

**Command Center V2, avec chat Ollama CPU explicitement activé :**

~~~powershell
& $VP -m hex_cortex.memory.cortex_command_center_v2 --project-root . --port 8777 --enable-cpu-chat
~~~

Ouvrir **http://127.0.0.1:8777/** directement dans Edge. Cliquer « Chat CPU », « Rechercher les modèles Ollama », sélectionner un **petit** modèle texte déjà installé (par ex. 1B–3B selon sa vitesse CPU), puis envoyer une question. Un clic sur `Catalogue d'outils` révèle les modules actifs et non connectés.

*Attention :* sur Ryzen 9 avec 32 Go de RAM, le coût CPU dépend de la taille du modèle ; commencer petit. Toujours **éviter la RX 6700 XT** instable : `num_gpu=0` est transmis au runtime Ollama. Les très gros modèles peuvent être extrêmement lents sur CPU. Si Ollama n'est pas lancé, le bouton « Rechercher les modèles » affiche une indisponibilité sans contacter Internet ni écrire de fichiers HEX-CORTEX.

V2 n'a toujours **pas** de micro, voix, TTS, actions Windows, appels web, service de recherche, mémoire de conversation longue durée ni agents persistants. Ne pas faire croire que les cartes statiques sont déjà des outils utilisables.

## Prochains investissements, classés par apport de valeur

1. **UX véritablement fluide** : streaming Ollama contrôlé, annulation et séparation des sessions, notifications et latences CPU, tests d'accessibilité, audit des tailles sur petits écrans.
2. **Voix française** : microphone optionnel, transcription faster-whisper et synthèse vocale Piper/Kokoro dans un environnement CPU séparé, boutons et permissions par capteur; pas de wake-word permanent par défaut.
3. **Catalogue d'outils MCP** : discovery de skills et extensions avec permissions `deny/read/suggest/execute`, versions et licences vérifiées, isolation des opérations sensibles et aucune exécution silencieuse.
4. **Opérations HEX-CORTEX internes** : suivi de tâches, logs, tests, modèle de coût, traces Router/Clock/Workspace et preuve de performance avec/sans Harness.
5. **World Model temporel** : panneaux d'avant/après/déplacement, IoU humaine, baseline comparative, replay de vraies corrections sans invention de résultats.

Aucune copie de code tiers Jarvis n'est incluse dans V2. Les API/modules déjà développés dans HEX-CORTEX sont réutilisés directement, pour éviter les collisions de routage et de mémoire.
