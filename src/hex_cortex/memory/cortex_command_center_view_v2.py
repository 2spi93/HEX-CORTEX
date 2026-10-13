"""Extend the existing V1 cockpit: tabs, real local CPU chat and catalog.

All source strings are bundled and served locally; no external Jarvis code,
CDNs, unsafe HTML interpolation or third-party scripts are injected.
"""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_css_v1 import CSS as BASE_CSS
from hex_cortex.memory.cortex_command_center_html_v1 import HTML as BASE_HTML
from hex_cortex.memory.cortex_command_center_js_v1 import JS as BASE_JS

_CHAT = """
<section id="chat" aria-label="Chat local Ollama">
  <div class="section-title"><h2>Chat · Brain adapter local</h2><span>Ollama · CPU uniquement · une requête à la fois</span></div>
  <div class="panel">
    <p class="disclaimer">Le chat nécessite un démarrage explicite avec --enable-cpu-chat. Aucun outil PC, MCP,
      réseau externe, mémoire durable ou exécution GPU. Les réponses ne sont pas enregistrées par HEX-CORTEX.</p>
    <div class="chat-controls"><label for="chat-model">Modèle local</label>
      <select id="chat-model" aria-label="Modèle installé"><option value="">Non chargé</option></select>
      <button id="load-models" type="button">Rechercher les modèles Ollama</button>
    </div>
    <div class="chat-log" id="chat-log" role="log" aria-live="polite">
      <p class="muted">Choisis un modèle Ollama et envoie un message. Chaque envoi est autorisé séparément.</p>
    </div>
    <form id="chat-form" class="chat-form">
      <label for="chat-prompt">Message à HEX-CORTEX</label>
      <textarea id="chat-prompt" rows="3" maxlength="1600"
        placeholder="Pose une question à ton modèle local CPU…"></textarea>
      <div class="chat-actions"><span id="chat-state" role="status">Non connecté</span>
        <button id="send-chat" type="submit" disabled>Envoyer sur CPU</button>
      </div>
    </form>
  </div>
</section>
"""

_CATALOG = """
<section id="catalog" aria-label="Catalogue des capacités">
  <div class="section-title"><h2>Catalogue des capacités</h2>
    <span>Disponible ≠ exposé ≠ autorisé</span></div>
  <div class="panel"><div class="catalog-toolbar">
      <label for="catalog-search">Rechercher un module</label>
      <input id="catalog-search" type="search" placeholder="Ex. MCP, Memory, voix, World Model">
      <button type="button" id="catalog-refresh">Actualiser l'inventaire</button>
    </div>
    <div id="catalog-list" class="catalog-grid" aria-live="polite">
      <p class="muted">Inventaire en cours de chargement…</p>
    </div>
    <p class="disclaimer">Aucune fonctionnalité marquée non connectée n'exécute d'actions.
       Toute activation future passe par les permissions du Harness existant.</p>
  </div>
</section>
"""

HTML = BASE_HTML.replace(
    '<a href="#vision">', '<a href="#chat">◈ Chat CPU</a><a href="#catalog">▦ Catalogue d’outils</a><a href="#vision">',
).replace('<section id="vision">', _CHAT + '\n<section id="vision">').replace(
    '<section id="roadmap">', _CATALOG + '\n<section id="roadmap">',
).replace(
    'Command Center <em>HEX-CORTEX</em>', 'Command Center <em>HEX-CORTEX V2</em>',
)

CSS = BASE_CSS + r"""
.nav a.current{background:#20536d;color:#e6feff;box-shadow:inset 3px 0 #69d6ec}
.main section[hidden]{display:none!important}
.chat-controls,.chat-actions,.catalog-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0}
.chat-controls label,.chat-form label,.catalog-toolbar label{font-size:12px;color:#99bed0}
select,textarea,input[type=search]{background:#0a1623;color:#e7f8fd;border:1px solid #376078;border-radius:8px;padding:11px;font:inherit}
select{min-width:210px;max-width:100%}textarea{width:100%;resize:vertical;min-height:90px}
input[type=search]{flex:1;min-width:170px}.chat-log{min-height:210px;max-height:370px;overflow:auto;background:#0a1826;border:1px solid #243c51;border-radius:12px;padding:16px;margin:20px 0}
.chat-entry{max-width:88%;margin-bottom:12px;padding:12px 16px;border-radius:12px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;background:#173447;color:#e4f4fc}
.chat-entry.from-user{background:#214b50;margin-left:auto}.chat-entry small{display:block;color:#88bbc2;margin-bottom:6px}
.chat-actions{justify-content:space-between}.chat-actions span{color:#8bb0c5;font-size:12px}
.catalog-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:13px;margin:18px 0}
.catalog-card{border:1px solid #315065;border-radius:12px;padding:15px;background:#0b1d2c;min-height:112px}
.catalog-card strong{display:block;color:#e2f5ff;margin:0 0 8px}
.catalog-card .state{font-weight:600;font-size:11px;color:#7bd7c0}
.catalog-card .state.off{color:#efc18b}.catalog-card p{color:#92aec0;font-size:12px;line-height:1.5}
@media(max-width:520px){.chat-controls select,.chat-controls button{width:100%}.chat-entry{max-width:100%}}
"""

