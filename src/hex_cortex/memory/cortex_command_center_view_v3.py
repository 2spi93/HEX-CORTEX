"""V3 locally scoped conversational UX, built from V2 without a second frontend."""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v2 import (
    CSS as BASE_CSS,
    HTML as BASE_HTML,
    JS as BASE_JS,
)

HTML = (
    BASE_HTML.replace(
        'Command Center <em>HEX-CORTEX V2</em>',
        'Command Center <em>HEX-CORTEX V3</em>',
    )
    .replace(
        '<button id="load-models" type="button">Rechercher les modèles Ollama</button>',
        '<button id="load-models" type="button">Rechercher les modèles Ollama</button>'
        '<button id="new-conversation" type="button">Nouvelle conversation</button>',
    )
    .replace(
        "Les réponses ne sont pas enregistrées par HEX-CORTEX.",
        "Les trois derniers échanges peuvent être renvoyés au modèle dans la même "
        "conversation, sans sauvegarde sur disque. Changer de modèle efface ce contexte.",
    )
    .replace(
        "Non connecté — Ollama et autres Brain adapters à autoriser.",
        "Chat Ollama CPU disponible après activation ; aucun outil connecté au chat.",
    )
    .replace(
        '<span id="chat-state" role="status">Non connecté</span>',
        '<span id="chat-state" role="status">Contexte temporaire, local à cet onglet</span>',
    )
)

CSS = BASE_CSS + r"""
#new-conversation{background:#142b40;border-color:#45647a}
#new-conversation:hover{background:#1d3b55}
.chat-entry.from-assistant{background:#173447}
.chat-status-row{display:flex;align-items:center;gap:15px;flex-wrap:wrap}
.chat-status-row strong{color:#93e4d9;font-size:11px}
#chat-form[aria-busy=true]{opacity:.92}
@media(max-width:520px){#new-conversation{width:100%}}
"""

# Keep V2's functioning catalog/tab/model-discovery code; only replace the
# V2 submit handler so one real user click can never trigger two model calls.
V2_SUBMIT_BEGIN = "const chatLog=el('chat-log');"
if V2_SUBMIT_BEGIN not in BASE_JS:
    raise RuntimeError("V3 requires known V2 chat view")
JS = BASE_JS.split(V2_SUBMIT_BEGIN, 1)[0].replace(
    "Lecture seule · Aucun modèle exécuté · Aucun événement ou fichier créé par le tableau de bord",
    "Tableau de bord en lecture seule · Chat CPU sur demande · Aucune écriture par l'interface",
) + r"""
const chatLog = el('chat-log');
const chatForm = el('chat-form');
const chatPrompt = el('chat-prompt');
const sendChat = el('send-chat');
const newConversation = el('new-conversation');
// Client-held conversational context only; no localStorage, cookies, or server
// memory. This is intentionally NOT trusted verified event evidence.
let chatHistory = [];
let requestActive = false;

function appendChat(role, message) {
  const entry = document.createElement('div');
  entry.className = 'chat-entry ' + (role === 'Vous' ? 'from-user' : 'from-assistant');
  const heading = document.createElement('small');
  heading.textContent = role;
  const contents = document.createElement('div');
  contents.textContent = message;
  entry.append(heading, contents);
  chatLog.append(entry);
  chatLog.scrollTop = chatLog.scrollHeight;
}
function clearChat(reason) {
  if (requestActive) return;
  chatHistory = [];
  chatLog.replaceChildren();
  const info = document.createElement('p');
  info.className = 'muted';
  info.textContent = reason;
  chatLog.append(info);
  chatPrompt.value = '';
  label('chat-state', 'Contexte effacé · Aucun historique écrit sur disque');
}
newConversation.addEventListener('click', () =>
  clearChat('Nouvelle conversation : aucun échange précédent envoyé au modèle.')
);
modelSelector.addEventListener('change', () =>
  clearChat('Modèle changé : conversation repartie sans ancien contexte.')
);
// Reloading the model list can silently select a different first model.
// Invalidate the conversational context before such a change.
el('load-models').addEventListener('click', () =>
  clearChat('Liste des modèles actualisée : contexte précédent effacé.')
);

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (requestActive) return;
  const prompt = chatPrompt.value.trim();
  const model = modelSelector.value;
  if (!prompt || !model) return;
  requestActive = true;
  sendChat.disabled = true;
  modelSelector.disabled = true;
  newConversation.disabled = true;
  el('load-models').disabled = true;
  chatForm.setAttribute('aria-busy', 'true');
  const historyForRequest = chatHistory.slice(-6);
  appendChat('Vous', prompt);
  label('chat-state', 'Inférence CPU en cours · 45 s maximum · ' +
    (historyForRequest.length / 2) + ' échange(s) repris');
  const began = performance.now();
  try {
    const response = await fetch('/api/ollama/conversation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-HEX-Chat-Approval': 'single-cpu-request'
      },
      body: JSON.stringify({prompt, model, history: historyForRequest})
    });
    const data = await response.json();
    if (!response.ok || data.status !== 'completed') {
      throw new Error(data.reason || 'Modèle indisponible');
    }
    appendChat('HEX-CORTEX · ' + data.model_used, data.reply);
    // Keep exactly three previous user/assistant pairs. Truncation changes
    // the model's context and is not a claim of full long-term memory.
    chatHistory.push(
      {role: 'user', content: prompt.slice(0, 600)},
      {role: 'assistant', content: data.reply.slice(0, 600)}
    );
    chatHistory = chatHistory.slice(-6);
    chatPrompt.value = '';
    const elapsed = Math.round(performance.now() - began);
    label('chat-state',
      'Réponse CPU · ' + elapsed + ' ms côté navigateur · ' +
      (data.history_items_used / 2) + ' échange(s) réutilisés · non sauvegardé');
  } catch (error) {
    appendChat('Erreur de requête', error.message);
    label('chat-state', 'Échec · le message n’a pas été ajouté au contexte');
  } finally {
    requestActive = false;
    sendChat.disabled = false;
    modelSelector.disabled = false;
    newConversation.disabled = false;
    el('load-models').disabled = false;
    chatForm.setAttribute('aria-busy', 'false');
  }
});

"""
