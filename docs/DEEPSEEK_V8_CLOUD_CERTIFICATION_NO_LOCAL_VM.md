# V8.1 — Certifier le SDK DeepSeek sans VMware ni GPU local

## Pourquoi on change la procédure

Le PC opérateur HEX-CORTEX a reproduit des écrans verts avec la RX 6700 XT (y compris VMware). Les tests matériels GPU, benchmarks DeepSeek et lancement d'une VM locale sont **suspendus** jusqu'à diagnostic du bloc alimentation + câblage PCIe + carte graphique. Le Command Center V8 peut rester disponible en simple mode CPU si le PC est stable, mais il ne sert pas à tester la stabilité GPU.

**Preuves existantes sur l'hôte (octobre 2026) :** 32 passed, 2 skipped pour les tests ciblés V8, Ruff sans erreur, Command Center V8 fonctionnel, aucune inférence DSH réelle depuis le poste utilisateur.

## Niveau B — GitHub Actions CPU cloud, aucun modèle, aucune clé

Workflow indépendant : [.github/workflows/v8-cloud-deepseek-sdk-preflight.yml](../.github/workflows/v8-cloud-deepseek-sdk-preflight.yml).

- Déclenché sur PR lorsque le fichier du workflow ou le pilote V8 évolue.
- Machine Ubuntu GitHub hébergée, CPU et réseau de la machine distante uniquement.
- **Pas de checkout** du code du dépôt, aucune permission GitHub API, aucun secret ni clé fournie.
- Téléchargement exact deepseek-harness-sdk==0.1.5rc1 depuis PyPI, empreinte SHA256 attendue 8d9897e97e8a95fd738cb2c3e2c563951d824e43847ec6f3b0fb172c0729b4d8 (valeur publiée par PyPI le 10 septembre 2026).
- Installation des dépendances du SDK, vérification que deepseek-harness-runtime-bin est à la même version, import de DeepSeekHarness et inspection de l'API publique, vérification que la commande dsh est disponible, sans l'exécuter.
- Artefact JSON v8-deepseek-sdk-cloud-preflight-ubuntu, indicateurs model_called=false, runtime_process_started=false, real_model_functionality_certified=false.

Le chargement de packages depuis PyPI présente un risque supply chain résiduel, limité ici à un runner GitHub éphémère sans secrets ni dépôt monté. Cela constitue un test d'intégration du package, **pas une preuve de sécurité** ni d'agent en fonctionnement.

Le workflow peut être testé via une PR sur cette branche sans toucher au PC. L'évènement workflow_dispatch existe également dans le fichier, mais GitHub nécessite que le workflow soit présent sur la branche par défaut pour proposer le déclenchement manuel. Ne pas fusionner main automatiquement juste pour débloquer ce bouton.

Références : [GitHub Actions déclenchement manuel](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow), [DeepSeek SDK PyPI](https://pypi.org/project/deepseek-harness-sdk/).

## Niveau C — Test véritable de l'agent, également déporté

Pour obtenir une preuve d'agent autonome et non une simple importation Python, choisir ensuite un seul environnement distant jetable :

- Un VPS cloud neuf, Linux, réservé exclusivement à ce test et à détruire ensuite, **pas le VPS GTIXT ou TXT**.
- Ou un job GitHub Actions manuel spécifique avec protection environnement et secret API dédié, introduit uniquement après audit et approbation explicite. Les workflows déclenchés sur PR ne doivent JAMAIS obtenir ce secret.

Conditions techniques pour déclarer le pilote « fonctionnel sur fixture » :

1. Version du SDK et du runtime réellement épinglées et enregistrées.
2. Projet artificiel isolé, test de départ échouant pour la raison attendue.
3. Session DSH sdk-minimal qui lance réellement son moteur JSON-RPC et obtient une réponse modèle.
4. Au moins un appel d'outil rapporté, avec log opérateur permettant d'examiner les commandes émises.
5. Correction obtenue uniquement sur calc.py, original test_calc.py/README.md préservés, aucun fichier additionnel inattendu.
6. Exécution indépendante du test après arrêt de l'agent, sous un environnement encore jetable (jamais sur PC principal). La seule affirmation « tests passed » dans le texte d'un LLM n'est pas une preuve.
7. Copie manuelle du reçu JSON expurgé vers receipts/v8_deepseek_sdk/operator_import.json puis contrôle via GET /api/integrations/deepseek-harness/pilot.

**Limites :** succès fonctionnel d'une tâche jouet ≠ audit de sécurité, gestion effective d'outils sur HEX-CORTEX, capacité de recherche Web, évaluation de performance réelle ou autonomie fiable. Pour brancher un registre d'outils au Chat, il faut encore un Gateway d'autorisation, une sandbox indépendante et un protocole d'évaluation.

## Quand le matériel Windows sera réparable

Ne reprends pas VMware ni les benchmarks GPU tant que l'alimentation, la présence de deux câbles PCIe GPU indépendants et l'état de la carte RX 6700 XT n'auront pas été vérifiés. Vérifier la puissance et les connecteurs du bloc d'alimentation avant toute manipulation. Débrancher secteur avant intervention. Dans le doute, privilégier un professionnel pour l'alimentation et la carte.
