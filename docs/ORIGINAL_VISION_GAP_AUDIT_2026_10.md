# HEX-CORTEX — audit de fidélité à la vision originale (10 octobre 2026)

## Provenance de cet audit

Comparaison des archives de conversation transmises par le projet
(`Modèles IA compacts et puissants.txt`, `Hex-Cortex Avancement.txt`,
`Avancement blocs parallèles.txt`, `Cortex local backend plan.txt`,
`V8.5 FinalEndStateCertificate.txt`), des discussions récentes et
des chemins réellement inspectés dans le dépôt GitHub `2spi93/HEX-CORTEX`.

Cet inventaire **ne prouve pas** que toute capacité a été testée dans
un environnement utilisateur. Les niveaux de vérité sont :

- **Code confirmé** : fichier(s) identifiés et inspectés.
- **Contrat ou test déterministe** : surface logicielle démontrée, mais
  pas nécessairement activité avec un vrai modèle/service/jeu de données.
- **Intégration partielle** : des sous-systèmes existent mais leur
  fonctionnement commun n'est pas encore certifié.
- **Recherche/différé** : prévu explicitement, sans preuve d'exécution
  fonctionnelle ou de formation d'un modèle.

Les modules ci-dessous sont autant que possible réutilisés, sans
réécrire ou dupliquer le socle historique.

## Vision fondatrice — état constaté

| Pilier | Évidence existante | État prudent / écart |
|---|---|---|
| Exosquelette cognitif indépendant du LLM | `cortex_local_harness_v2.py`, `cortex_cloud_brain_v5.py` | Code confirmé; APIs réelles OpenAI/Anthropic non testées |
| Thalamic Router et activation sparse | `core/router.py`, `core/cell_registry.py` | Code confirmé; coordination initialement séparée du Harness |
| Trois vitesses REFLEX/WORKING/DEEP | `core/schemas.py`, `core/router.py` | Routage déterministe, comportements avancés non prouvés |
| CognitiveClock + boucle bornée | `core/cognitive_clock.py` | Code et tests; durée synchrone contrôlée a posteriori, non préemptive |
| Global Workspace | `core/workspace.py` | Code confirmé; contenu cognitif exploitable non certifié |
| CanonicalSpine / provenance | `spine/canonical_spine.py`, `spine/jsonl_store.py` | Hash-chain, persistance et replay vérifiables ; pas d'attestation externe |
| Immunité, trust, quarantaine, double-check | `core/cell_registry.py`, `evolver/schemas.py` | Politique démontrable; verifier externe obligatoire pour une vraie preuve |
| Memoires et apprentissage de compétences | `memory/cortex_cognitive_memory.py`, `memory/cortex_cognitive_residuals.py`, les artefacts de skill | Ledger, graphe et règles présents ; qualité d'apprentissage transversal à vérifier |
| Cognitive Genome et ontologie d'erreurs | `docs/COGNITIVE_GENOME_IMPLEMENTATION_STATUS.md`, `config/cognitive_genome_v1.json` | Gouvernance et contrôles, pas mutation automatique des poids |
| Résidu topologique et homéostasie | `memory/cortex_cognitive_genome*.py`, `memory/cortex_cognitive_residuals.py` | Contrats et opérations, pas apprentissage prédictif entraîné |
| Conseil de profils et juge constitutionnel | `docs/COGNITIVE_GENOME_ADAPTIVE_DISTILLATION_AND_CR_JEPA_V0.md` et implémentations genome | Gouvernance et politique de preuve, pas débat multi-modèle validé |
| CR-JEPA / monde causal | `docs/COGNITIVE_GENOME_ADAPTIVE_DISTILLATION_AND_CR_JEPA_V0.md` | Manifeste/dataset et seuils de recherche, **aucun CR-JEPA entraîné prouvé** |
| Distillation adaptative / LoRA | `docs/SELF_IMPROVEMENT.md` et registre d'adaptateurs | Projets gouvernés; pas de distillation/LoRA active entraînée |
| World Model multimodal | `docs/MULTIMODAL_WORLD_MODEL_PATH_V1.md`, `memory/cortex_world.py` | Descripteurs, calculs et simulations; pas un modèle physique appris complet |
| Multimodal image, vidéo, 3D, voix | `memory/cortex_media.py`, `memory/cortex_media_to_latent_cli.py` | Rails et contrats présents; génération GPU/flux live non prouvés |
| Coding sûr, worktree, patch review | `memory/cortex_coding_runtime_cli.py` | Commandes, permissions et rails présents; cycle autonome complet non certifié |
| Recherche web, sources, agents externes | `memory/cortex_research_runtime_cli.py`, MCP, A2A local | Plusieurs adaptateurs; conformité intégrale SDK et vrai flux non certifiés |
| Skills transférables / mémoire procédurale | `evolver/agent_skill_portability.py`, `memory/cortex_mcp_skills.py` | Export/catalogue opt-in ; pas confiance/promotions automatiques |
| Federation GTIXT strictement isolée | `memory/cortex_gtixt_offline_bridge.py` | 7 catégories lecture seule, snapshot opt-in; pas import mémoire ou accès live |
| Codes binaires E8 / CognitiveECC / Adinkra | Mention dans nos échanges sur `/opt/txt/src/hex_cortex/codes/` | **Non localisés dans les chemins GitHub `src/hex_cortex/codes/*` vérifiés**; une installation sur l'ancien environnement `/opt/txt` ne démontre pas son intégration au dépôt actuel |

### Point d'architecture à corriger — intégré dans V6

