# HEX-CORTEX V8 — Premier agent DeepSeek Harness **réel** dans une VM jetable

## État prouvé et limite

Le préflight V7 transmis par l'opérateur indique `external_sdk_distribution_installed=false`, `external_runtime_launched=false`, `real_deepseek_integration_attested=false`. L'intégrité de la mémoire visuelle CanonicalSpine est vérifiée, mais cela ne prouve pas que DeepSeek est déjà branché.

V8 fournit deux briques séparées :

1. **Pilote exécutable** `cortex_deepseek_sdk_pilot_v8.py` utilisant réellement l'API publique officielle `from deepseek_harness import DeepSeekHarness`, profil **`sdk-minimal`**, `with DeepSeekHarness(..., cwd=..., dsh_home=..., profile='sdk-minimal') as client: client.run(...)`. Il ne s'exécute qu'après double consentement explicite et sur un projet fictif créé dans un environnement extérieur au dépôt. Le profil minimal dispose **réellement d'un shell**, donc ce n'est PAS une sandbox.
2. **Import à lecture seule** `operator_import.json` et visualisation dans la page DeepSeek Harness du Command Center V8. Les événements sont réduits à des nombres et des empreintes : aucune commande, contenu de fichier, clé ou texte du modèle n'est injecté dans CanonicalSpine ou dans le chat HEX.

Références officielles vérifiées le 13 octobre 2026 :

- [README du SDK Python](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md)
- [Exemple Python du fournisseur](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/examples/minimal.py)
- [Avertissement de sécurité](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)

**Le logiciel est encore en developer preview et non audité.** L'API, les plugins et profils peuvent changer. Le drapeau `--ack-disposable-vm` **n'atteste PAS matériellement qu'une VM existe** : l'opérateur doit vérifier lui-même l'isolation réelle. Ne PAS exécuter le pilote sur l'hôte Windows contenant les dépôts ou clés GTIXT/HEX/TXT, ni dans WSL2 avec lecteurs Windows montés. Aucune garantie ne provient des seuls prompts, du SDK ou des validations Python.

## A — Mettre à jour le Command Center sur ton Windows 11 (ne lance pas DeepSeek)

Dans PowerShell après avoir arrêté V7 avec Ctrl+C :

```powershell
git fetch origin
git switch -c feature/v8-deepseek-sdk-isolated-agent-pilot --track origin/feature/v8-deepseek-sdk-isolated-agent-pilot
$VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
& $VP -m pytest -q tests/test_cortex_deepseek_sdk_pilot_v8.py tests/test_cortex_deepseek_sdk_receipt_v8.py tests/test_cortex_command_center_v7.py
& $VP -m ruff check .
& $VP -m hex_cortex.memory.cortex_command_center_v8 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision
```

Dans la page `http://127.0.0.1:8777/`, onglet **DeepSeek Harness**, le résultat initial normal est « Aucun essai SDK externe rapporté ». Le serveur V8 conserve l'état V7, le Chat CPU et MobileSAM V6. Il ne lance **jamais** un agent.

## B — VM jetable : installer réellement le SDK, sans accès à l'hôte

Préparer une VM **Debian 12/13 ou Ubuntu**, avec ses propres ressources, réseau maîtrisé, disque jetable, aucun dossier partagé avec Windows, aucun montage des répertoires personnels, aucune clé ou compte principal. Prendre un snapshot de cette VM **avant** installation et ne pas stocker de secrets persistants importants. Clone GitHub public dans la VM uniquement : c'est une **copie** de code, pas le vrai dépôt local Windows.

