"""V4 browser UI: real photos/camera/voice, CPU wireframe, code and device safety.

Keep V3 HTML/CSS; completely replace the inherited multi-version JS
concatenation with two fresh modules to avoid silent bootstrap failures.
"""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v3 import (
    CSS as BASE_CSS,
    HTML as BASE_HTML,
)
from hex_cortex.memory.cortex_command_center_runtime_v4 import JS as RUNTIME
from hex_cortex.memory.cortex_command_center_media_v4 import JS as MEDIA

MEDIA_PANEL = """
<section id="media" aria-label="Photo et caméra">
  <div class="section-title"><h2>Vision interactive · photos et caméra</h2>
  <span>Traitement dans le navigateur · aucune image envoyée au serveur</span></div>
  <div class="panel">
    <p class="disclaimer">Charge une photo ou autorise volontairement une caméra locale.
       Dessine une boîte en glissant sur l'image. Ce rectangle n'est PAS un masque MobileSAM ;
       aucun objet n'est reconnu automatiquement. Les images restent dans ton navigateur.</p>
    <div class="chat-controls">
      <label for="photo-file">Photo locale</label>
      <input type="file" id="photo-file" accept="image/png,image/jpeg,image/webp">
      <button type="button" id="camera-start">Activer la caméra</button>
      <button type="button" id="camera-snap" disabled>Capturer</button>
      <button type="button" id="camera-stop" disabled>Couper la caméra</button>
    </div>
    <video id="camera-stream" autoplay playsinline muted hidden></video>
    <canvas id="photo-canvas" width="640" height="400"
      aria-label="Photo et sélection rectangulaire au pointeur"></canvas>
    <div class="chat-controls">
      <label for="object-label">Objet sélectionné</label>
      <input type="text" id="object-label" maxlength="64" value="object1"
        placeholder="Nom de l'objet">
      <button id="bbox-export" type="button" disabled>Exporter boîte JSON</button>
      <button id="crop-export" type="button" disabled>Exporter le recadrage</button>
      <button id="photo-export" type="button" disabled>Exporter la photo PNG</button>
    </div>
    <pre id="photo-status" aria-live="polite">Aucune image locale ouverte.</pre>
  </div>
</section>
"""

VOICE_PANEL = """
<section id="voice" aria-label="Voix française">
  <div class="section-title"><h2>Voix et dictée française</h2>
    <span>À la demande · aucun wake word permanent</span></div>
  <div class="panel">
    <p class="disclaimer">Reconnaissance vocale Web Speech : selon le navigateur, la transcription
       peut utiliser un service distant. Ce mode n'est donc PAS garanti hors ligne.
       Utilise uniquement des informations non sensibles.
       Le texte est placé dans le champ Chat, jamais envoyé au modèle sans ton clic.</p>
    <div class="chat-controls">
      <button id="voice-start" type="button">Dictée ponctuelle (micro)</button>
      <button id="voice-stop" type="button" disabled>Arrêter la dictée</button>
      <button id="voice-speak" type="button">Lire une phrase (TTS)</button>
      <button id="voice-silence" type="button">Stopper la lecture</button>
    </div>
    <label for="voice-text">Texte dicté ou à prononcer</label>
    <textarea id="voice-text" rows="4" maxlength="1600"
      placeholder="Aucun micro ouvert. La dictée et la synthèse sont facultatives."></textarea>
    <div class="chat-controls">
      <button id="voice-to-chat" type="button">Copier vers Chat CPU sans envoyer</button>
    </div>
    <pre id="voice-status" aria-live="polite">Micro désactivé.</pre>
  </div>
</section>
"""

SCENE_PANEL = """
<section id="scene3d" aria-label="Géométrie 3D et simulation">
  <div class="section-title"><h2>Scène 3D · laboratoire géométrique CPU</h2>
    <span>Projection d'un cube de référence · pas de reconstruction 3D de photo</span></div>
  <div class="panel">
    <p class="disclaimer">Visualise une géométrie 3D filaire par projection mathématique
       dans Canvas 2D, pour éviter WebGL/GPU sur la RX 6700 XT instable.
       Il ne s'agit ni d'un modèle génératif ni d'une reconstruction de tes photos.</p>
    <canvas id="scene-canvas" width="640" height="390"
      aria-label="Projection 3D filaire calculée sur CPU"></canvas>
    <div class="chat-controls">
      <label for="angle-x">Rotation X</label>
      <input type="range" id="angle-x" min="-180" max="180" value="-20">
      <label for="angle-y">Rotation Y</label>
      <input type="range" id="angle-y" min="-180" max="180" value="28">
      <button type="button" id="scene-reset">Réinitialiser la scène</button>
    </div>
    <pre id="scene-status">Géométrie synthétique, repère local. Sans inférence 3D.</pre>
  </div>
</section>
"""

