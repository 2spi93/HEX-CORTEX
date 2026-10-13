# HEX-CORTEX Command Center — MVP local (lecture seule)

## Objet

La tour de contrôle visuelle est maintenant une application **locale** sur `http://127.0.0.1:8777/`. Elle exploite **les composants existants** : `LocalHarness V2` (probe de fichiers à la demande), `CanonicalSpineJsonlStore` (vérification de la chaîne de hachage), les `inspection.json` V40 et les enregistrements du cockpit statique historique. Il n'y a pas de deuxième mémoire, de deuxième agent autonome ni de faux chat IA.

### Fonctionnel dans ce premier MVP

- Tableau de bord responsive et actualisation des sections, aucune dépendance CDN ;
- les masques *déjà produits* via V40 apparaissent avec leur nom et un aperçu PNG local ;
- intégrité du journal V42/V43 local dédié, nombre d'événements, types d'événements (sans exposer les payloads personnels) ;
- historique de l'ancien `cortex_ui_cockpit_builder` s'il existe, sans modifier ses fichiers ;
- bouton **Exécuter le probe** : seul endpoint POST volontaire. Il appelle le vrai `LocalHarness.execute` avec uniquement le tool existant `repo_manifest`, budget modèle=0 et résultat en mémoire, **pas** d'exécution arbitraire, pas de commandes shell, pas de fichier écrit.

### Non connecté à ce stade

Conversation Ollama/chat, STT/TTS, caméra active, capture écran, nouveaux appels MobileSAM, nouvelles actions MCP, outils de navigateur, Cloud LLM, World Model actif, mémoire principale de production, automatisations ou fonctions d'administration. Les présenter comme « actifs » serait trompeur. Leur intégration suivra le gateway et les permissions du Harness après revue et tests.

## Sécurité / architecture

Serveur HTTP Python standard library **bind uniquement sur 127.0.0.1**, porte `8777` par défaut ; contrôle du header Host et Origin (résistance au DNS rebinding / cross-site), aucun CORS, CSP strict, entêtes X-Frame-Options/CORP/nosniff, pas de ressources externes. Aucune route POST autre que `/api/harness/probe` et le probe exige un header explicite ainsi qu'une origine locale. Les routes de `cortex_server_api` avec enqueue/webhooks **ne sont pas exposées** dans cette interface.

Chemins servis : seulement l'aperçu PNG de masques déjà listés dans un ticket V40, avec identifiants bornés, vérification des chemins/symlinks/tailles et correspondance au dossier local. Le rapport d'état lit uniquement des chemins d'artefact fixés. Les photos et les images appartiennent à l'opérateur ; le serveur n'est pas accessible à travers le LAN. Ne pas l'exposer via reverse proxy, tunneling, pare-feu ou un proxy HTTPS sans une couche d'authentification conçue et auditée.

Les preuves V40/V42 étant locales et issues de tickets opérateurs, un `status: verified` décrit la cohérence de la chaîne, **pas** la qualité des masques ni une intelligence générale. Les modèles restent sur CPU, aucun traitement GPU.

## Démarrage — PowerShell Windows (une commande par ligne)

Dans `C:\Users\2spi\HEX-CORTEX`, conserver `images/`, `receipts/` et `weights/` ; **ne pas nettoyer les dossiers non suivis**.

~~~powershell
git fetch origin
git switch -c feature/command-center-mvp-local-readonly --track origin/feature/command-center-mvp-local-readonly
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_command_center_v1.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_command_center_v1 --project-root . --port 8777 --dry-run
& $VP -m hex_cortex.memory.cortex_command_center_v1 --project-root . --port 8777
~~~

Laisse le terminal ouvert ; dans ton navigateur :

**http://127.0.0.1:8777/**

Pour tester le statut JSON sans interface :

~~~powershell
Invoke-RestMethod http://127.0.0.1:8777/api/snapshot | ConvertTo-Json -Depth 8
~~~

Dans l'interface, clique sur **Exécuter le probe** : cela n'autorise que la lecture de l'inventaire des quatre noms de fichiers `pyproject.toml/README.md/AGENTS.md/CLAUDE.md` (selon leur présence), aucune écriture. Pour arrêter proprement, `Ctrl+C` dans le terminal serveur.

Si les observations V42/V43 n'ont pas été volontairement persistées, le panneau CanonicalSpine affichera `not_recorded`, ce qui est **normal**. La vision affiche le dernier run V40 s'il est encore présent.

## Évolution du Command Center, sans duplication

Phase 2 : modèle Ollama CPU via Brain adapter existant, avec autorisation explicite par requête, température/jetons/temps bornés ; pas d'appels GPU (RX 6700 XT instable). Phase 3 : audio français STT/TTS derrière permissions de micro et environnement dédié ; modules Jarvis tiers en extensions isolées, après revue de licences et dépendances. Phase 4 : préparation d'opérations MCP et d'actions PC dans le sandbox/permission gateway existant, avec audit/révocation. Phase 5 : visualiser les prédictions et comparatifs World Model/V33, puis boucle d'erreur→critic→replay→skill candidate, sans métriques inventées.

La PR reste en brouillon, ne pas fusionner automatiquement à `main` ; ce MVP vise la disponibilité locale, les contrôles de sécurité et l'observabilité, pas l'autonomie complète.
