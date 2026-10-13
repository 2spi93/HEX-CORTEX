# HEX-CORTEX V6 — segmentation réelle MobileSAM depuis le Command Center

## Objectif

V4 affiche une caméra, un canvas et des boîtes de sélection, mais sans inférence. V6 permet de sélectionner une zone d'une photo puis, seulement après clic explicite, de l'envoyer au serveur local pour une réelle inférence MobileSAM sur CPU. Réutilise le predictor V36 existant, sans réimplémenter le modèle.

## Garanties et limites

- Nouveau lancement explicite --enable-cpu-vision; par défaut le modèle de vision n'est pas accessible par l'interface.
- Endpoint GET /api/vision/cpu/availability n'effectue ni accès aux poids, ni inférence, ni transfert d'image.
- Endpoint POST /api/vision/cpu/segment exige host et origine localhost autorisés, un header de consentement par appel, image JPEG/PNG/WebP en Base64 <=8 Mo, maximum 16 mégapixels, une boîte XYXY valide, un object_id borné.
- Avant toute inférence, le checkpoint fixe weights/mobile_sam.pt doit égaler le SHA256 6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f relevé par l'opérateur. Pas de téléversement de modèle ni téléchargement de poids.
- Appel exact à _mobile_sam_box_infer déjà écrit en V36, sur CPU; n'autorise ni CUDA, ni écriture disque, ni modification CanonicalSpine, ni action physique.
- Le même sémaphore CPU protège le modèle texte Ollama et le modèle MobileSAM contre une surcharge simultanée.
- Retourne un masque binaire PNG en mémoire + surcouche RGBA en mémoire, SHA256 des pixels, nombre de pixels, latence, absence de référence humaine. Le navigateur peut enregistrer le masque volontairement sur le disque local, mais le serveur ne le conserve jamais.
- Les deux étapes initiales de choix d'image et de dessin de boîte restent 100 % navigateur. Cliquer sur Segmenter transmet alors la photo au service strictement local 127.0.0.1; il ne faut donc plus dire qu'aucune image ne quitte jamais le navigateur. Aucun cloud n'est utilisé par ce module.
- Le MobileSAM infère un contour à partir de ta boîte. Il ne donne ni reconnaissance sémantique de catégorie fiable, ni segmentation de toutes les choses sans prompts, ni reconstruction 3D, ni vérité terrain indépendante. Il n'actualise pas automatiquement les 5 reçus V40 existants.

## PowerShell Windows — une commande par ligne

Stopper le serveur V5 par Ctrl+C, vérifier le poids MobileSAM déjà installé, puis :

    git fetch origin
    git switch -c feature/command-center-v6-real-photo-segmentation-cpu --track origin/feature/command-center-v6-real-photo-segmentation-cpu
    $VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
    $WeightSHA = (Get-FileHash .\weights\mobile_sam.pt -Algorithm SHA256).Hash.ToLowerInvariant()
    if($WeightSHA -ne "6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f"){throw "Checkpoint inattendu : arrêter"}
    & $VP -m pytest -q tests/test_cortex_cpu_segmentation_v36.py tests/test_cortex_command_center_v5.py tests/test_cortex_command_center_v6.py
    & $VP -m ruff check .
    & $VP -m hex_cortex.memory.cortex_command_center_v6 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision --dry-run
    & $VP -m hex_cortex.memory.cortex_command_center_v6 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision

Ouvrir http://127.0.0.1:8777/ puis Ctrl+F5. Choisir Photo & caméra, ouvrir une photo locale ou faire une capture, glisser pour tracer un rectangle sur un objet, cliquer Segmenter avec MobileSAM CPU. Le résultat doit surligner uniquement la silhouette prédite et activer Exporter le masque prédit. Si le modèle refuse, copier l'état segmentation affiché, sans désactiver la validation des poids.

## Conception après V6

Chantiers parallèles : reconnaissance indépendante des boîtes/noms d'objets (ex Florence-2 après audit), annotation humaine et IoU, overlay/provenance au sein du CanonicalSpine avec approbation de persistance, suivi temporel même objet sur vidéo, World Model comparé à une baseline, STT/TTS offline garanti, surveillance des performances CPU, adaptateurs MCP/robot/drone sous gateway stricte.

Inspiré de l'architecture de séparation des skills et outils de https://github.com/open-jarvis/OpenJarvis mais aucun code externe Jarvis n'est installé ou fusionné.
