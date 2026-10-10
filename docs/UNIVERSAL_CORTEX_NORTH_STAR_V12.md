# HEX-CORTEX V12 — North Star : Cognitive Exoskeleton Universel

Date : 10 octobre 2026. Ce document rétablit et explicite la vision
fondatrice du propriétaire, qui **prévaut** sur les descriptions
historiques trop étroites « coding-only ».

## 1. Identité (non négociable)

HEX-CORTEX est une **armure cognitive universelle**, comparable
conceptuellement à l'armure de Tony Stark autour d'un cerveau humain.
Le cerveau est un modèle IA **interchangeable** ; HEX-CORTEX lui apporte
les organes cognitifs, la connaissance calculable, les vérificateurs,
les outils, les capteurs, la mémoire, les compétences et les interfaces
d'intervention. Tout modèle relié à HEX-CORTEX doit pouvoir *potentiellement*
améliorer ses capacités — mais un gain réel doit être mesuré, jamais
annoncé sans comparaison contrôlée.

Ne pas confondre l'armure et son premier terrain d'essai :
**le codage n'est qu'une application**, choisie pour ses tests objectifs.

## 2. La connaissance du monde

Ce ne doit pas être un prompt monolithique disant « connais tout ».

- **Mathématiques :** calcul exact et numérique, algèbre, optimisation,
  logique formelle, solveurs et preuve indépendante.
- **Physique :** unités et dimensions, mécanique, énergie, conservation,
  dynamiques, limites et propagation des incertitudes.
- **Chimie et molécules :** composition, structures, masses et
  stœchiométrie, propriétés, jeux de données identifiés ; ne jamais
  confondre estimation et observation expérimentale.
- **Biologie :** biologie moléculaire, systèmes et organismes ;
  preuves, qualité des données et limites biologiques.
- **Sciences et ingénierie :** matériaux, électronique, astronomie,
  statistiques, causalité, expériences et modèles multi-échelles.
- **Connaissances humaines :** publications, textes, bases de données,
  normes et autres ressources traçables, actualisables et autorisées.
- **World model :** état observé → action candidate → prédiction →
  observation suivante → résidu mesuré → apprentissage, sans
  attribuer aux poids d'un modèle une vérité scientifique présumée.

Le **World Knowledge Layer** doit disposer d'une hiérarchie de preuves :
(1) calcul vérifié ou mesure calibrée, (2) expérience reproductible,
(3) simulation validée sur son domaine, (4) source primaire indépendante,
(5) avis du modèle, (6) hypothèse à tester.

Le système doit conserver source, version, date, dimensions/unités,
incertitude, champ de validité et contre-exemples. La taille d'un
réservoir d'informations n'est pas l'intelligence : **retrouver peu,
calculer juste et vérifier indépendamment** est la priorité.

## 3. L'armure autour de tout cerveau

Le Cognitive Genome définit les règles stables, les signatures de
compétence, l'ontologie des erreurs et les droits d'action. Le
phénotype adaptatif choisit le cerveau, les cellules, les sources,
le budget, les outils et les procédures appropriés.

Le mécanisme d'amplification à démontrer :

```text
Modèle interchangeable
  + Router sparse
  + Math/Physics/Chemistry/Biology/Engineering/Code Cells
  + Memory/Skill Graph/Anti-Forgetting
  + Evidence/Scientific Verifiers
  + World Model/Prediction/Residual Ledger
  + Planner/Simulators/Gateway
  → meilleure réponse ou tâche plus complexe ?
  → mesure empirique par rapport au même modèle sans HEX-CORTEX
```

L'amélioration attendue dépend du problème. Certaines tâches peuvent
ne pas progresser, voire empirer si le routage, les outils ou les
sources sont mauvais. **Pas de revendication x2, x10 ou "plus puissant
que tout autre modèle" sans expériences.**

## 4. Supports et incarnation

HEX-CORTEX doit pouvoir être hébergé ou connecté à différents supports
avec les **mêmes contrats cognitifs**, mais des garde-fous distincts :

| Surface | Exemples visés | Contrat nécessaire |
|---|---|---|
| Applications | VS Code, outils métiers, projets logiciels | API/outils autorisés, versions, tests, revue et rollback |
| Ordinateur local | Windows, Linux | permissions, sandbox, stockage et journaux |
| Simulation | Modèle numérique d'une machine ou d'un drone | état, unités, dynamique, contraintes, comparaison réel/simulé |
| Capteurs | Caméra, inertiel, télémétrie, objets connectés | origine des observations, calibration, qualité et horodatage |
| Robot | Manipulateur, robot mobile | supervision matérielle indépendante, limites, arrêt d'urgence |
| Drone | Plateforme aérienne | simulation d'abord, géorestrictions, état, sûreté et pilote autorisé |
| Autre dispositif | Tout système doté d'un adaptateur contractuel | évaluation des dangers, sûreté indépendante et permissions |