CODE_PANEL = """
<section id="code" aria-label="Code HEX-CORTEX en lecture seule">
  <div class="section-title"><h2>Atelier de code</h2><span>Sources allowlistées · aucune exécution</span></div>
  <div class="panel">
    <div class="chat-controls"><label for="code-files">Source autorisée</label>
      <select id="code-files"><option value="">Sélectionner un fichier</option></select>
      <button id="code-open" type="button">Lire le code</button>
      <button id="code-copy" type="button" disabled>Copier le code</button>
    </div>
    <pre id="code-source" class="code-source" aria-label="Code source">Aucun fichier chargé.</pre>
    <p class="disclaimer">Aucune sauvegarde, modification, commande shell, compilation,
       test ou commit n'est lancé depuis ce panneau.</p>
  </div>
</section>
"""

DEVICE_PANEL = """
<section id="devices" aria-label="Interfaces de périphériques externes">
  <div class="section-title"><h2>Appareils et robotique</h2>
    <span>Registre réel des capacités · commandes physiques désactivées</span></div>
  <div class="panel">
    <div id="device-list" class="catalog-grid">Chargement du registre local…</div>
    <p class="disclaimer">Une caméra USB ou intégrée est accessible uniquement via consentement du
       navigateur. Les téléphones distants, drones et robots n'ont pas d'adaptateur
       matériel autorisé : impossible de les commander depuis cette version.</p>
    <div class="chat-controls">
      <label for="sim-target">Simulation hors matériel</label>
      <select id="sim-target"><option value="robot">Robot fictif</option>
        <option value="drone">Drone fictif</option></select>
      <button type="button" id="sim-arm">Armer simulation</button>
      <button type="button" id="sim-left">◀ Gauche</button>
      <button type="button" id="sim-forward">▲ Avancer</button>
      <button type="button" id="sim-right">Droite ▶</button>
      <button type="button" id="sim-stop">ARRÊT D'URGENCE</button>
    </div>
    <pre id="sim-status" aria-live="polite">Simulation désarmée. Aucun périphérique physique ne peut recevoir ces événements.</pre>
  </div>
</section>
"""

HTML = BASE_HTML.replace(
    '<a href="#roadmap">',
    '<a href="#media">▣ Photo & caméra</a>'
    '<a href="#voice">◉ Voix</a>'
    '<a href="#scene3d">⬡ 3D CPU</a>'
    '<a href="#code">⌘ Code</a>'
    '<a href="#devices">⌁ Appareils</a>'
    '<a href="#roadmap">',
).replace(
    '<section id="roadmap">',
    MEDIA_PANEL + VOICE_PANEL + SCENE_PANEL + CODE_PANEL + DEVICE_PANEL
    + '<section id="roadmap">',
).replace(
    'Command Center <em>HEX-CORTEX V3</em>',
    'Command Center <em>HEX-CORTEX V4</em>',
).replace(
    'CONSOLE OPÉRATEUR · PHASE 1',
    'CONSOLE OPÉRATEUR · MULTIMODAL LAB',
)

CSS = BASE_CSS + r"""
#photo-canvas,#scene-canvas{display:block;max-width:100%;height:auto;
  background:#071320;border:1px solid #345468;border-radius:11px;touch-action:none;margin:18px 0}
#camera-stream{max-width:100%;max-height:260px;border-radius:10px;margin:10px 0}
#photo-canvas{cursor:crosshair}
input[type=file],input[type=text]{font:inherit;color:#e4f6ff;background:#0b1c2b;
  padding:9px;border:1px solid #3d5870;border-radius:8px;max-width:100%}
.code-source{max-height:580px;overflow:auto;tab-size:4;white-space:pre;
  font:12px/1.6 Consolas,'Courier New',monospace}
#sim-stop{background:#853d46;border-color:#b65f67}
#sim-status,#voice-status,#photo-status{max-height:150px}
.sidebar{overflow-y:auto}
.main section[hidden]{display:none!important}
"""

JS = RUNTIME + "\n" + MEDIA
