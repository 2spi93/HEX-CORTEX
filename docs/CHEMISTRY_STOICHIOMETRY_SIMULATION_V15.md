# HEX-CORTEX V15 — ChemistryCell : calcul moléculaire et simulation stœchiométrique

## Mission

HEX-CORTEX ne doit pas se limiter au développement logiciel. Après les
MathCell (V13) et PhysicsCell (V14), V15 apporte un **organe scientifique
réellement calculant** pour la composition atomique et la stœchiométrie.

Le principe est inspiré des lois de conservation observées dans le monde
physique : dans un système fermé et pour une réaction **sans transformation
nucléaire**, les atomes de chaque élément doivent être conservés.

**ATTENTION :** connaître la formule d'une molécule et équilibrer une
équation n'établit **ni la réalité de la réaction**, ni sa cinétique,
son énergie libre, son rendement ni sa sûreté. Le logiciel n'est pas un
simulateur de chimie moléculaire et n'autorise aucune expérience physique.

## Capacités calculantes (stdlib Python sans modèle IA)

`src/hex_cortex/core/cortex_chemistry_cell_v15.py` :

- lecture strictement bornée de formules neutres basiques, exemple
  `H2O`, `CO2`, `CH4`, `Ca(OH)2`, `Al2(SO4)3` ;
- 14 éléments explicitement pris en charge (H, C, N, O, Na, Cl,
  S, P, Mg, Ca, K, Fe, Al, Si), sans extrapolation hors table ;
- composition atomique exacte, groupes parenthésés bornés,
  coefficients positifs et conservation stricte de chaque élément ;
- calcul des coefficients stœchiométriques par réduction de matrice
  sur `fractions.Fraction`, plus relecture du bilan élément par élément ;
- refus des systèmes impossibles ou ambigus (nullité différente de 1)
  et des coefficients dépassant le budget ;
- masse molaire **conventionnelle arrondie** en g/mol à partir des
  valeurs IUPAC affichées et explicitement identifiées ;
- quantités de matière en mol comme fractions exactes ;
- simulation idéale du **réactif limitant**, avancement, produits,
  reliquats, inventaire des éléments et masse, tous revérifiés ;
- sortie structurée `CellResult`, hash de preuve, intégration au
  `CognitiveCircuit`, revue par recalcul et commande PowerShell.

Aucun `eval` ou `exec`, outil externe, réseau, GPU, Ollama, API payante,
pilote matériel ou appareil de laboratoire n'est utilisé.

## Exemples dans PowerShell

Installe les commandes après `git pull` :

```powershell
python -m pip install -e ".[dev]"
```

### 1. Équilibrer la formation de l'eau

```powershell
hexcortex-chemistry --reactant H2 --reactant O2 --product H2O --approve-simulate --pretty
```

Bilan exact : `2 H2 + O2 → 2 H2O`.

### 2. Simulation d'inventaire

```powershell
hexcortex-chemistry --reactant H2 --reactant O2 --product H2O --amount H2=3 --amount O2=1 --approve-simulate --pretty
```

Inventaire initial : **3 mol H₂** et **1 mol O₂**.

Simulation stœchiométrique **idéale** :
- O₂ limitant ;
- 2 mol H₂O comptabilisés ;
- 1 mol H₂ et 0 mol O₂ restants ;
- inventaire d'H et d'O rigoureusement inchangé avant/après ;
- masse calculée sur **la même table de poids arrondis** inchangée.

Ce résultat ne certifie ni déclenchement spontané ni 100 % de
rendement expérimental : le mode « conversion complète hypothétique »
est une hypothèse mathématique.

### 3. Combustion idéale du méthane

```powershell
hexcortex-chemistry --reactant CH4 --reactant O2 --product CO2 --product H2O --amount CH4=2 --amount O2=3 --approve-simulate --pretty
```

Bilan : `CH4 + 2 O2 → CO2 + 2 H2O`.

L'avancement calculé est **3/2 mol** : en comptabilité idéale,
`3/2 mol CO2`, `3 mol H2O`, `1/2 mol CH4` résiduels,
`0 mol O2`.

### 4. Parenthèses et groupes atomiques

```powershell
hexcortex-chemistry --reactant "Ca(OH)2" --reactant HCl --product CaCl2 --product H2O --approve-simulate --pretty
```

Bilan : `Ca(OH)2 + 2 HCl → CaCl2 + 2 H2O`.

## Simulation de régression : 507 états d'inventaire

Le test `test_bounded_simulation_grid_always_conserves_atoms_and_molar_mass`
parcourt **3 réactions × 13 quantités pour le premier réactif ×
13 quantités pour le second = 507 cas**, incluant des
inventaires nuls, des cas limitants et des excès.

À chaque cas, la simulation exige :
- conservation exacte des atomes élément par élément ;
- conservation du bilan massique calculé avec la table fixée ;
- absence de quantité de matière négative ;
- absence de toute action de laboratoire.

Ce test **ne constitue pas une validation physico-chimique externe**
des réactions, une simulation de dynamique moléculaire, ni une mesure
du taux de succès de l'IA.

## Provenance et limites de la base scientifique

Les références choisies sont :
- **IUPAC** — `Stoichiometry`, Gold Book, terminologie :
  https://goldbook.iupac.org/terms/view/S06026
- **IUPAC** — table des poids atomiques :
  https://iupac.qmul.ac.uk/AtWt/
- **NIST Chemistry WebBook** — dioxyde de carbone et sa masse
  moléculaire de référence :
  https://webbook.nist.gov/cgi/cbook.cgi?ID=C124389&Mask=8004

La valeur conventionnelle de `CO2` utilisée avec
C = 12.011 et O = 15.999 est **44.009 g/mol**.
La base NIST peut afficher une masse légèrement différente
(par ex. 44.0095) suivant la précision et les conventions ;
ce n'est **pas** une erreur du bilan atomique, mais un rappel
que ces poids représentent des approximations physiques.

La V15 ne prend pas en charge :
- les ions, charges, électrons, isotopes et équations redox ;
- les hydrates, état de phase, solvants et complexation ;
- toutes les molécules du tableau périodique ;
- plusieurs solutions indépendantes de bilan ;
- les réactions catalytiques, réversibles, d'équilibre ou cinétiques ;
- la température, pression, thermodynamique ou rendements réels ;
- les produits toxiques et l'autorisation d'expérimentation.

L'origine des nombres n'établit pas l'innocuité de leur usage :
**aucune action physique n'est autorisée** par ChemistryCell.

## Validation indépendante du reste du cortex

L'interface `chemistry_cell_result` fournit le résultat typé de la
cellule ; `verify_chemistry_cell_result` recalcule la stœchiométrie
et rejette les sorties altérées. Ces deux chemins **partagent le même
algorithme** : cette vérification ne prouve pas l'indépendance d'un
laboratoire ou d'une méthode scientifique distincte.

Les tests Windows/Ubuntu vérifient le calcul, les refus, le circuit,
la CLI et la grille des 507 simulations, sans modèle IA.

Le contrôle `hexcortex-readiness --pretty` inclut maintenant
`chemistry_exact_atoms_and_mass_conservation`. Le rapport
`hexcortex-release-audit --pretty` inventorie cette nouvelle brique.

## Suite : connaissance scientifique universelle

La prochaine étape structurante sera un **Scientific Knowledge Router**
reliant MathCell, PhysicsCell et ChemistryCell à des sources
scientifiques traçables, avec unités, qualité, versions et gestion
des contradictions. Il devra pouvoir dire « preuve insuffisante »,
plutôt que produire un résultat spéculatif.
