# HEX-CORTEX V14 — PhysicsCell : unités SI et lois classiques vérifiées

## Résultat livré

V14 met en œuvre un **deuxième organe scientifique calculant**, après
MathCell : `cortex_physics_cell_v14.py` et la commande
`hexcortex-physics`.

L'inspiration provient des lois régulières de la nature et de
l'organisation des systèmes physiques, sans supposer qu'un calcul
connaît ou prédit automatiquement toutes les conditions du monde réel.

Le principe de sûreté est : **un nombre sans unité et sans domaine
de validité ne constitue pas une connaissance physique suffisante**.

## Exemples immédiatement utilisables sur Windows PowerShell

```powershell
python -m pip install -e ".[dev]"

# F = m × a : 3 kg × (2/3 m/s²) = 2 N
hexcortex-physics --law force --mass 3 --acceleration 2/3 --approve-calculate --pretty

# E = m v²/2 : 2 kg, 3 m/s → 9 J
hexcortex-physics --law kinetic_energy --mass 2 --speed 3 --approve-calculate --pretty

# v = distance / durée : 100 m / 8 s = 25/2 m/s
hexcortex-physics --law speed --distance 100 --duration 8 --approve-calculate --pretty
```

Les résultats comprennent le nombre rationnel exact, son unité,
la dimension SI à sept composantes, un hash du calcul et la mention
qu'aucune mesure physique réelle n'a été vérifiée.

### Lois disponibles

| Loi | Entrées SI | Résultat SI |
|---|---|---|
| force = masse × accélération | kg, m/s² | newton (N) |
| énergie cinétique = masse × vitesse² / 2 | kg, m/s | joule (J) |
| quantité de mouvement = masse × vitesse | kg, m/s | kg·m/s |
| vitesse = distance / durée | m, s | m/s |
| puissance = énergie / durée | J, s | watt (W) |
| masse volumique = masse / volume | kg, m³ | kg/m³ |

Chaque formule est calculée via `Fraction` et dotée d'un
contrôle de cohérence algébrique inverse (ou égalité réarrangée pour
l'énergie cinétique), ainsi que d'une vérification de la dimension
dérivée. Cela détecte les incohérences courantes mais **n'est pas
un oracle indépendant, une preuve de loi universelle ni une
simulation scientifique complète**.

## Limites intentionnelles

- Pas d'unité arbitraire, ni de conversion automatique :
  le formulaire de la loi fixe explicitement ses unités SI.
- Les nombres réels flottants tels que `1.25` sont refusés :
  utiliser les fractions exactes `5/4` pour cette version.
- Les masses/volumes/durées doivent être strictement positifs ;
  les vitesses et énergies sont non négatives dans les formules
  qui utilisent des grandeurs scalaires. Les hypothèses sont
  explicites et ne couvrent pas les conventions de signes
  de tous les systèmes physiques.
- Seules les équations classiques idéalisées listées sont
  disponibles. Les frottements, forces additionnelles,
  relativité, turbulence, thermodynamique réelle,
  incertitudes expérimentales et propriétés matérielles
  ne sont pas modélisés.
- Pas de modèle local, de requête cloud, de calcul
  scientifique lourd, d'actionneur, de réseau ou de
  générateur de code utilisé.
- Les données calculées ne peuvent pas commander un drone
  ou une machine réelle ; une supervision indépendante est nécessaire.

Sources normatives / institutionnelles :
- NIST/BIPM SI : https://www.nist.gov/pml/owm/metric-si/si-units
- NIST règles sur les dimensions :
  https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values

## Validation

Tests automatiques : chaque loi, ses dimensions exactes, requêtes
mal formées, injections, unités invalides, divisions par zéro,
limites des quantités et intégration au CortexCircuit.

Le contrôle `hexcortex-readiness --pretty` inclut désormais
`physics_si_exact_laws_and_unit_safety: true` si les tests
élémentaires sont valides.

Le prochain objectif scientifique est ChemistryCell avec références
moléculaires et stœchiométrie, puis un routeur
de connaissances vérifiables multi-domaines.
