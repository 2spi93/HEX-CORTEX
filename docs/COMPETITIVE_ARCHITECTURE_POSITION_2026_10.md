# HEX-CORTEX — positionnement scientifique et concurrentiel (10 octobre 2026)

## Méthode et prudence

Le présent comparatif s'appuie sur les sources publiques des protocoles,
des fournisseurs, des laboratoires de recherche et des responsables des
benchmarks. Il compare **capacités annoncées / architectures publiées** aux
**fonctions réellement identifiées** dans `2spi93/HEX-CORTEX`.
Aucun score de benchmark LLM ou de capacité d'agent HEX-CORTEX n'a été
obtenu. **L'innovation n'est pas démontrée par le nombre de fichiers,
le nombre de tests ou le nom d'un mécanisme cognitif.**

## Principaux faits externes (sources vérifiables)

1. **MCP 2026-07-28 :** noyau de protocole sans session obligatoire,
   requêtes multi-round-trip, extensions formelles (Tasks notamment),
   durcissement de l'autorisation et dépréciation des anciennes primitives.
   Source : https://blog.modelcontextprotocol.io/posts/2026-07-28/
2. **A2A v1.0.0 :** standard de coopération inter-agents,
   modèles et méthodes normatifs, bindings HTTP, JSON-RPC et gRPC;
   SDK officiels multi-langages. Ce protocole ne remplace pas MCP.
   Sources : https://a2a-protocol.org/latest/specification/
   et https://a2a-protocol.org/latest/
3. **Codex :** agents de codage et gouvernance opérationnelle : séparation
   des permissions, sandbox, revue et traçabilité sont des sujets
   d'ingénierie déjà déployés.
   Sources : https://openai.com/index/running-codex-safely/
   et https://developers.openai.com/api/docs/guides/agents/sandboxes
4. **GitHub Copilot cloud agent :** délégation des issues puis génération
   d'une pull request à revoir ; le seul fait de produire des PR n'est
   donc pas une différenciation nouvelle.
   Source : https://docs.github.com/en/copilot/get-started/quickstart-for-using-github-copilot-on-github-com
5. **Letta :** Context Repositories (mémoire versionnée dans Git,
   février 2026), Skill Learning (décembre 2025), Context-Bench V2
   (juillet 2026) et trajectoires d'expérience portables (juillet 2026).
   Le principe d'une mémoire qui traverse les générations de modèles
   et d'un apprentissage de skills n'est plus inédit.
   Sources : https://www.letta.com/blog/context-repositories/
   https://www.letta.com/blog/skill-learning/
   https://www.letta.com/blog/evaluating-memory-in-production-agents/
   https://www.letta.com/blog/trajectory/
6. **SWE-Bench Pro V2 (22 septembre 2026) :** 642 tâches nettoyées,
   protocole d'évaluation verrouillé, contrôles anti-contamination et
   réévaluation sur une image propre : les scores synthétiques publics
   ne suffisent pas à mesurer le codage en conditions réelles.
   Source : https://labs.scale.com/blog/swe-bench-pro-v2
7. **Meta V-JEPA 2 :** monde visuel prédictif entraîné et publié par
   Meta. Les descriptions du CR-JEPA ou du world model HEX-CORTEX,
   sans modèles entraînés ni évalués, n'en sont pas un équivalent.
   Source : https://ai.meta.com/research/vjepa/

## HEX-CORTEX : conclusion comparative fondée sur preuves

| Axe | Positionnement | Précision |
|---|---|---|
| Cerveau interchangeable | Direction utile, mais **standardisation déjà forte** | Adaptateurs OpenAI/Anthropic/Ollama intégrés; requêtes live non attestées |
| Sparse cells, Router/Workspace/Clock | **Architecture originale dans sa composition**, sans preuve d'avantage mesuré | Modèle-free et vérifiable via tests déterministes |
| CanonicalSpine, Gateway, mémoire durable | Point fort de design **centré sur la preuve et la reprise** | Tests de panne et idempotence locaux; pas multi-fichiers ACID |
| Skills apprises | **En convergence avec Letta et l'état de l'art**, pas unique | Revue multi-contextes présente; pas de progrès empirique démontré |
| Coding autonome | **En retard d'intégration opérationnelle** sur des agents cloud prêts à produire/revoir des PR | Tests Python générés désactivés hors sandbox; pas de score SWE-Bench Pro |
| MCP / A2A | **En retard de conformité prouvée** | Sous-ensembles locaux; pas de SDK tiers certifiant le contrat |
| CR-JEPA, world model, LoRA | **Recherche non réalisée** face aux modèles entraînés publiés | Contrats/ledger présents, pas de poids entraînés |
| Confidentialité et contrôle local | Orientation attractive pour usage personnel, **non exclusive** | No-server, cloud optionnel et permissions explicites |

**Bilan :** HEX-CORTEX n'est pas globalement « en avance » sur
l'industrie au sens d'une performance démontrée. Il conserve une
orientation potentiellement différenciante dans la combinaison
des contrôles vérifiables, de la provenance, de la mémoire structurée,
de l'activation de compétences soumise à preuve et d'un fonctionnement
sans modèle local. Sa maturité produit et sa capacité de coder
autonomement restent toutefois moins établies que celles des
outils de production cités.

## La seule direction crédible pour devenir innovant

1. **Une tâche réelle, du début à la fin :** récupérer un problème,
   sélectionner le contexte nécessaire, proposer un patch, l'évaluer
   dans un environnement OS isolé, obtenir une preuve externe et
   enregistrer un épisode sans fuite de secrets.
2. **Apprentissage empirique :** démontrer qu'une même famille de bugs
   est corrigée plus vite ou plus souvent grâce à un skill issu
   d'épisodes *vérifiés* — avec comparaison avant/après et groupe témoin,
   sans utiliser les benchmarks LLM locaux.
3. **Références externes :** tests contre les SDK officiels MCP/A2A,
   puis sur de vrais dépôts non vus avec un protocole anti-contamination.
4. **Autorité minimale :** jamais de promotion automatique de skills,
   de shell non isolé ni de merge implicite.
5. **Évolutivité :** conserver un Brain interchangeable; coûts et
   latences de cloud observés en environnement autorisé, sans
   transformer les empreintes de fichiers en scores de qualité IA.

## Amélioration reliée dans V11

`core/cognitive_replay_pipeline_v11.py` réalise réellement, sur un
circuit hors ligne, la chaîne :
`Task → Router/Cells/Verifier → Clock/Spine → ReplayEngine → MemoryProposal`.
La mémoire reste **proposée, non persistée, non promue**; le système
rapporte explicitement `retrieval_cycle_integrated=false` et
`real_independent_outcome_certified=false`. Cela prépare l'intégration
future sans maquiller la simulation en intelligence entraînée.

Les délimitations commerciales sont un choix : ne pas réintroduire
de VPS HEX-CORTEX, ne pas imposer de modèle local, ne pas rouvrir
les benchmarks de modèles avant un besoin empirique réel.
