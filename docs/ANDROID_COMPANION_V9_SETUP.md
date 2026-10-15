# HEX-CORTEX V9 — Compagnon mobile Android / Huawei P20

## Capacité réellement livrée

L'application est dans docs/companion/index.html. Elle permet sur smartphone de :
- déclencher la caméra arrière avec permission ou utiliser la capture Android de secours ;
- importer des photos JPEG/PNG/WebP (8 Mo, 12 mégapixels au maximum) ;
- tracer un rectangle autour d'un objet au doigt ;
- exporter une photo JPEG normalisée et un fichier JSON hex.mobile_manual_bbox.v9 contenant une bbox XYXY calculée dans la photo exportée, un identifiant, la provenance manuelle et un SHA256 lorsque disponible ;
- partager explicitement les deux fichiers avec l'interface Android.

Pas de téléchargement automatique d'une image vers un serveur. Le Service Worker ne conserve que les fichiers statiques de l'application, jamais les photos. Le partage Android peut transférer les fichiers vers un service tiers choisi par l'utilisateur : examiner la destination avant de partager. Aucune fonctionnalité IA embarquée ni contrôle matériel externe.

## Mise en ligne HTTPS via GitHub Pages

La caméra moderne exige HTTPS ou un contexte sécurisé. GitHub Pages peut héberger ces fichiers statiques gratuitement, sans code backend ni secret :

1. Dans GitHub, ouvrir 2spi93/HEX-CORTEX → Settings → Pages.
2. Source : Deploy from a branch.
3. Sélectionner la branche feature/v9-android-camera-companion-pwa et le dossier /docs, puis Save.
4. Attendre le déploiement. L'URL attendue est https://2spi93.github.io/HEX-CORTEX/companion/ ; utiliser l'URL exacte affichée par GitHub Pages.
5. Ouvrir sur le Huawei P20 avec Chrome et accorder la caméra volontairement. Installer sur l'écran d'accueil si le navigateur le propose.

Attention : le code statique est public sur GitHub Pages, pas tes photos qui restent dans le navigateur sauf partage explicite. Ne jamais incorporer une clé privée dans cette application.

## Transférer une image vers le vrai MobileSAM CPU HEX-CORTEX

1. Depuis le téléphone, exporter la photo JPG et le fichier .bbox.json.
2. Transférer le JPG vers le PC Windows par USB ou une application de partage explicitement choisie.
3. Dans le Command Center V8 local http://127.0.0.1:8777/, ouvrir Photo & caméra, charger le JPG, sélectionner à nouveau l'objet et cliquer Segmenter avec MobileSAM CPU. Le serveur doit être démarré avec --enable-cpu-vision.
4. Le JSON de la boîte est une preuve de sélection manuelle : **l'interface PC V8 ne l'importe pas encore automatiquement**. Cette fonction arrivera dans une étape séparée.

La loopback 127.0.0.1 de Windows est inaccessible depuis le Huawei P20. Ne jamais exposer directement le port 8777 en Internet ou LAN en remplaçant le bind par 0.0.0.0. Le pilotage distant exige HTTPS, appairage, authentification forte et permissions par action.

## Vérification

Les tests GitHub Ubuntu et Windows contrôlent le code du compagnon, sa politique de confidentialité, ses références HTML/JS et son fonctionnement PWA statique. Il faudra vérifier manuellement sur téléphone les permissions caméra, gestes tactiles, export et partage Android. Une CI réussie ne certifie pas la compatibilité caméra de ton modèle précis.

Étapes futures : import bbox JSON dans l'interface PC, appairage WebRTC chiffré pour flux vidéo sous opt-in, segmentation/annotation humaine, télémétrie seule des appareils externes avant action physique.
