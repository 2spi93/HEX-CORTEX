"""V5 knowledge/credibility cockpit UI; reuses V4's tested standalone runtime."""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v4 import (
    CSS as BASE_CSS, HTML as BASE_HTML,
)
from hex_cortex.memory.cortex_command_center_media_v4 import JS as MEDIA
from hex_cortex.memory.cortex_command_center_runtime_v4 import JS as RUNTIME


KNOWLEDGE = """
<section id="knowledge" aria-label="Preuves et connaissances locales de HEX-CORTEX">
  <div class="section-title"><h2>Connaissance vérifiée du projet</h2>
    <span>État calculé en direct depuis les registres, non halluciné par le modèle</span></div>
  <div class="panel">
    <p class="disclaimer">Ce dossier factuel est donné au Brain avant chaque réponse Ollama.
      Il distingue les fonctions réellement connectées, les simulations et les fonctions absentes.
      Une chaîne intègre n'est pas une validation scientifique de la perception.</p>
    <div class="chat-controls">
      <button id="knowledge-refresh" type="button">Actualiser les preuves</button>
      <button id="knowledge-copy" type="button" disabled>Copier le dossier JSON</button>
      <span id="knowledge-state" role="status">Données non chargées</span>
    </div>
    <div id="knowledge-grid" class="catalog-grid">
      <p class="muted">Chargement des faits vérifiés…</p>
    </div>
    <div class="section-title"><h3>Provenance et limites</h3></div>
    <pre id="knowledge-sources" class="code-source">En attente du registre local.</pre>
    <p class="disclaimer">Le dossier couvre le Command Center et ses preuves locales.
      Il ne remplace pas l'indexation documentaire, la validation d'outils MCP,
      les annotations humaines ni les tests de modèles sur données indépendantes.</p>
  </div>
</section>
"""

HTML = (
    BASE_HTML
    .replace("Command Center <em>HEX-CORTEX V4</em>",
             "Command Center <em>HEX-CORTEX V5</em>")
    .replace(
        '<a href="#catalog">',
        '<a href="#knowledge">◇ Connaissance & preuves</a><a href="#catalog">',
    )
    .replace(
        '<section id="catalog">',
        KNOWLEDGE + '<section id="catalog">',
    )
    .replace(
        "Non connectée — micro, STT et TTS isolés.",
        "Dictée Web Speech sur demande (cloud possible) ; TTS navigateur. "
        "STT local hors ligne à intégrer.",
    )
    .replace(
        "Inspection V40 en lecture — nouvelles images sur approbation.",
        "V40 inspectable ; nouvelles photos et boîtes manuelles depuis le panneau Photo.",
    )
)

CSS = BASE_CSS + r"""
#knowledge-sources{min-height:100px;max-height:220px}
#knowledge-state{font-size:12px;color:#a9c4d0}
#knowledge-grid .catalog-card{min-height:100px}
"""

# This is intentionally a small, tested change to V4's *working* JS, not
# another concatenation of V1/V2/V3 runtimes.
RUNTIME_V5 = RUNTIME.replace(
    """  window.addEventListener('unhandledrejection', e => report(
    'Erreur asynchrone interface : '+String(e.reason).slice(0,180), true
  ));""",
    """  window.addEventListener('unhandledrejection', e => {
    const reason=String(e.reason||'');
    if(reason.includes('sseError not found')){
      show('voice-status',
        'Service de dictée du navigateur indisponible. '
        +'La reconnaissance Web Speech peut dépendre du réseau ; '
        +'utiliser le clavier ou attendre le futur moteur STT local.');
      report('Voix navigateur indisponible ; autres modules opérationnels.');
      e.preventDefault();return;
    }
    report('Erreur asynchrone interface : '+reason.slice(0,180), true);
  });""",
).replace(
    """      show('chat-state',
        'Réponse CPU · '+Math.round(performance.now()-started)+
        ' ms aller-retour · '+(data.history_items_used/2)+' échange(s) réutilisé(s)');""",
    """      show('chat-state',
        'Réponse CPU · '+Math.round(performance.now()-started)+
        ' ms aller-retour · '+(data.history_items_used/2)+' échange(s) réutilisé(s)'+
        (data.server_capability_facts_used?
          ' · contexte HEX-CORTEX vérifié [snapshot, capabilities, devices]':''));
    """,
)

JS_KNOWLEDGE = r"""
'use strict';
(() => {
  const $=id=>document.getElementById(id);
  let current=null;
  async function load(){
    const button=$('knowledge-refresh');
    button.disabled=true;
    $('knowledge-state').textContent='Vérification en cours…';
    try{
      const r=await fetch('/api/project/brief',{cache:'no-store'});
      const data=await r.json();
      if(!r.ok)throw Error(data.reason||'HTTP '+r.status);
      current=data;
      const area=$('knowledge-grid');area.replaceChildren();
      const facts=[
        ['Modèle / Brain',
         data.chat.enabled_by_operator?'Ollama CPU autorisé':'Désactivé au lancement'],
        ['Harness',data.installed_integrations.harness],
        ['Scènes / masques V40',
         (data.evidence.photographic_scenes_with_receipts??'Non vérifié')+' / '+
         (data.evidence.operator_predicted_masks??'Non vérifié')],
        ['CanonicalSpine',
         data.evidence.dedicated_spine_integrity_verified
          ?data.evidence.dedicated_spine_event_count+' événements · chaîne intègre'
          :'Non vérifiée'],
        ['Vision',data.installed_integrations.vision],
        ['Voix',data.installed_integrations.voice],
        ['Code',data.installed_integrations.code],
        ['Périphériques',data.installed_integrations.devices],
      ];
      for(const [key,value] of facts){
        const card=document.createElement('article');card.className='catalog-card';
        const title=document.createElement('strong');title.textContent=key;
        const desc=document.createElement('p');desc.textContent=value;
        card.append(title,desc);area.append(card);
      }
      const sources=[
        'Empreinte du dossier : '+data.facts_sha256,
        'Sources contrôlées :',
        ...data.sources.map(s=>'- ['+s.id+'] '+s.path+' : '+s.description),
        '',
        'Fonctions non connectées :',
        ...data.unavailable.map(x=>'- '+x),
        '',
        'Limite : '+data.provenance_note
      ].join('\n');
      $('knowledge-sources').textContent=sources;
      $('knowledge-state').textContent='Dossier local vérifié · mise à jour à la demande';
      $('knowledge-copy').disabled=false;
    }catch(e){
      current=null;
      $('knowledge-state').textContent='Impossible de lire les preuves : '+e.message;
      $('knowledge-copy').disabled=true;
    }finally{button.disabled=false;}
  }
  $('knowledge-refresh').addEventListener('click',load);
  $('knowledge-copy').addEventListener('click',async()=>{
    if(!current)return;
    try{
      await navigator.clipboard.writeText(JSON.stringify(current,null,2));
      $('knowledge-state').textContent='Dossier JSON copié dans le presse-papier';
    }catch(e){
      $('knowledge-state').textContent='Copie refusée par le navigateur';
    }
  });
  load();
})();
"""

JS = RUNTIME_V5 + "\n" + MEDIA + "\n" + JS_KNOWLEDGE