Auparavant, `ThalamicRouter`, `CellRegistry`, `GlobalWorkspace`,
`CognitiveClock` et `CanonicalSpine` possédaient chacun leurs tests,
sans démonstration suffisamment directe de la sélection de cellules,
de leur résultat typé, d'une preuve vérifiée et d'un état de confiance
traversant *un même circuit*. V6 ajoute
`core/cognitive_circuit_v1.py`, un orchestrateur
**entièrement déterministe et sans modèle**, avec :

- sélection uniquement parmi les cellules saines et non quarantinées ;
- budget de cellule, mode REFLEX/WORKING/DEEP et horloge bornée ;
- workspace minuscule, objectif hashé ;
- résultat `CellResult` typé avec références d'évidence obligatoires ;
- vérificateur injecté explicitement ; deuxième vérificateur distinct
  obligatoire pour les cellules `requires_double_check` ;
- dégradation de réputation lorsque la vérification échoue ;
- chaîne CanonicalSpine et rapports privés de prompts/réponses ;
- interdiction implicite de modifier les dépôts, de promouvoir des skills
  ou d'appeler un LLM.

**Limite :** un callback Python injecté peut avoir des effets de bord.
Ce circuit n'est pas un bac à sable, et la fiabilité d'un vérificateur
ne peut pas être garantie par sa seule signature. L'hôte/gateway doit
imposer l'isolation des outils et une preuve indépendante.

### Correctif de confidentialité V6

`CognitiveClock` persistait auparavant `str(exc)` dans la spine en cas
d'échec de handler. Une exception externe peut révéler un prompt, un token
ou une clé. V6 conserve seulement `tick_handler_failed`. La clock
détecte aussi un dépassement de budget après un tick synchrone; elle ne
peut pas préempter du Python arbitraire.

## Alignement doctrinal après les décisions récentes

1. HEX-CORTEX demeure un **cortex généraliste pour coder, inspecter,
   réparer, apprendre, compresser et réutiliser des compétences vérifiées**.
   Ce n'est pas un robot de trading ou GTIXT.
2. **Pas de serveur HEX-CORTEX.** Les plans historiques « server-later »,
   Hermes distant, n8n et `llama-server` sont supersédés ou hors périmètre.
3. **Pas de modèle local ni de benchmark LLM obligatoire.**
   Le matériel sera amélioré plus tard. Les tests `pytest`, Ruff,
   contrats, replay, données synthétiques et mocks restent valides.
4. Un cerveau hébergé via OpenAI/Anthropic reste possible avec double
   autorisation et compte API propre; aucune requête cloud n'a été réalisée
   dans la CI.
5. Aucune amélioration, correction, promotion, revue, patch ou fusion n'est
   automatiquement certifiée par une simple réponse LLM.
6. Ne pas utiliser les exercices synthétiques ou les sorties du Mock Brain
   comme mesure d'intelligence générale.

## Reste à construire / à prouver (sans attendre un nouveau PC)

### P0 — protection et invariants de production

- Contrôler la fuite de données dans tous les rails événements/receipts,
  pas seulement le noyau corrigé V6.
- Renforcer budget/cancellation/timeout indépendants de la bonne volonté
  du modèle ; évaluer les callbacks synchrones à long terme.
- Reprise sur panne, atomicité/durabilité des écritures de mémoire,
  concurrence entre écrivains, déduplication et tests de restauration.
- Isolation stricte par projet et par intention de données transmises au cloud.
- Automatiser l'analyse de sécurité des chemins, imports, worktrees et
  permissions avant toute proposition d'autonomie.

### P1 — « système vivant » réellement relié

- Chaîner retrieval sélectif → workspace → router → critic →
  memory residual → skill candidate → review → replay,
  sur une même tâche **avec des données de preuve externes réelles**.
- Ajouter un paquet de preuves reproductible, lisible par un humain,
  et une politique de promotion/révocation vérifiée.
- Interop MCP/A2A contre clients SDK réels et contrôles d'accès ;
  le sous-ensemble maison n'est pas une conformité certifiée.
- Tester de vrais dépôts dans un environnement local d'isolation
  adapté au matériel et aux contraintes de sécurité, sans VPS.

### P2 — recherche empirique / non bloquante pour l'ingénierie

- CR-JEPA et dynamique latente entraînée, distillation adaptative, LoRA,
  comparaison de cerveaux et mesures GPU restent **recherche**.
- Capture/voix/vision en temps réel et génération vidéo/3D GPU
  restent différées si le PC ne peut pas les supporter.
- E8/Adinkra/CognitiveECC : valider une stratégie de portage depuis
  les anciennes copies `/opt/txt` avant d'affirmer leur présence;
  la correction de bits est une propriété mathématique, pas une preuve
  de robustesse cognitive.
- Les idées philosophiques/mathématiques (nombre d'or, attracteurs,
  auto-organisation) sont des heuristiques de recherche, pas
  des lois scientifiques ou un avantage chiffré validé.

## Critères honnêtes de fin de projet

- **Core stable** : code, contrats et CI stables sur Windows et Linux.
- **Protocole/Hands stable** : autonomie bornée en environnement isolé,
  sans accès élargi implicite ; vrais tests d'interopérabilité.
- **Learning validé** : preuve que des erreurs observées peuvent créer
  des skills réutilisables, sans régression ni auto-promotion.
- **Recherche avancée** : distincte du jalon produit stable.
- **API cloud testées réellement** : distinctes de la simulation;
  seulement sur consentement, compte/API et coût du propriétaire.

Aucune affirmation « production_ready=true » ne doit être émise avant
la levée et la validation des blocages critiques par une preuve adéquate.
