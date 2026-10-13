"""Local Command Center JavaScript, no dynamic HTML injection or remote code."""

JS = r"""
'use strict';
const el = (id) => document.getElementById(id);
const label = (id, text) => { el(id).textContent = String(text); };
function tag(text) {
  const node = document.createElement('span');
  node.className = 'event-tag';
  node.textContent = text;
  return node;
}
function showVision(data) {
  const area = el('vision-list');
  area.replaceChildren();
  if (!data || data.status !== 'operator_receipt_loaded') {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = 'Aucune inspection V40 exploitable. Lance V40 sur ton PC avant de voir les masques.';
    area.append(p); return;
  }
  for (const scene of data.scenes) {
    for (const obj of scene.objects) {
      const card = document.createElement('article');
      card.className = 'vision-card';
      if (obj.preview_url) {
        const image = document.createElement('img');
        image.loading = 'lazy';
        image.src = obj.preview_url;
        image.alt = 'Aperçu de masque prédit : ' + scene.scene_id + ' / ' + obj.object_id;
        card.append(image);
      }
      const heading = document.createElement('strong');
      heading.textContent = obj.object_id;
      card.append(heading);
      const sub = document.createElement('small');
      sub.textContent = scene.scene_id + ' · non annoté';
      card.append(sub);
      area.append(card);
    }
  }
}
async function refresh() {
  el('refresh').disabled = true;
  try {
    const response = await fetch('/api/snapshot', {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    label('mode', 'CPU SAFE');
    label('scenes', data.vision.scenes ? data.vision.scenes.length : '—');
    label('masks', data.vision.mask_count ?? '—');
    label('events', data.spine.events ?? '—');
    label('spine-status', data.spine.integrity === true ? 'Chaîne vérifiée' : data.spine.status);
    label('spine-visual', data.spine.visual_predictions ?? '—');
    label('cockpit-status', data.cockpit.latest_status ?? data.cockpit.status);
    const types = el('event-types');
    types.replaceChildren();
    for (const row of (data.spine.types || [])) {
      types.append(tag(row.type + ' · ' + row.count));
    }
    showVision(data.vision);
    const errors = ['vision', 'spine', 'cockpit'].filter(k => data[k].status === 'error');
    el('banner').classList.toggle('error', errors.length > 0);
    label('banner', errors.length ? 'Lecture locale partielle : ' + errors.join(', ') :
      'Lecture seule · Aucun modèle exécuté · Aucun événement ou fichier créé par le tableau de bord');
  } catch (e) {
    el('banner').classList.add('error');
    label('banner', 'Command Center indisponible : ' + e.message);
  } finally {
    el('refresh').disabled = false;
  }
}
async function probe() {
  const button = el('probe');
  button.disabled = true;
  label('probe-result', 'Vérification du dépôt via le Harness existant…');
  try {
    const response = await fetch('/api/harness/probe', {
      method: 'POST', headers: {'X-HEX-Read-Probe': 'explicit'}, body: ''
    });
    const result = await response.json();
    label('probe-result', JSON.stringify(result, null, 2));
  } catch (e) {
    label('probe-result', 'Probe échoué : ' + e.message);
  } finally {
    button.disabled = false;
  }
}
el('refresh').addEventListener('click', refresh);
el('probe').addEventListener('click', probe);
refresh();
"""
