# HEX-CORTEX Command Center V4 — Multimodal Device Lab (safe-by-default)

## Problème opérateur et objectif

Sur les captures V3, la page HTML est affichée, mais les compteurs restent vides, le bandeau dit « Chargement des données locales… », les sections ne se cachent pas et le catalogue ne se charge pas. V4 remplace **le JavaScript frontend concaténé V1+V2+V3 par un nouveau bootstrap autonome**, garde les API Python déjà prouvées et ajoute une erreur d'initialisation visible. Le code JS est parsé avec Node dans le test CI si disponible.

### Fonctions livrées, avec leurs limites explicites

| Module | Vraie fonction | Ce qui n'est PAS fourni |
|---|---|---|
| Chat / Harness | Ollama CPU avec 3 échanges contextuels, accès local et permissions; V3 réutilisé | Memory promotion automatique, tool execution, contexte permanent |
| Photo | Import local JPEG/PNG/WebP <=8 Mo et <=16 MP, affichage Canvas, sélection rectangle (XYXY en coordonnées source), export JSON, crop PNG et image | Détection automatique d'objets, segmentation MobileSAM depuis ce panneau, vérité terrain |
| Caméra | Bouton explicite navigateur, preview, snapshot dans Canvas, stop et révocation de toutes les pistes, coupure si page cachée | Stream permanent, reconnaissance sans approbation, webcam IP distante |
| Voix | SpeechRecognition du navigateur à la demande en français, transcription vers Chat SANS envoyer, TTS vocal par bouton | Localité garantie de STT/TTS, wake word, enregistrement micro, 100 % offline |
| 3D | Cube en véritables coordonnées 3D projetées avec Canvas2D et deux rotations sur CPU | Reconstruction 3D d'une photo, tracking, profondeur, WebGL/GPU |
| Code | Liste fermée de 5 fichiers texte du dépôt, lecture avec bornes et refus symlink/path traversal, copie vers presse-papier | Exécution de code, shell, édition, tests lancés, accès aux secrets |
| Appareils | Registre honnête caméra/micro/phone/drone/robot/domotique, simulation locale désarmée/armée avec arrêt d'urgence | **Aucune commande physique drone/robot/téléphone**, pas d'appairage ou SDK connecté |
| V40/V42/V43 | Aperçus existants, hash et compteurs, panneau vrai Harness, catalogue | Validation de qualité visuelle, World Model indépendant |

V4 n'installe aucun projet Jarvis tiers ni aucun nouveau paquet Python. Elle s'intègre au serveur loopback, au Brain adapter, au Harness et à la CanonicalSpine existants. Les cinq masques V40 et les treize événements locaux devraient rester visibles après restauration du frontend, sans lecture d'autres dossiers.

## Sûreté, données et appareils externes

- Backend bind exclusivement `127.0.0.1`, Host/Origin/CSP/nosniff/frame-deny inchangés. Modifie uniquement le Permissions-Policy de V3 pour permettre caméra/micro **avec consentement explicite du navigateur**, autrement V3 interdit les deux sans possibilité de fonctionnement. Aucun CORS et aucun endpoint physique activé.
- Les photos et captures caméra V4 restent **dans la mémoire du navigateur**, aucun upload HTTP vers HEX-CORTEX. L'export est un téléchargement choisi par l'utilisateur. Fermer la page stoppe les pistes caméra; mise en arrière-plan coupe aussi la caméra.
- Le STT `SpeechRecognition` Web Speech **peut utiliser les serveurs du fournisseur du navigateur**. Ne pas dicter de données sensibles. Pour un futur mode réellement offline, brancher faster-whisper ou Whisper CPU isolé et audité ; pas avant validation du matériel/latence.
- Le module 3D est mathématique sur Canvas2D (CPU) ; **pas de WebGL ou GPU** car l'AMD RX 6700 XT de l'opérateur reste instable. Les scènes 3D issues de vraies photos exigeraient de nouvelles données de profondeur/caméras et un modèle calibré.
- Le simulateur de robot/drone est **entièrement en Javascript et sans socket/HTTP**, donc il ne peut pas déplacer un objet physique. Pour passer au matériel : appairage, autorisation par action et catégorie, interverrouillage sécurité, arrêt d'urgence matériel, audit actions/replay, SDK signé, test en environnement isolé, protocole d'échec sûr. Les contrôles actifs de drone requièrent aussi les précautions réglementaires et aéronautiques appropriées ; aucune commande automatique ni mouvement non supervisé.

## Installation — PowerShell Windows, une commande par ligne

Depuis le dépôt HEX-CORTEX, fermer d'abord V3 (Ctrl+C dans le terminal qui sert le port 8777) puis lancer :

~~~powershell
git fetch origin
git switch -c feature/command-center-v4-multimodal-device-lab --track origin/feature/command-center-v4-multimodal-device-lab
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_command_center_v1.py tests/test_cortex_command_center_v2.py tests/test_cortex_command_center_v3.py tests/test_cortex_command_center_v4.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_command_center_v4 --project-root . --port 8777 --dry-run
& $VP -m hex_cortex.memory.cortex_command_center_v4 --project-root . --port 8777 --enable-cpu-chat
~~~

Naviguer vers **http://127.0.0.1:8777/**, recharger complètement avec Ctrl+F5 (un onglet serveur ancien ne met pas forcément automatiquement à jour son JS). Tu dois obtenir *V4* et les onglets distincts. Commencer par « Vue générale » : vérifier que **3 scènes, 5 masques et 13 événements** réapparaissent si les receipts V40 et le journal V42/V43 sont encore présents. Si tout reste vide, regarder la console F12 pour une erreur script et relever :

~~~powershell
Invoke-RestMethod http://127.0.0.1:8777/api/snapshot | ConvertTo-Json -Depth 6
~~~

Test fonctionnel recommandé : « Photo & caméra » → choisir une photo locale → tracer une boîte → exporter .bbox.json. « 3D CPU » → tourner le cube avec les sliders. « Code » → lire `cortex_local_harness_v2.py`. « Appareils » → lancer une **simulation** et utiliser arrêt d'urgence. Pour le micro, cliquer « Dictée ponctuelle » uniquement si tu acceptes la possibilité d'une transcription par fournisseur externe du navigateur. Ne jamais utiliser ce module pour piloter un drone physique.

## Suites de développement parallèles

**A : UX & performance** — streaming token par token, interruption effective de requête, benchmark FPS/latence, diagnostics HTTP JS, sessions gérées, adaptation tablette.

**B : Vision et physique** — sélectionner une zone → proposer explicitement une segmentation CPU MobileSAM → comparer vraie annotation humaine et erreur; séquences vidéo du même objet → tracking et World Model évalués sur baseline; 3D réel ultérieur après capteur de profondeur ou reconstructions validées.

**C : Audio CPU offline** — STT faster-whisper/Whisper tiny CPU isolé, TTS Piper/Kokoro avec voix françaises licenciées, permissions par mic, silence immédiat, aucune écoute permanente.

**D : Code et cognition** — lecture du projet et recherche BM25 sourcée dans le chat avec preuve de fichiers et changement explicite de compétences; exécution de tests et patch uniquement via gateway existant, pas par accès shell arbitraire.

**E : Hubs appareils** — API normalisée device_id/capability/safety_class/action_permissions, appairage, bridge de caméra téléphone opt-in, mock de robot, jamais de vrai contrôle tant que les SDK, rôles et validations matérielles ne sont pas connus.

Le travail peut se découper entre plusieurs développeurs, mais la livraison doit passer les tests transverses du Harness et de sécurité. Le nombre de boutons n'est pas une preuve de capacité autonome.
