"""V8 operator-facing actual isolated DeepSeek SDK pilot evidence viewer."""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v7 import (
    CSS as BASE_CSS, HTML as BASE_HTML, JS as BASE_JS,
)

_INSERT = """
<div class="section-title"><h3>Essai SDK réel · VM séparée</h3>
  <span>Rapport importé manuellement et non authentifié</span></div>
<p class="disclaimer">Le test d'agent s'effectue exclusivement dans une VM jetable,
  hors du PC principal et sans accès aux secrets. Le dossier importé prouve
  seulement qu'un programme a déclaré ces résultats. Le Chat HEX-CORTEX ne
  reçoit aucun outil externe. Aucun shell DeepSeek ne s'exécute ici.</p>
<div class="chat-controls">
  <button id="dsh-pilot-refresh" type="button">Relire le reçu de la VM</button>
  <span id="dsh-pilot-state" role="status">Aucun rapport de pilote importé</span>
</div>
<pre id="dsh-pilot-result" class="code-source">En attente d'un reçu validé.</pre>
"""

HTML = (
    BASE_HTML
    .replace(
        "Command Center <em>HEX-CORTEX V7</em>",
        "Command Center <em>HEX-CORTEX V8</em>",
    )
    .replace(
        '<pre id="dsh-metadata" class="code-source">Aucun runtime DeepSeek lancé.</pre>',
        '<pre id="dsh-metadata" class="code-source">Aucun runtime DeepSeek lancé.</pre>'
        + _INSERT,
    )
)

CSS = BASE_CSS + r"""
#dsh-pilot-result{max-height:240px}
#dsh-pilot-state{font-size:12px;color:#abcbd7}
"""

JS_PILOT = r"""
'use strict';
(() => {
  const byId=id=>document.getElementById(id);
  const state=byId('dsh-pilot-state'),out=byId('dsh-pilot-result');
  const button=byId('dsh-pilot-refresh');
  async function reload(){
    button.disabled=true;
    state.textContent='Lecture locale du reçu importé…';
    try{
      const res=await fetch('/api/integrations/deepseek-harness/pilot',{
        cache:'no-store'
      });
      const data=await res.json();
      if(!res.ok)throw Error(data.reason||'HTTP '+res.status);
      if(data.status==='no_operator_imported_receipt'){
        state.textContent='Aucun essai SDK externe rapporté';
        out.textContent='Pas de reçu importé. Aucun agent DeepSeek connecté au Chat.';
        return;
      }
      state.textContent='Essai externe déclaré · non attesté indépendamment';
      out.textContent=[
        'État : '+data.status,
        'Runtime lancé (déclaré par la VM) : '+data.fixture_sdk_turn_reported,
        'Modèle : '+data.model+' / '+data.provider,
        'SDK : '+data.sdk_version_reported,
        'Correction du bug dans le fixture (déclarée) : '+data.fixture_exact_expected_fix_reported,
        'Événements tool/call rapportés : '+data.observed_tool_call_events_reported,
        'Événements tool/result rapportés : '+data.observed_tool_result_events_reported,
        'Noms d’outils authentifiés : NON',
        'Runtime connecté au Chat : NON',
        'Exécution locale depuis le Command Center : AUCUNE',
        'Validation indépendante de l’isolation VM : NON',
        'Promotions CanonicalSpine : AUCUNE',
        'Empreinte du reçu importé : '+data.source_receipt_sha256,
      ].join('\n');
    }catch(err){
      state.textContent='Import refusé : '+err.message;
      out.textContent='Vérifier le schéma, les tailles et les empreintes.';
    }finally{button.disabled=false;}
  }
  button.addEventListener('click',reload);
  reload();
})();
"""

JS = BASE_JS + "\n" + JS_PILOT