JS = BASE_JS + r"""
// Tab-like navigation: no long scrolling through unrelated panels.
const tabs = Array.from(document.querySelectorAll('.sidebar .nav a'));
const sections = Array.from(document.querySelectorAll('.main section[id]'));
function openTab(id) {
  const chosen = sections.find(s => s.id === id) || sections[0];
  sections.forEach(s => { s.hidden = (s !== chosen); });
  tabs.forEach(a => {
    const active = a.getAttribute('href') === '#' + chosen.id;
    a.classList.toggle('current', active);
    if (active) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  window.scrollTo({top:0,behavior:'instant'});
}
tabs.forEach(a => a.addEventListener('click', e => {
  e.preventDefault();
  const id = a.getAttribute('href').slice(1);
  openTab(id);
  if (history.replaceState) history.replaceState(null, '', '#' + id);
}));
openTab(location.hash.slice(1) || 'overview');
window.addEventListener('hashchange', () => openTab(location.hash.slice(1)));
const displayCatalog = (features, query='') => {
  const target = el('catalog-list');
  target.replaceChildren();
  const normalized = query.toLowerCase();
  for (const item of features.filter(f =>
    (f.name + ' ' + f.id + ' ' + f.status).toLowerCase().includes(normalized))) {
    const card = document.createElement('article'); card.className='catalog-card';
    const title = document.createElement('strong'); title.textContent=item.name;
    const status = document.createElement('span'); status.className='state';
    if (!item.status.startsWith('connected') && !item.status.startsWith('enabled')) status.classList.add('off');
    status.textContent=item.status.replaceAll('_',' ');
    const detail = document.createElement('p'); detail.textContent='Accès : '+item.action.replaceAll('_',' ');
    card.append(title,status,detail); target.append(card);
  }
  if (!target.children.length) {
    const p=document.createElement('p'); p.textContent='Aucun module correspondant.';target.append(p);
  }
};
let capabilityRows=[];
async function updateCatalog() {
  try {
    const response=await fetch('/api/capabilities',{cache:'no-store'});
    if(!response.ok) throw new Error('HTTP '+response.status);
    const info=await response.json();
    capabilityRows=info.features || [];
    displayCatalog(capabilityRows,el('catalog-search').value);
  }catch(e){el('catalog-list').textContent='Inventaire indisponible : '+e.message;}
}
el('catalog-search').addEventListener('input',()=>{
  displayCatalog(capabilityRows,el('catalog-search').value);
});
el('catalog-refresh').addEventListener('click',updateCatalog);
updateCatalog();

// Model inventory is an explicit click; no model gets loaded on page open.
const modelSelector=el('chat-model');
el('load-models').addEventListener('click',async()=>{
  const b=el('load-models');b.disabled=true;
  label('chat-state','Recherche sur Ollama local…');
  try{
    const r=await fetch('/api/ollama/models',{cache:'no-store'});
    const data=await r.json();
    if(!r.ok) throw new Error(data.reason||'HTTP '+r.status);
    modelSelector.replaceChildren();
    for (const name of data.models){
      const option=document.createElement('option');option.value=name;option.textContent=name;
      modelSelector.append(option);
    }
    el('send-chat').disabled=!data.models.length;
    label('chat-state',data.models.length+' modèle(s) disponibles · CPU uniquement');
    if(!data.models.length)label('chat-state','Aucun modèle installé. Vérifie ollama list.');
  }catch(e){
    modelSelector.replaceChildren();
    el('send-chat').disabled=true;
    label('chat-state','Ollama indisponible : '+e.message);
  }finally{b.disabled=false;}
});
const chatLog=el('chat-log');
function appendChat(role,message){
  const entry=document.createElement('div');
  entry.className='chat-entry '+(role==='Vous'?'from-user':'');
  const heading=document.createElement('small');heading.textContent=role;
  const text=document.createElement('div');text.textContent=message;
  entry.append(heading,text);chatLog.append(entry);
  chatLog.scrollTop=chatLog.scrollHeight;
}
el('chat-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const prompt=el('chat-prompt').value.trim();
  const model=modelSelector.value;
  if(!prompt||!model)return;
  const button=el('send-chat');button.disabled=true;
  appendChat('Vous',prompt);
  label('chat-state','Inférence CPU en cours, 45 s maximum…');
  try{
    const response=await fetch('/api/ollama/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-HEX-Chat-Approval':'single-cpu-request'},
      body:JSON.stringify({prompt,model})
    });
    const data=await response.json();
    if(!response.ok||data.status!=='completed')throw new Error(data.reason||'CPU model unavailable');
    appendChat('HEX-CORTEX · '+data.model_used,data.reply);
    label('chat-state','Réponse locale · 1 appel · historique non sauvegardé');
    el('chat-prompt').value='';
  }catch(err){
    appendChat('Erreur',err.message);
    label('chat-state','Échec ou limite CPU atteinte');
  }finally{button.disabled=false;}
});
"""