**Règle absolue : le LLM ne doit pas commander directement des
moteurs, effecteurs ou appareils dangereux.**

`Physical Device Gateway` futur : boucle
`observe → estimer → planifier → simuler → vérifier → autoriser → exécuter
par contrôleur spécialisé → mesurer → arrêter/rollback selon sûreté`.

Les commandes physiques exigent un responsable humain et des mécanismes
indépendants du modèle : contrôleur d'état, watchdog, interverrouillages,
arrêt d'urgence, limitations physiques, authentification, télémetrie,
géorestrictions lorsque pertinentes et tests hors ligne. Un mode
`actuate` dans le manifeste V12 est toujours bloqué.

## 5. Implémentation réellement présente en octobre 2026

- **Présent et vérifié dans les tests :** Router, CellRegistry,
  Workspace, CognitiveClock, CanonicalSpine, Gateway, apprentissage
  contrôlé, Replay, Harness, Brain cloud facultatif (API réelle non testée).
- **Présent comme prototype ou contrat :** world model, adaptateur
  matériel `cortex_hardware_adapter.py`, rails média/perception,
  vision et planification ; pas équivalent à un robot opérationnel.
- **Ajouté en V12 :** inventaire typé des domaines/surfaces et plan
  consultatif `core/universal_capabilities_v12.py`; évaluation
  de sources scientifiques sous forme de reçus sans fausse
  certification et refus systématique de l'action physique.
- **À construire :** adaptateurs scientifiques exécutables,
  unités fortes, solveurs, moteurs de chimie/bio, acquisition de
  données sourcées, ROS 2, simulateur et pilotes adaptés,
  expérimentations trans-domaines, calibration et sécurité réelle.
- **Recherche différée :** entraînement CR-JEPA, modèles de monde
  scientifiques multimodaux, LoRA et calcul scientifique lourd.

Les huit entrées du catalogue V12 sont **des contrats déclaratifs**,
pas huit experts artificiels fonctionnels. La présence d'un adaptateur
ne certifie pas la capacité sur un drone ou une vraie molécule.

## 6. Compatibilité avec le PC actuel

Aucun modèle local ni serveur HEX-CORTEX ne doit être nécessaire
pour bâtir les contrats et tester le noyau. Cerveaux cloud optionnels,
données sensibles non transmises sans consentement. Tous les
contrats V12 se testent à l'aide de Python, Pydantic et pytest.

## 7. Feuille de route d'amplification universelle

1. **V12 :** corriger la mission et définir les domaines et supports,
   les schémas, la preuve, les permissions et l'interdiction de l'actuation.
2. **MathCell de production :** solveurs standard à versions épinglées,
   exactitude, unités, références de calcul, sans exécution de code IA.
3. **PhysicsCell :** dimensionnement, contraintes/conservation,
   simulation simple et validation contre références connues.
4. **ChemistryCell :** références moléculaires, schémas, unités,
   calculs reproductibles et provenance indépendante.
5. **Universal Knowledge Router :** retriever sélectif de sources
   scientifiques avec droits d'accès, qualité et horodatage.
6. **Body Adapter Layer :** simulateur seulement pour les drones/robots
   avant toute autre forme d'autorisation.
7. **Amplification Evaluation :** même modèle IA, mêmes problèmes,
   sans/avec HEX-CORTEX, jeux de données non vus, ablations de
   chaque organe, coût/latence/erreurs, validation indépendante.

### Références d'écosystème pour futures interfaces

- <https://gazebosim.org/docs/harmonic/ros2_integration/> :
  bridge ROS 2 ↔ Gazebo, simulations et messages.
- <https://mavlink.io/en/services/command.html> : protocole de
  commandes MAVLink et acquittement, **aucun pilote activé en V12**.

Aucun de ces protocoles n'est une garantie de sûreté en soi.

## 8. Critère définitif de différenciation

La vision réussira quand une **même IA**, assistée par HEX-CORTEX,
démontrera sur des situations non vues qu'elle :

- mobilise des lois mathématiques et scientifiques fiables ;
- combine les connaissances de disciplines différentes ;
- sait reconnaître et corriger ses erreurs plutôt que les oublier ;
- réutilise des compétences vérifiées avec moins de fautes ;
- peut changer de cerveau et de cible (logiciel, simulation,
  appareil) sans refaire toute son architecture ;
- garde des limites de sécurité appropriées à chaque support.

Ce résultat sera une mesure de capacité, et non une déclaration de marketing.
