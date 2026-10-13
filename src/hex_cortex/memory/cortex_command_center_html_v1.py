"""Self-hosted offline Command Center HTML; no third-party dependencies."""

HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>HEX-CORTEX · Command Center</title>
<link rel="stylesheet" href="/assets/command-center.css"><script defer src="/assets/command-center.js"></script></head>
<body><div class="shell">
<aside class="sidebar">
<div class="brand"><span class="logo">✦</span><div><strong>HEX-CORTEX</strong><small>COMMAND CENTER / MVP</small></div></div>
<nav class="nav"><a href="#overview">◉ Vue générale</a><a href="#vision">▣ Perception visuelle</a>
<a href="#memory">◇ CanonicalSpine</a><a href="#harness">⌘ Harness & outils</a>
<a href="#roadmap">↗ Modules à brancher</a></nav>
<div class="sidebar-foot"><span class="dot"></span> LOCAL · CPU SAFE <small>Lecture seule par défaut</small></div></aside>
<main class="main"><header><div><div class="eyebrow">CONSOLE OPÉRATEUR · PHASE 1</div>
<h1>Command Center <em>HEX-CORTEX</em></h1><p>Observabilité locale, preuves et inspection des masques. Aucune autonomie implicite.</p>
</div><button id="refresh" type="button">↻ Actualiser</button></header>
<div class="notification" id="banner" role="status" aria-live="polite">Chargement des données locales…</div>
<section id="overview"><div class="section-title"><h2>État opérationnel</h2><span>État lu localement · pas de modèles chargés</span></div>
<div class="metric-grid">
<article class="metric"><span>Mode actif</span><strong id="mode">—</strong><small>CPU / accès borné</small></article>
<article class="metric"><span>Scènes inspectables</span><strong id="scenes">—</strong><small>V40 · résultats opérateur</small></article>
<article class="metric"><span>Masques PNG</span><strong id="masks">—</strong><small>Prédictions non annotées</small></article>
<article class="metric"><span>Événements de mémoire locale</span><strong id="events">—</strong><small>V42/V43 si enregistrés</small></article></div></section>
<section id="vision"><div class="section-title"><h2>Perception visuelle</h2><span>Dernière inspection V40</span></div>
<div class="panel"><div class="panel-head"><strong>Objets segmentés et aperçus</strong><small>Masques prédits · aucune IoU humaine</small></div>
<div id="vision-list" class="vision-grid"><p class="muted">Aucun résultat encore chargé.</p></div></div></section>
<section id="memory"><div class="section-title"><h2>CanonicalSpine</h2><span>Journal dédié aux observations visuelles</span></div>
<div class="panel"><div class="row"><span>Intégrité locale de la chaîne</span><strong id="spine-status">—</strong></div>
<div class="row"><span>Prédictions d'objets enregistrées</span><strong id="spine-visual">—</strong></div>
<div class="row"><span>État du cockpit existant</span><strong id="cockpit-status">—</strong></div>
<div class="events" id="event-types"></div>
<p class="disclaimer">Un événement haché confirme la cohérence des enregistrements, pas la vérité des contours ni l'identité entre images.</p></div></section>
<section id="harness"><div class="section-title"><h2>Harness & diagnostics</h2><span>Réutilise LocalHarness V2</span></div>
<div class="panel harness"><strong>Probe de dépôt en lecture seule</strong>
<p>Action explicitement déclenchée : liste autorisée des fichiers racine. Exécution en mémoire, sans IA, sans shell et sans écriture.</p>
<code>LocalHarness → repo_manifest → SHA-256 → CanonicalSpine (mémoire)</code>
<button type="button" id="probe">Exécuter le probe</button>
<pre id="probe-result" aria-live="polite">En attente d'autorisation.</pre></div></section>
<section id="roadmap"><div class="section-title"><h2>Extensions Jarvis / OpenJarvis</h2><span>Connexions futures, pas de fonctionnalités fictives</span></div>
<div class="feature-grid">
<article><strong>◈ Chat multimodèle</strong><small>Non connecté — Ollama et autres Brain adapters à autoriser.</small></article>
<article><strong>◉ Voix française</strong><small>Non connectée — micro, STT et TTS isolés.</small></article>
<article><strong>◐ Vision interactive</strong><small>Inspection V40 en lecture — nouvelles images sur approbation.</small></article>
<article><strong>⌘ MCP & outils PC</strong><small>Non connectés — permissions et sandbox nécessaires.</small></article>
<article><strong>◇ World Model</strong><small>Prédiction/évaluation indépendante à brancher.</small></article>
<article><strong>▤ Benchmarks</strong><small>Mesure avec/sans Harness à intégrer.</small></article>
</div></section><footer>HEX-CORTEX · Localhost uniquement · Ni GPU, ni cloud, ni commandes arbitraires</footer>
</main></div></body></html>"""