Commandes bash **dans le terminal de la VM**, une ligne par commande :

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
git clone --branch feature/v8-deepseek-sdk-isolated-agent-pilot --single-branch https://github.com/2spi93/HEX-CORTEX.git ~/hex-v8-vm-copy
python3 -m venv ~/dsh-v8-venv
source ~/dsh-v8-venv/bin/activate
python -m pip index versions deepseek-harness-sdk
```

Vérifie les versions disponibles et les notices du projet, puis **choisis une version précise**. Par exemple, en remplaçant le texte entre chevrons par une vraie version publiée :

```bash
SDK_VERSION='REMPLACER_PAR_VERSION_AUDITEE'
python -m pip install "deepseek-harness-sdk==$SDK_VERSION"
python -c "import importlib.metadata as m; print('SDK:',m.version('deepseek-harness-sdk'),'Runtime:',m.version('deepseek-harness-runtime-bin'))"
cd ~/hex-v8-vm-copy
export PYTHONPATH="$(pwd)/src"
python -m hex_cortex.memory.cortex_deepseek_sdk_pilot_v8 --workspace ~/hex-v8-fixture
python -m hex_cortex.memory.cortex_deepseek_sdk_pilot_v8 --workspace ~/hex-v8-fixture --prepare-fixture --approve-create-fixture
```

Ces premières lignes ne chargent **aucun modèle** et ne démarrent **aucun agent DeepSeek**. Vérifie que le dossier `~/hex-v8-fixture` contient exactement `calc.py`, `test_calc.py`, `README.md`. Il contient volontairement un `add()` incorrect et un test standard Python.

### Premier agent réel — une seule tâche, sur le projet artificiel

Une fois la VM vérifiée comme isolée, après examen du fournisseur, des politiques de réseau et du SDK, crée éventuellement un **jeton DeepSeek dédié à budget très faible** dans la VM, jamais ton identifiant principal et jamais dans la conversation ChatGPT. Attention : l'agent pouvant exécuter des commandes dans la VM, l'accès au jeton ou au réseau reste possible ; la séparation VM ne transforme pas ce jeton en secret inaccessible à l'agent.

```bash
read -rsp 'Cle API de test (VM seulement) : ' DEEPSEEK_API_KEY; echo
export DEEPSEEK_API_KEY
python -m hex_cortex.memory.cortex_deepseek_sdk_pilot_v8 --workspace ~/hex-v8-fixture --dsh-home ~/dsh-v8-home --run-agent --ack-disposable-vm --approve-model-and-shell --expected-sdk-version "$SDK_VERSION" --provider deepseek-official --model deepseek-v4-flash > ~/dsh-v8-report.json
cat ~/dsh-v8-report.json
unset DEEPSEEK_API_KEY
```

Le programme appelle **le véritable runtime DSH** via le SDK; le modèle peut modifier le projet fictif et lancer `python -m unittest` parce que **`sdk-minimal` expose un shell persistant**. Les options `request_timeout_seconds=120`, `max_tokens=2048` et le contexte `dsh_home` indépendant limitent l'essai, mais ne constituent pas une isolation OS ni une garantie complète d'arrêt des processus descendants.

L'agent doit corriger l'addition, exécuter les tests et retourner son résultat. Inspecte manuellement `calc.py`, `test_calc.py`, les fichiers créés, les événements de session dans `~/dsh-v8-home`, et les activités processus/réseau. Le reçu **ne certifie pas** que les tests ont réellement réussi ; il mesure seulement si la sortie de `calc.py` correspond exactement au correctif attendu et combien d'événements de types `tool/call` et `tool/result` le runtime a émis. Il ne contient ni traces de commandes, ni sortie du modèle, seulement des empreintes et des comptes.

Si le fournisseur ou le modèle est indisponible, le pilote échoue sans accorder de nouveaux droits à HEX. Le support d'un modèle Ollama local par le runtime DSH dépend de l'adaptateur et du profil installés; il n'est PAS garanti par la simple présence d'Ollama.

## C — Revenir au Command Center : importer uniquement les métriques expurgées

Après vérification du contenu du rapport **dans la VM**, transfère uniquement `~/dsh-v8-report.json` depuis la VM vers l'hôte par un canal explicitement contrôlé (par exemple un transfert SSH/SCP configuré manuellement). **Ne monte pas tout le dossier HEX-CORTEX de Windows dans la VM.**

Dans le dépôt HEX-CORTEX Windows :

```powershell
New-Item -ItemType Directory -Force -Path .\receipts\v8_deepseek_sdk | Out-Null
```

Place la copie du JSON revu dans `receipts\v8_deepseek_sdk\operator_import.json` (nom exact) puis :

```powershell
Invoke-RestMethod http://127.0.0.1:8777/api/integrations/deepseek-harness/pilot | ConvertTo-Json -Depth 8
```

Dans l'onglet **DeepSeek Harness**, clique **Relire le reçu de la VM**. Tu verras les informations *déclarées* : version SDK, modèle, nombre d'appels d'outils, correctif observé, SHA256 du reçu. Le serveur ne réexécute pas DSH, n'importe aucune conversation et ne donne aucun outil à Qwen.

## D — Étape suivante : vrai registre de compétences sous Gateway

Le pilote confirme seulement qu'un agent DSH externe peut terminer une tâche fictive avec son propre runtime. Les noms de plugins/outils et les permissions effectives **ne sont pas inspectés en V8**. Après validation humaine du pilote, la phase suivante doit :

1. Interroger, à travers la version SDK effectivement épinglée, les outils/plugins proposés par le **profil VM** ; n'utiliser une API publique documentée ou, à défaut, un plugin Cordis d'inventaire explicitement audité.
2. Signer/hasher un manifeste externe `capability_id / version / provenance / safety_class / allowed_inputs / required_approval / isolation_id` ; aucun outil ne devient « connected » sur simple déclaration de l'agent.
3. Ajouter un adaptateur Gateway HEX autorisant d'abord **une seule tâche de développement sur un workspace temporaire**, avec confirmation par action, comparaison diff, limites de coûts, logs et kill switch **VM**, et refus de sortie automatique vers le vrai repo.
4. Rejouer dans CanonicalSpine uniquement les observations indépendamment examinées, et non les commandes ou les affirmations de succès du modèle.
5. Comparer quatre bras : Ollama seul, HEX sans DSH, DSH seul, HEX+DSH ; qualité mesurée et régression sécurité obligatoire.

**Critère concret :** le moteur DSH termine réellement le correctif sur la VM, le résultat est inspectable depuis V8, les journaux ne contiennent aucune activité inattendue; seulement ensuite démarrer le Gateway V9. Aucun merge automatique sur `main`.
