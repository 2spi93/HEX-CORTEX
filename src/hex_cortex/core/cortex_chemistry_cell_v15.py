"""ChemistryCell V15: bounded formula parsing, exact atom balance and molar simulation.

This is idealized stoichiometric bookkeeping, NOT molecular dynamics,
reaction prediction, synthesis advice, or any laboratory/physical operation.
Rounded conventional atomic weights are IUPAC-sourced reference values
and MUST NOT be confused with exact isotope/sample molar masses.
No LLM, network, eval/exec, process launch, or device actuation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from fractions import Fraction
from functools import reduce

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact
from hex_cortex.core.schemas import CellResult, Task

# Conventional rounded atomic weights in g/mol (IUPAC published tables).
# These decimal representations are exact as software inputs, NOT physical truth.
# https://iupac.qmul.ac.uk/AtWt/
_ATOMIC_G_MOL: dict[str, str] = {
    "H": "1.008", "C": "12.011", "N": "14.007", "O": "15.999",
    "Na": "22.990", "Cl": "35.45", "S": "32.06", "P": "30.974",
    "Mg": "24.305", "Ca": "40.078", "K": "39.098", "Fe": "55.845",
    "Al": "26.982", "Si": "28.085",
}
_TOKENS = re.compile(r"[A-Z][a-z]?|[1-9][0-9]{0,2}|[()]")
_MAX_FORMULA_LENGTH = 96
_MAX_ATOMS_PER_FORMULA = 20_000
_MAX_SPECIES = 8
_MAX_COEFFICIENT = 10_000
_MAX_AMOUNT_BITS = 160


class ChemistryRefusal(ValueError):
    """Intentional fail-closed chemistry error without raw user data."""


def _parse_formula(formula: str) -> dict[str, int]:
    if not isinstance(formula, str) or not 1 <= len(formula) <= _MAX_FORMULA_LENGTH:
        raise ChemistryRefusal("chemistry_formula_length_invalid")
    pieces = _TOKENS.findall(formula)
    if not pieces or "".join(pieces) != formula:
        raise ChemistryRefusal("chemistry_formula_grammar_invalid")
    stack: list[Counter[str]] = [Counter()]
    prev = "start"
    for idx, part in enumerate(pieces):
        if part == "(":
            if len(stack) >= 7:
                raise ChemistryRefusal("chemistry_formula_depth_exceeded")
            stack.append(Counter())
            prev = "open"
        elif part == ")":
            if len(stack) <= 1 or prev in ("open", "start"):
                raise ChemistryRefusal("chemistry_formula_parentheses_invalid")
            group = stack.pop()
            if not group:
                raise ChemistryRefusal("chemistry_formula_group_empty")
            factor = 1
            if idx + 1 < len(pieces) and pieces[idx + 1].isdigit():
                factor = int(pieces[idx + 1])
            stack[-1].update({symbol: count * factor for symbol, count in group.items()})
            prev = "close"
        elif part.isdigit():
            if prev not in ("element", "close"):
                raise ChemistryRefusal("chemistry_formula_number_unattached")
            prev = "number"
        else:
            if part not in _ATOMIC_G_MOL:
                raise ChemistryRefusal("chemistry_element_not_in_allowlist")
            factor = 1
            if idx + 1 < len(pieces) and pieces[idx + 1].isdigit():
                factor = int(pieces[idx + 1])
            stack[-1][part] += factor
            prev = "element"
        if sum(stack[-1].values()) > _MAX_ATOMS_PER_FORMULA:
            raise ChemistryRefusal("chemistry_formula_atoms_budget_exceeded")
    if len(stack) != 1 or prev == "open":
        raise ChemistryRefusal("chemistry_formula_parentheses_invalid")
    counts = dict(sorted(stack[0].items()))
    if not counts or sum(counts.values()) > _MAX_ATOMS_PER_FORMULA:
        raise ChemistryRefusal("chemistry_formula_atoms_budget_exceeded")
    return counts


def _rational_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else str(value)


def _molar_mass(formula: str) -> Fraction:
    counts = _parse_formula(formula)
    return sum(
        (Fraction(_ATOMIC_G_MOL[symbol]) * number for symbol, number in counts.items()),
        Fraction(),
    )


def _validated_sides(reactants: object, products: object) -> tuple[list[str], list[str]]:
    if not isinstance(reactants, list) or not isinstance(products, list):
        raise ChemistryRefusal("chemistry_sides_must_be_lists")
    if not 1 <= len(reactants) <= 4 or not 1 <= len(products) <= 4:
        raise ChemistryRefusal("chemistry_sides_size_out_of_range")
    if len(reactants) + len(products) > _MAX_SPECIES:
        raise ChemistryRefusal("chemistry_species_budget_exceeded")
    if any(not isinstance(x, str) for x in [*reactants, *products]):
        raise ChemistryRefusal("chemistry_species_must_be_formulas")
    if len(set([*reactants, *products])) != len(reactants) + len(products):
        raise ChemistryRefusal("chemistry_duplicate_species")
    for item in [*reactants, *products]:
        _parse_formula(item)
    return reactants, products


def _integer_coefficients(matrix: list[list[int]]) -> list[int]:
    """RREF over rationals, require a single all-positive integer null vector."""
    rows = [[Fraction(value) for value in row] for row in matrix]
    n = len(rows[0])
    pivots: list[int] = []
    row_index = 0
    for column in range(n):
        nonzero = next((i for i in range(row_index, len(rows))
                        if rows[i][column] != 0), None)
        if nonzero is None:
            continue
        rows[row_index], rows[nonzero] = rows[nonzero], rows[row_index]
        divisor = rows[row_index][column]
        rows[row_index] = [value / divisor for value in rows[row_index]]
        for r in range(len(rows)):
            if r != row_index and rows[r][column]:
                factor = rows[r][column]
                rows[r] = [
                    a - factor * b for a, b in zip(
                        rows[r], rows[row_index], strict=True
                    )
                ]
        pivots.append(column)
        row_index += 1
        if row_index == len(rows):
            break
    free = [c for c in range(n) if c not in pivots]
    if len(free) != 1:
        raise ChemistryRefusal("chemistry_underdetermined_or_inconsistent")
    candidate = [Fraction() for _ in range(n)]
    candidate[free[0]] = Fraction(1)
    for i, pivot in enumerate(pivots):
        candidate[pivot] = -rows[i][free[0]]
    if all(x < 0 for x in candidate):
        candidate = [-x for x in candidate]
    if any(x <= 0 for x in candidate):
        raise ChemistryRefusal("chemistry_no_positive_balance")
    lcm = math.lcm(*(x.denominator for x in candidate))
    ints = [int(x * lcm) for x in candidate]
    divisor = reduce(math.gcd, ints)
    result = [i // divisor for i in ints]
    if any(i > _MAX_COEFFICIENT for i in result):
        raise ChemistryRefusal("chemistry_coefficient_budget_exceeded")
    return result


def _balance(reactants: list[str], products: list[str]) -> tuple[list[int], list[int]]:
    formulas = [_parse_formula(s) for s in [*reactants, *products]]
    symbols = sorted({symbol for item in formulas for symbol in item})
    if len(symbols) > 14:
        raise ChemistryRefusal("chemistry_elements_budget_exceeded")
    split = len(reactants)
    matrix = [
        [item.get(symbol, 0) * (1 if j < split else -1)
         for j, item in enumerate(formulas)]
        for symbol in symbols
    ]
    coefficients = _integer_coefficients(matrix)
    for row in matrix:
        if sum(a * b for a, b in zip(row, coefficients, strict=True)):
            raise ChemistryRefusal("chemistry_atom_conservation_failed")
    return coefficients[:split], coefficients[split:]


def _amount(value: object) -> Fraction:
    if not isinstance(value, str) or len(value) > 128:
        raise ChemistryRefusal("chemistry_amount_invalid")
    proof = calculate_exact(value, approved=True)
    if proof.get("status") != "verified_exact_arithmetic":
        raise ChemistryRefusal("chemistry_amount_invalid")
    quantity = Fraction(int(proof["numerator"]), int(proof["denominator"]))
    if quantity < 0:
        raise ChemistryRefusal("chemistry_amount_negative")
    if max(quantity.numerator.bit_length(), quantity.denominator.bit_length()) > _MAX_AMOUNT_BITS:
        raise ChemistryRefusal("chemistry_amount_budget_exceeded")
    return quantity


def _simulation(
    reactants: list[str], products: list[str],
    rc: list[int], pc: list[int], inventory: dict[str, str],
) -> dict[str, object]:
    if not isinstance(inventory, dict) or set(inventory) != set(reactants):
        raise ChemistryRefusal("chemistry_inventory_names_mismatch")
    amounts = {s: _amount(inventory[s]) for s in reactants}
    extents = {s: amounts[s] / coefficient
               for s, coefficient in zip(reactants, rc, strict=True)}
    extent = min(extents.values())
    limiter = sorted(s for s, value in extents.items() if value == extent)
    remaining = {
        s: amounts[s] - extent * coefficient
        for s, coefficient in zip(reactants, rc, strict=True)
    }
    yields = {
        s: extent * coefficient
        for s, coefficient in zip(products, pc, strict=True)
    }
    # Independent element-by-element accounting of initial inventory vs
    # leftover reactants + products. The nominal balance alone is NOT enough.
    symbols = sorted({sym for s in [*reactants, *products] for sym in _parse_formula(s)})
    original = {
        symbol: sum(
            (amounts[s] * _parse_formula(s).get(symbol, 0) for s in reactants),
            Fraction(),
        )
        for symbol in symbols
    }
    final = {
        symbol: sum(
            (remaining[s] * _parse_formula(s).get(symbol, 0) for s in reactants),
            Fraction(),
        ) + sum(
            (yields[s] * _parse_formula(s).get(symbol, 0) for s in products),
            Fraction(),
        )
        for symbol in symbols
    }
    if original != final:
        raise ChemistryRefusal("chemistry_simulation_atom_conservation_failed")
    initial_mass = sum(
        (amounts[s] * _molar_mass(s) for s in reactants), Fraction()
    )
    final_mass = sum(
        (remaining[s] * _molar_mass(s) for s in reactants), Fraction()
    ) + sum((yields[s] * _molar_mass(s) for s in products), Fraction())
    if initial_mass != final_mass:
        raise ChemistryRefusal("chemistry_simulation_mass_conservation_failed")
    return {
        "simulation_type": "idealized_complete_stoichiometric_conversion",
        "extent_mol": _rational_text(extent),
        "limiting_reactants": limiter,
        "unreacted_mol": {s: _rational_text(x) for s, x in remaining.items()},
        "products_mol": {s: _rational_text(x) for s, x in yields.items()},
        "initial_mass_g_rounded_weights": _rational_text(initial_mass),
        "final_mass_g_rounded_weights": _rational_text(final_mass),
        "element_inventory_conserved": True,
        "mass_conserved_under_fixed_rounded_weights": True,
        "kinetics_or_reaction_feasibility_verified": False,
        "real_world_yield_predicted": False,
    }


def run_chemistry(
    reactants: object, products: object, *,
    amounts_mol: dict[str, str] | None = None, approved: bool = False,
) -> dict[str, object]:
    """Return a bounded, auditable idealized atom-balance or mole simulation."""
    def refuse(reason: str) -> dict[str, object]:
        return {
            "status": "blocked", "reason": reason, "calculation_performed": False,
            "simulation_executed": False, "model_called": False,
            "physical_action_authorized": False, "laboratory_action_performed": False,
        }
    if not approved:
        return refuse("chemistry_operator_approval_required")
    try:
        rs, ps = _validated_sides(reactants, products)
        rc, pc = _balance(rs, ps)
        molar_masses = {
            s: _rational_text(_molar_mass(s)) for s in [*rs, *ps]
        }
        simulation = (
            _simulation(rs, ps, rc, pc, amounts_mol)
            if amounts_mol is not None else None
        )
    except ChemistryRefusal as exc:
        return refuse(str(exc))
    except (OverflowError, ZeroDivisionError, ValueError, TypeError, RecursionError):
        return refuse("chemistry_computation_failed")
    balance = {
        "reactants": [{"formula": s, "coefficient": c}
                      for s, c in zip(rs, rc, strict=True)],
        "products": [{"formula": s, "coefficient": c}
                     for s, c in zip(ps, pc, strict=True)],
    }
    body = {"balance": balance, "simulation": simulation}
    return {
        "status": "verified_idealized_stoichiometry",
        "balance": balance,
        "molar_mass_g_per_mol_rounded_iupac": molar_masses,
        "reference": "IUPAC_conventional_rounded_weights_2023",
        "atom_conservation_verified": True,
        "equation_hash": hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "simulation": simulation,
        "calculation_performed": True,
        "simulation_executed": simulation is not None,
        "model_called": False,
        "physical_action_authorized": False,
        "laboratory_action_performed": False,
        "chemical_feasibility_certified": False,
    }


def chemistry_cell_result(cell_id: str, task: Task, *, approved: bool = False) -> CellResult:
    """Bridge JSON scientific request to the existing typed cognitive circuit."""
    if len(task.content) > 4096:
        raise ChemistryRefusal("chemistry_request_too_large")
    try:
        request = json.loads(task.content)
    except (ValueError, TypeError) as exc:
        raise ChemistryRefusal("chemistry_request_json_invalid") from exc
    if not isinstance(request, dict) or not {"reactants", "products"} <= set(request) or (
        set(request) - {"reactants", "products", "amounts_mol"}
    ):
        raise ChemistryRefusal("chemistry_request_shape_invalid")
    result = run_chemistry(
        request["reactants"], request["products"],
        amounts_mol=request.get("amounts_mol"), approved=approved,
    )
    if result["status"] != "verified_idealized_stoichiometry":
        raise ChemistryRefusal(str(result["reason"]))
    return CellResult(
        cell_id=cell_id, task_id=task.task_id,
        confidence=1.0, uncertainty=0.0,
        payload={"balance": result["balance"], "simulation": result["simulation"]},
        evidence_refs=["chemistry:stoichiometric:" + str(result["equation_hash"])],
    )
