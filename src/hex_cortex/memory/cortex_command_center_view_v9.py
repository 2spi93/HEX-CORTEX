"""HEX-CORTEX V9 — import verified Android bbox into existing V6 CPU vision.

All code remains in the existing V6 browser photo-selection closure.
No file is uploaded by importing a JSON. MobileSAM continues to require its
separate explicit segmentation click and the V6 approved localhost endpoint.
"""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v8 import (
    CSS as BASE_CSS, HTML as BASE_HTML, JS as BASE_JS,
)
from hex_cortex.memory.cortex_command_center_view_v6 import MEDIA_V6


_IMPORT_PANEL = """
<div class="chat-controls">
  <label for="phone-bbox-import">Boîte du téléphone (.bbox.json)</label>
  <input id="phone-bbox-import" type="file" accept=".json,application/json">
  <a href="https://2spi93.github.io/HEX-CORTEX/companion/"
     target="_blank" rel="noopener noreferrer">
    Compagnon mobile (après activation GitHub Pages)</a>
</div>
<pre id="phone-bbox-state" role="status">Choisis d'abord le JPEG exporté
  du téléphone puis son fichier bbox JSON. Vérification SHA-256 obligatoire.</pre>
"""

HTML = (
    BASE_HTML
    .replace("Command Center <em>HEX-CORTEX V8</em>",
             "Command Center <em>HEX-CORTEX V9</em>")
    .replace(
        '<pre id="segmentation-status" aria-live="polite">',
        _IMPORT_PANEL + '<pre id="segmentation-status" aria-live="polite">',
    )
)

CSS = BASE_CSS + r"""
#phone-bbox-state{max-height:125px;overflow-wrap:anywhere}
#phone-bbox-import{font:inherit;color:#e2f7fa;max-width:100%}
"""

_IMPORT_JS = r"""
  // This handler runs in the existing browser-only image selection closure.
  // Importing JSON is NEVER equivalent to authorizing model inference.
  $('phone-bbox-import').addEventListener('change', async event => {
    const file = event.target.files?.[0];
    const jpeg = $('photo-file').files?.[0];
    const statusId = 'phone-bbox-state';
    if (!file || !original || !jpeg) {
      message(statusId, 'Charger d’abord le JPEG exporté du téléphone.');
      return;
    }
    if (file.size > 16_384 || file.size < 2 || jpeg.size > 8_000_000) {
      message(statusId, 'Fichier JSON ou JPEG hors limites.');
      return;
    }
    const expected = original;
    try {
      const descriptor = JSON.parse(await file.text());
      const bounds = descriptor?.bbox_xyxy;
      const dimension = descriptor?.dimensions;
      const name = descriptor?.object_id;
      const sha = descriptor?.image_sha256;
      if (descriptor?.schema !== 'hex.mobile_manual_bbox.v9' ||
          descriptor.segmentation_performed !== false ||
          descriptor.label_source !== 'operator_selected_not_model_recognition' ||
          !Array.isArray(bounds) || bounds.length !== 4 ||
          !bounds.every(x => Number.isSafeInteger(x)) ||
          !Array.isArray(dimension) || dimension.length !== 2 ||
          dimension[0] !== original.width || dimension[1] !== original.height ||
          !/^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(name) ||
          typeof sha !== 'string' || !/^[a-f0-9]{64}$/.test(sha) ||
          !(0 <= bounds[0] && bounds[0] < bounds[2] &&
            bounds[2] <= original.width &&
            0 <= bounds[1] && bounds[1] < bounds[3] &&
            bounds[3] <= original.height)) {
        throw Error('JSON non conforme ou dimensions/boîte invalides');
      }
      if (!crypto?.subtle) throw Error('SHA256 indisponible dans le navigateur');
      const digest = await crypto.subtle.digest('SHA-256', await jpeg.arrayBuffer());
      const computed = Array.from(new Uint8Array(digest))
        .map(b => b.toString(16).padStart(2, '0')).join('');
      if (computed !== sha || original !== expected) {
        throw Error('Photo différente du JPEG enregistré dans le JSON');
      }
      clearPredictedMask();
      $('object-label').value = name;
      dragStart = {
        x: bounds[0] * canvas.width / original.width,
        y: bounds[1] * canvas.height / original.height
      };
      dragEnd = {
        x: bounds[2] * canvas.width / original.width,
        y: bounds[3] * canvas.height / original.height
      };
      draw();
      message(statusId,
        'Photo SHA256 et dimensions vérifiées · boîte importée : ' +
        bounds.join(', ') + '. Aucun appel MobileSAM lancé automatiquement.');
    } catch (error) {
      message(statusId, 'Import refusé : ' + error.message);
    }
  });

"""

if MEDIA_V6.count("  const video=$('camera-stream');") != 1:
    raise RuntimeError("V6 browser scene selection anchor changed")
MODIFIED_MEDIA = MEDIA_V6.replace(
    "  const video=$('camera-stream');",
    _IMPORT_JS + "  const video=$('camera-stream');",
)
if BASE_JS.count(MEDIA_V6) != 1:
    raise RuntimeError("V8 composed script no longer contains existing V6 media module")
JS = BASE_JS.replace(MEDIA_V6, MODIFIED_MEDIA)
