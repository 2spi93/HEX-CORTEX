# HEX-CORTEX Command Center V5 — projet réellement connu du chat CPU

## Motivation opérateur

Les captures Windows V4 attestent un vrai chat Ollama, une vision V40 consultable, un journal dédié V42/V43 vérifié et un probe LocalHarness opérationnel. Mais Qwen décrit des capacités génériques (dont la recherche Web) absentes du chat. La reconnaissance vocale navigateur remonte aussi une erreur asynchrone sseError not found. Des modèles 14B prennent environ 33 secondes sur CPU selon une capture.

## Ce qui est intégré

- Route GET /api/project/brief : résumé factuel borné, relu depuis le snapshot existant et le registre des périphériques. Marque comme non vérifiés les journaux ou reçus absents/dégradés. Fournit source ids et SHA256 du dossier. Pas de lecture libre de fichiers.
- Hook réutilisable du serveur V3 : même Host/Origin et consentement par requête, mêmes limites de contexte, même LocalHarness CALL_MODEL, aucun outil. Le serveur produit seul les faits transmis au système de LocalOllamaBrain, jamais le navigateur.
- Réponses Ollama accompagnées de la provenance du contexte local, sans affirmer que la qualité sémantique est démontrée. La mémoire de conversation demeure temporaire.
- Nouvel onglet Connaissance & preuves : capacités connectées, comptes V40 et V42/V43, sources accessibles, limites et export manuel du dossier JSON.
- Échec connu du service de dictée Web Speech présenté comme une erreur du fournisseur vocal et non un crash global. Le navigateur peut contacter un service distant; ne pas lui dicter de données sensibles.
- Préférence du modèle qwen2.5:3b déjà installé lors de la découverte, pour diminuer le coût CPU sans empêcher l'utilisation volontaire de 14B. Caméra masquée correctement lorsqu'elle est coupée.

## Commandes PowerShell (une par ligne)

Arrêter le serveur V4 avec Ctrl+C avant la suite.

    git fetch origin
    git switch -c feature/command-center-v5-grounded-cognition-and-ux --track origin/feature/command-center-v5-grounded-cognition-and-ux
    $VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
    & $VP -m pytest -q tests/test_cortex_local_ollama_brain.py tests/test_cortex_command_center_v1.py tests/test_cortex_command_center_v2.py tests/test_cortex_command_center_v3.py tests/test_cortex_command_center_v4.py tests/test_cortex_command_center_v5.py
    & $VP -m ruff check .
    & $VP -m hex_cortex.memory.cortex_command_center_v5 --project-root . --port 8777 --enable-cpu-chat

Ouvrir http://127.0.0.1:8777/ et actualiser complètement (Ctrl+F5). Dans Connaissance & preuves, comparer les données aux aperçus et au journal. Dans Chat CPU, demander : Quelles sont réellement tes capacités HEX-CORTEX ? Peux-tu chercher sur le Web, modifier du code ou piloter un drone ? Précise les preuves. Si une réponse diverge, consulter directement GET /api/project/brief.

## Sécurité et limites

Le modèle est un raisonneur local CPU, non le moteur d'exécution du cockpit. Pas de capacités Web/MCP/Windows, de contrôle de périphériques physiques, d'autopromotion des skills, ni de preuve d'un vrai World Model 3D ou temporel. Les libellés d'objets et le texte des reçus ne sont pas promus comme instructions système. Les preuves d'intégrité ne mesurent pas la précision de segmentation.

## Extensions prioritaires parallèles

1. Segmentation photo approuvée MobileSAM CPU à partir d'une bbox, avec sha256 checkpoint, non-persistence par défaut, test IoU humain indépendant.
2. Voix française réellement offline (Whisper/Faster-Whisper CPU et Piper) séparée de Web Speech, mic push-to-talk uniquement.
3. Outils Code/MCP supervisés par registre existant, permissions et sandbox, aperçu avant application, aucune exécution silencieuse.
4. Découverte de périphériques uniquement en lecture/télémétrie avant appairage matériel, autorisation et arrêt d'urgence.
5. Streaming Ollama avec véritable annulation, budgets latence, mesure contre baselines, et amélioration ergonomique responsive.
6. World Model temporel validé sur scènes indépendantes, analyse des erreurs, suivi d'objet et contrôle de généralisation.

Références d'inspiration : OpenJarvis (https://github.com/open-jarvis/OpenJarvis/blob/main/docs/architecture/skills.md), Home Assistant Wyoming (https://www.home-assistant.io/integrations/wyoming). Les architectures sont étudiées; aucun code tiers recopié dans HEX-CORTEX.
