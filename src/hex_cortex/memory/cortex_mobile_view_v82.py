"""Mobile operator view: standalone, responsive, no injected remote content."""
from __future__ import annotations

HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>HEX-CORTEX · Mobile</title>
<link rel="stylesheet" href="/assets/mobile.css">
<script src="/assets/mobile.js" defer></script>
</head><body>
<header><div class="eyebrow">HEX-CORTEX · CONSOLE PRIVÉE</div>
<h1>Mobile <small>V8.2 / CPU</small></h1>
<p>Supervision locale, caméra sur l'appareil, sans pilotage matériel.</p></header>
<main>
<section><h2>État des capacités</h2>
<p id="status" role="status" aria-live="polite">Lecture de l'état…</p>
<div class="grid">
<div><strong>HEX-CORTEX</strong><span>Console en lecture seule</span></div>
<div><strong>DeepSeek</strong><span id="dsh">Vérification…</span></div>
<div><strong>Drone</strong><span>Commandes de vol désactivées</span></div>
<div><strong>GPU</strong><span>Aucune sollicitation du GPU</span></div>
</div><button id="refresh" type="button">Actualiser le diagnostic</button>
</section>
<section><h2>Caméra Android / PC</h2>
<p>La caméra ne s'ouvre qu'après ton clic. Les images restent dans ce navigateur.
La capture peut être enregistrée sur l'appareil, sans transmission à HEX-CORTEX.</p>
<div class="camera">
<video id="preview" autoplay playsinline muted aria-label="Aperçu caméra"></video>
<canvas id="snapshot" width="640" height="480" hidden></canvas>
<img id="still" alt="Dernière capture locale" hidden>
</div>
<p id="camera-status" role="status" aria-live="polite">Caméra inactive.</p>
<div class="actions">
<button type="button" id="camera-on">Autoriser la caméra</button>
<button type="button" id="capture" disabled>Capturer sur l'appareil</button>
<button type="button" id="save" disabled>Enregistrer la photo</button>
<button type="button" id="camera-off" disabled>Arrêter la caméra</button>
</div></section>
<section><h2>Modules à raccorder</h2>
<p>La voix, les outils de développement, les compétences DeepSeek complètes,
les drones et les objets connectés exigent des connecteurs audités.
Aucune exécution automatique ou commande de drone n'est activée ici.</p>
</section></main>
<footer>Usage privé HTTPS via un réseau autorisé · Jamais de port ouvert publiquement.</footer>
</body></html>
"""

CSS = """
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#eff8fd;
 background:#091620;font-size:16px}
*{box-sizing:border-box}body{margin:0}
header,main,footer{max-width:760px;margin:auto;padding:18px}
header{padding-top:32px}h1{font-size:clamp(1.8rem,7vw,3rem);margin:.2em 0}
h1 small{font-size:.38em;color:#6edad1}p{color:#c2d2df;line-height:1.55}
.eyebrow{font-size:.73rem;letter-spacing:.15em;color:#79e0d5}
section{border:1px solid #294252;border-radius:16px;padding:18px;
background:#122632;margin:18px 0}
section h2{font-size:1.19rem;margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.grid div{border:1px solid #334955;border-radius:10px;padding:12px}
.grid strong{display:block;font-size:.88rem}.grid span{font-size:.79rem;color:#a9bccb}
button{min-height:44px;border:1px solid #61c8bd;border-radius:9px;background:#17616a;
color:#fff;padding:10px 13px;font:inherit;cursor:pointer;margin-top:7px}
button:disabled{opacity:.4;cursor:not-allowed}
.actions{display:flex;flex-wrap:wrap;gap:6px}
.camera{min-height:180px;border-radius:12px;overflow:hidden;background:#050c12}
.camera video,.camera img{width:100%;max-height:420px;object-fit:contain;display:block}
.camera video:not([src]){min-height:180px}
#status,#camera-status{min-height:1.6em;font-size:.88rem}
footer{font-size:.78rem;color:#93b2bd;padding-bottom:40px}
@media(max-width:430px){header,main,footer{padding:12px}.grid{grid-template-columns:1fr}
section{padding:14px}.actions button{flex:1 1 145px}}
"""

JS = r"""
'use strict';
(() => {
  const id = key => document.getElementById(key);
  const status = id('status'), dsh = id('dsh'), cameraStatus = id('camera-status');
  const video = id('preview'), image = id('still'), canvas = id('snapshot');
  const on = id('camera-on'), off = id('camera-off');
  const capture = id('capture'), save = id('save');
  let stream = null, photo = null, photoUrl = null;
  async function refresh() {
    status.textContent = 'Récupération du diagnostic…';
    try {
      const response = await fetch('/api/mobile/status', {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      if (data.schema !== 'hex.mobile_console.v82') throw new Error('Schéma inconnu');
      status.textContent = 'Console locale disponible · aucune action matériel autorisée';
      dsh.textContent = data.deepseek_agent_connected ?
        'Agent connecté' : 'Non connecté · reçu : ' + data.deepseek_sdk_pilot_receipt;
    } catch (_) {
      status.textContent = 'Diagnostic indisponible, aucune commande autorisée';
      dsh.textContent = 'Non vérifié';
    }
  }
  function stop() {
    if (stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
    video.srcObject = null;
    on.disabled = false; off.disabled = true; capture.disabled = true;
    cameraStatus.textContent = 'Caméra arrêtée · aucune vidéo envoyée au serveur.';
  }
  on.addEventListener('click', async () => {
    if (stream) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      cameraStatus.textContent = 'Caméra disponible uniquement via HTTPS privé ou localhost.';
      return;
    }
    on.disabled = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio:false, video:{facingMode:{ideal:'environment'},width:{ideal:640},
                            height:{ideal:480}}
      });
      video.srcObject = stream;
      await video.play();
      off.disabled = false; capture.disabled = false;
      cameraStatus.textContent = 'Aperçu local actif · aucun flux transmis.';
    } catch (_) {
      stop();
      cameraStatus.textContent = 'Autorisation refusée ou caméra indisponible.';
    }
  });
  capture.addEventListener('click', () => {
    if (!stream || !video.videoWidth || !video.videoHeight) return;
    canvas.width = Math.min(1280, video.videoWidth);
    canvas.height = Math.round(canvas.width * video.videoHeight / video.videoWidth);
    canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
    canvas.toBlob(blob => {
      if (!blob) { cameraStatus.textContent = 'Capture impossible.'; return; }
      if (photoUrl) URL.revokeObjectURL(photoUrl);
      photo = blob; photoUrl = URL.createObjectURL(blob);
      image.src = photoUrl; image.hidden = false; save.disabled = false;
      cameraStatus.textContent = 'Photo capturée localement · aucun transfert réseau.';
    }, 'image/jpeg', .85);
  });
  save.addEventListener('click', () => {
    if (!photo || !photoUrl) return;
    const link = document.createElement('a');
    link.href = photoUrl; link.download = 'hex-cortex-camera.jpg';
    document.body.appendChild(link); link.click(); link.remove();
  });
  off.addEventListener('click', stop);
  window.addEventListener('pagehide', () => {
    stop(); if (photoUrl) URL.revokeObjectURL(photoUrl);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
  });
  id('refresh').addEventListener('click', refresh);
  refresh();
})();
"""
