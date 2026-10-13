"""V7 plugin-first compatibility dashboard: V6 functions unchanged."""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v6 import (
    CSS as BASE_CSS, HTML as BASE_HTML, JS as BASE_JS,
)

DSH_PANEL = """
<section id="dsh" aria-label="Connexion facultative DeepSeek Harness">
  <div class="section-title"><h2>DeepSeek Harness · intégration contrôlée</h2>
    <span>Runtime externe indépendant · préflight en lecture seule</span></div>
  <div class="panel">
    <p class="disclaimer">Harness officiel DeepSeek : agents de développement, sessions,
      outils, plugins et MCP. Les fonctions sont des candidates, pas des fonctions
      de HEX-CORTEX déjà connectées. Le logiciel tiers peut modifier des fichiers et
      exécuter du code : le lancer exclusivement dans une VM jetable sans montage
      du vrai dépôt, des secrets ou du matériel. Le contrôle CPU reste chez HEX-CORTEX.</p>
    <div class="chat-controls">
      <button id="dsh-refresh" type="button">Examiner le pont DeepSeek</button>
      <span id="dsh-state" role="status">Inventaire non chargé</span>
    </div>
    <div id="dsh-grid" class="catalog-grid"></div>
    <pre id="dsh-metadata" class="code-source">Aucun runtime DeepSeek lancé.</pre>
    <p class="disclaimer">Cette vue ne lance ni agent ni subprocess, ne lit pas
      tes identifiants, n'installe aucun plugin et n'envoie aucune donnée à un tiers.
      Une future connexion utilisera le SDK Python officiel sur une VM isolée,
      puis un examen humain des opérations et de leurs reçus avant CanonicalSpine.</p>
  </div>
</section>
"""

HTML = (
    BASE_HTML
    .replace("Command Center <em>HEX-CORTEX V6</em>",
             "Command Center <em>HEX-CORTEX V7</em>")
    .replace(
        '<a href="#roadmap">',
        '<a href="#dsh">◇ DeepSeek Harness</a><a href="#roadmap">',
    )
    .replace(
        '<section id="roadmap">',
        DSH_PANEL + '<section id="roadmap">',
    )
)

CSS = BASE_CSS + r"""
#dsh-grid article{min-height:108px}
#dsh-metadata{max-height:360px}
#dsh-state{font-size:12px;color:#a9c4d0}
"""

JS_BRIDGE = r"""
'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const state=$('dsh-state'),area=$('dsh-grid'),out=$('dsh-metadata');
  async function refresh(){
    $('dsh-refresh').disabled=true;
    state.textContent='Inspection des métadonnées locales…';
    try{
      const response=await fetch('/api/integrations/deepseek-harness',{
        cache:'no-store'
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.reason||response.status);
      area.replaceChildren();
      for(const entry of data.capabilities){
        const card=document.createElement('article');
        card.className='catalog-card';
        const heading=document.createElement('strong');
        heading.textContent=entry.capability.replaceAll('_',' ');
        const text=document.createElement('p');
        text.textContent=entry.connected?'Présent dans HEX-CORTEX':
          (entry.candidate?'Proposé par DeepSeek · non connecté':'Non disponible');
        const why=document.createElement('p');why.textContent='Gate : '+entry.gate;
        card.append(heading,text,why);area.append(card);
      }
      out.textContent=[
        'SDK Python trouvé (distribution uniquement) : '+
          (data.external_sdk_distribution_installed?
            data.external_sdk_distribution_version:'non installé'),
        'DSH lancé par HEX-CORTEX : NON',
        'Outils, commandes et plugins externes activés : AUCUN',
        'Empreinte des faits HEX-CORTEX : '+data.hex_fact_digest,
        'Empreinte du préflight : '+data.receipt_sha256,
        'Transport futur : '+data.bridge_transport_proposal,
        'Origine : '+data.upstream_repo,
        'Notice sécurité : '+data.upstream_safety_notice,
        'Conditions avant mise en exécution :',
        ...data.requires_before_execution.map(s=>' - '+s)
      ].join('\n');
      state.textContent='Pont inventorié · aucun runtime externe lancé';
    }catch(err){
      state.textContent='Lecture refusée : '+err.message;
      out.textContent='Aucune donnée de compatibilité disponible.';
    }finally{$('dsh-refresh').disabled=false;}
  }
  $('dsh-refresh').addEventListener('click',refresh);
  refresh();
})();
"""

JS = BASE_JS + "\n" + JS_BRIDGE
