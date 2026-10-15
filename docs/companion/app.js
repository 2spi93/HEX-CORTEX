'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const canvas = $('photo'), ctx = canvas.getContext('2d');
  const video = $('camera-feed');
  const MAX_BYTES = 8_000_000, MAX_PIXELS = 12_000_000;
  let image = null, stream = null, beginning = null, ending = null;
  let dragging = false, busy = false, generation = 0;
  let cachedExport = null;
  const status = (id, text) => { $(id).textContent = String(text); };

  function setActions() {
    const selected = Boolean(validBox());
    $('selection-clear').disabled = !selected;
    $('export-photo').disabled = !image || busy;
    $('export-box').disabled = !selected || busy;
    $('share').disabled = !selected || busy;
  }

  function validBox() {
    if (!image || !beginning || !ending) return null;
    const left = Math.min(beginning.x, ending.x);
    const right = Math.max(beginning.x, ending.x);
    const top = Math.min(beginning.y, ending.y);
    const bottom = Math.max(beginning.y, ending.y);
    if (right - left < 6 || bottom - top < 6) return null;
    return [
      Math.floor(left * image.width / canvas.width),
      Math.floor(top * image.height / canvas.height),
      Math.min(image.width, Math.ceil(right * image.width / canvas.width)),
      Math.min(image.height, Math.ceil(bottom * image.height / canvas.height))
    ];
  }

  function coordinates(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(canvas.width,
        (event.clientX - rect.left) * canvas.width / rect.width)),
      y: Math.max(0, Math.min(canvas.height,
        (event.clientY - rect.top) * canvas.height / rect.height))
    };
  }

  function repaint() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!image) {
      ctx.fillStyle = '#0b2230'; ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#bdd8e4'; ctx.font = '17px sans-serif';
      ctx.fillText('Photo non chargée', 28, 48);
    } else {
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      const bbox = validBox();
      if (bbox) {
        const [a, b, c, d] = bbox;
        const x = a * canvas.width / image.width;
        const y = b * canvas.height / image.height;
        const w = (c - a) * canvas.width / image.width;
        const h = (d - b) * canvas.height / image.height;
        ctx.fillStyle = 'rgba(19,235,200,.13)';
        ctx.fillRect(x, y, w, h);
        ctx.strokeStyle = '#55ffe5'; ctx.lineWidth = 3;
        ctx.strokeRect(x, y, w, h);
        status('selection-state',
          'Boîte XYXY : [' + bbox.join(', ') + '] · photo ' +
          image.width + ' × ' + image.height + ' px · sélection manuelle');
      } else {
        status('selection-state', 'Photo ' + image.width + ' × ' +
          image.height + ' px · trace une boîte au doigt');
      }
    }
    setActions();
  }

  function stopCamera() {
    if (stream) for (const track of stream.getTracks()) track.stop();
    stream = null;
    video.pause(); video.srcObject = null; video.hidden = true;
    $('camera-start').disabled = false;
    $('camera-snap').disabled = true;
    $('camera-stop').disabled = true;
  }

  async function acceptBitmap(bitmap, origin, expectedGeneration) {
    if (expectedGeneration !== generation) {
      bitmap.close?.(); return;
    }
    if (!bitmap.width || !bitmap.height ||
        bitmap.width * bitmap.height > MAX_PIXELS) {
      bitmap.close?.();
      throw new Error('Image trop grande (limite : 12 millions de pixels)');
    }
    image?.close?.();
    image = bitmap; beginning = null; ending = null; cachedExport = null;
    canvas.width = Math.min(bitmap.width, 720);
    canvas.height = Math.max(1, Math.round(
      bitmap.height * canvas.width / bitmap.width));
    repaint();
    status('camera-state', origin + ' · prête pour la sélection');
    status('export-state', 'Image uniquement en mémoire ; aucun envoi automatique.');
  }

  async function loadPhoto(file, label) {
    if (!file) return;
    const requested = ++generation;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
        || file.size < 1 || file.size > MAX_BYTES) {
      status('camera-state', 'Photo refusée : JPEG, PNG ou WebP de moins de 8 Mo.');
      return;
    }
    try {
      stopCamera();
      const bitmap = await createImageBitmap(file);
      await acceptBitmap(bitmap, label, requested);
    } catch (err) {
      status('camera-state', 'Impossible de charger la photo : ' + err.message);
    }
  }
  $('photo-choose').addEventListener('change', ev =>
    loadPhoto(ev.target.files?.[0], 'Photo sélectionnée'));
  $('camera-fallback').addEventListener('change', ev =>
    loadPhoto(ev.target.files?.[0], 'Capture Android'));

  $('camera-start').addEventListener('click', async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      status('camera-state',
        'Aperçu vidéo indisponible. Utilise « Prendre une photo (secours) ».');
      return;
    }
    $('camera-start').disabled = true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' },
                 width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      $('camera-snap').disabled = false;
      $('camera-stop').disabled = false;
      status('camera-state', 'Caméra active sur autorisation · aucune transmission.');
    } catch (err) {
      stopCamera();
      status('camera-state', 'Accès caméra refusé/indisponible : ' +
        (err.name || 'erreur') + '. Essaie la capture de secours.');
    }
  });

  $('camera-snap').addEventListener('click', async () => {
    if (!stream || !video.videoWidth || busy) return;
    busy = true; setActions();
    const requested = ++generation;
    try {
      const offscreen = document.createElement('canvas');
      offscreen.width = video.videoWidth;
      offscreen.height = video.videoHeight;
      offscreen.getContext('2d').drawImage(video, 0, 0);
      const bitmap = await createImageBitmap(offscreen);
      stopCamera();
      await acceptBitmap(bitmap, 'Capture caméra', requested);
    } catch (err) {
      status('camera-state', 'Capture échouée : ' + err.message);
    } finally { busy = false; setActions(); }
  });
  $('camera-stop').addEventListener('click', () => {
    stopCamera(); status('camera-state', 'Caméra arrêtée, pistes libérées.');
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && stream) stopCamera();
  });
  window.addEventListener('pagehide', stopCamera);

  canvas.addEventListener('pointerdown', ev => {
    if (!image) return;
    beginning = coordinates(ev); ending = beginning;
    dragging = true; cachedExport = null;
    canvas.setPointerCapture(ev.pointerId);
    repaint();
  });
  canvas.addEventListener('pointermove', ev => {
    if (!dragging) return;
    ending = coordinates(ev); repaint();
  });
  canvas.addEventListener('pointerup', ev => {
    if (!dragging) return;
    ending = coordinates(ev); dragging = false;
    canvas.releasePointerCapture(ev.pointerId); repaint();
  });
  canvas.addEventListener('pointercancel', () => { dragging = false; repaint(); });
  $('selection-clear').addEventListener('click', () => {
    beginning = null; ending = null; cachedExport = null; repaint();
  });
  $('object-name').addEventListener('input', () => { cachedExport = null; });

  function safeName() {
    const name = $('object-name').value.trim();
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(name)) throw Error(
      'Nom invalide : lettre, chiffres, tiret ou underscore (48 caractères max)');
    return name;
  }
  function toBlob(offscreen, type, quality) {
    return new Promise((resolve, reject) =>
      offscreen.toBlob(value => value ? resolve(value) :
        reject(Error('Encodage local indisponible')), type, quality));
  }
  function download(file) {
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url; link.download = file.name;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  async function prepareExport() {
    const bbox = validBox(), name = safeName();
    if (!image || !bbox) throw Error('Charge une photo et trace un rectangle');
    if (cachedExport?.bbox.join(',') === bbox.join(',') &&
        cachedExport.name === name && cachedExport.gen === generation)
      return cachedExport;
    // Normalized export: the JSON coordinates refer exactly to THIS JPEG's
    // decoded dimensions, including orientation corrected by the browser.
    const offscreen = document.createElement('canvas');
    offscreen.width = image.width; offscreen.height = image.height;
    const g = offscreen.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, image.width, image.height);
    g.drawImage(image, 0, 0);
    const picture = await toBlob(offscreen, 'image/jpeg', .87);
    if (picture.size > MAX_BYTES) throw Error('JPEG exporté >8 Mo');
    const photoFile = new File([picture], name + '-photo.jpg', {type: 'image/jpeg'});
    let sha = null;
    if (window.crypto?.subtle) {
      const digest = await crypto.subtle.digest('SHA-256', await picture.arrayBuffer());
      sha = Array.from(new Uint8Array(digest))
        .map(b => b.toString(16).padStart(2, '0')).join('');
    }
    const receipt = {
      schema: 'hex.mobile_manual_bbox.v9',
      image_filename: photoFile.name,
      image_sha256: sha,
      dimensions: [image.width, image.height],
      object_id: name,
      bbox_xyxy: bbox,
      label_source: 'operator_selected_not_model_recognition',
      mask_exists: false,
      segmentation_performed: false,
      remote_device_control_performed: false,
      explicit_manual_export: true
    };
    const bboxFile = new File([JSON.stringify(receipt, null, 2)],
      name + '.bbox.json', {type: 'application/json'});
    cachedExport = {gen: generation, bbox, name, photoFile, bboxFile};
    return cachedExport;
  }
  async function exportSelected(kind) {
    if (busy) return;
    busy = true; setActions();
    try {
      const files = await prepareExport();
      download(kind === 'box' ? files.bboxFile : files.photoFile);
      status('export-state', 'Fichier créé localement ; aucun transfert réseau par HEX-CORTEX.');
    } catch (err) { status('export-state', 'Export bloqué : ' + err.message); }
    finally { busy = false; setActions(); }
  }
  $('export-box').addEventListener('click', () => exportSelected('box'));
  $('export-photo').addEventListener('click', () => exportSelected('photo'));
  $('share').addEventListener('click', async () => {
    if (busy) return;
    busy = true; setActions();
    try {
      const exported = await prepareExport();
      const files = [exported.photoFile, exported.bboxFile];
      if (!navigator.canShare || !navigator.canShare({files})) {
        throw Error('Partage de fichiers indisponible. Télécharge photo et JSON.');
      }
      await navigator.share({files, title: 'HEX-CORTEX • capture manuelle'});
      status('export-state',
        'Partage demandé à Android. La destination choisie peut transmettre les fichiers.');
    } catch (err) {
      status('export-state', err.name === 'AbortError' ?
        'Partage annulé.' : 'Partage indisponible : ' + err.message);
    } finally { busy = false; setActions(); }
  });

  status('connection', navigator.onLine ? 'Mode privé · prêt' : 'Hors ligne');
  window.addEventListener('online', () => status('connection', 'Mode privé · prêt'));
  window.addEventListener('offline', () => status('connection', 'Hors ligne'));
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('./sw.js').catch(() => {
      // Offline caching is optional, not required for camera capture.
    });
  }
  repaint();
})();
