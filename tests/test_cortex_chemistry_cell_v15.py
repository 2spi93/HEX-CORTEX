"""ChemistryCell V15: known atom balances, mole simulations and hostile inputs."""
from __future__ import annotations

import json
from fractions import Fraction

import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_chemistry_cell_v15 import (
    ChemistryRefusal,
    _molar_mass,
    _parse_formula,
    chemistry_cell_result,
    run_chemistry,
    verify_chemistry_cell_result,
)
from hex_cortex.core.schemas import CellRole, CellSpec, Task


@pytest.mark.parametrize(("formula", "expected"), [
    ("H2O", {"H": 2, "O": 1}),
    ("CO2", {"C": 1, "O": 2}),
    ("CH4", {"C": 1, "H": 4}),
    ("Ca(OH)2", {"Ca": 1, "O": 2, "H": 2}),
    ("Al2(SO4)3", {"Al": 2, "S": 3, "O": 12}),
    ("Mg(OH)2", {"Mg": 1, "O": 2, "H": 2}),
    ("Fe2O3", {"Fe": 2, "O": 3}),
])
def test_formula_parsing_counts_are_exact(formula, expected):
    assert _parse_formula(formula) == expected


@pytest.mark.parametrize("formula", [
    "", "H0", "H01", "H1000", "(OH", "OH)", "Ca()2", "()",
    "Xy2", "H₂O", "H2O + H2", "h2o", "Fe3+", "Na.Cl",
    "2H2O", "(())", "Ca(OH)0", "H2O\n", "H2O)__import__(os)",
])
def test_formula_rejects_nonstandard_or_unsafe_syntax(formula):
    with pytest.raises(ChemistryRefusal):
        _parse_formula(formula)


@pytest.mark.parametrize(("reactants", "products", "coeff_r", "coeff_p"), [
    (["H2", "O2"], ["H2O"], [2, 1], [2]),
    (["CH4", "O2"], ["CO2", "H2O"], [1, 2], [1, 2]),
    (["Fe", "O2"], ["Fe2O3"], [4, 3], [2]),
    (["Ca(OH)2", "HCl"], ["CaCl2", "H2O"], [1, 2], [1, 2]),
    (["Al", "O2"], ["Al2O3"], [4, 3], [2]),
    (["Na", "Cl2"], ["NaCl"], [2, 1], [2]),
    (["N2", "H2"], ["NH3"], [1, 3], [2]),
])
def test_exact_bounded_balancing_known_cases(reactants, products, coeff_r, coeff_p):
    report = run_chemistry(reactants, products, approved=True)
    assert report["status"] == "verified_idealized_stoichiometry"
    assert [x["coefficient"] for x in report["balance"]["reactants"]] == coeff_r
    assert [x["coefficient"] for x in report["balance"]["products"]] == coeff_p
    assert report["atom_conservation_verified"] is True
    assert report["chemical_feasibility_certified"] is False
    assert report["simulation_executed"] is False
    assert report["laboratory_action_performed"] is False


def test_water_stoichiometry_limiting_reagent_and_mass_invariant():
    result = run_chemistry(
        ["H2", "O2"], ["H2O"],
        amounts_mol={"H2": "3", "O2": "1"}, approved=True,
    )
    assert result["status"] == "verified_idealized_stoichiometry"
    sim = result["simulation"]
    assert sim["extent_mol"] == "1"
    assert sim["limiting_reactants"] == ["O2"]
    assert sim["products_mol"] == {"H2O": "2"}
    assert sim["unreacted_mol"] == {"H2": "1", "O2": "0"}
    assert sim["element_inventory_conserved"] is True
    assert sim["mass_conserved_under_fixed_rounded_weights"] is True
    assert sim["real_world_yield_predicted"] is False


def test_simulate_methane_stoichiometry_ideal_complete_conversion():
    result = run_chemistry(
        ["CH4", "O2"], ["CO2", "H2O"],
        amounts_mol={"CH4": "2", "O2": "3"},
        approved=True,
    )
    assert result["status"] == "verified_idealized_stoichiometry"
    sim = result["simulation"]
    assert sim["extent_mol"] == "3/2"
    assert sim["limiting_reactants"] == ["O2"]
    assert sim["products_mol"] == {"CO2": "3/2", "H2O": "3"}
    assert sim["unreacted_mol"] == {"CH4": "1/2", "O2": "0"}
    assert sim["element_inventory_conserved"] is True


def test_zero_reactant_quantity_gives_zero_conversion():
    result = run_chemistry(
        ["H2", "O2"], ["H2O"],
        amounts_mol={"H2": "0", "O2": "7/2"},
        approved=True,
    )
    assert result["simulation"]["extent_mol"] == "0"
    assert result["simulation"]["products_mol"] == {"H2O": "0"}
    assert result["simulation"]["limiting_reactants"] == ["H2"]


def test_rounded_iupac_molar_masses_are_approximate_not_exact_truth():
    assert _molar_mass("H2O") == Fraction("18.015")
    assert _molar_mass("CO2") == Fraction("44.009")
    report = run_chemistry(["C", "O2"], ["CO2"], approved=True)
    assert report["molar_mass_g_per_mol_rounded_iupac"]["CO2"] == "44009/1000"
    assert "rounded" in report["reference"]
    assert report["chemical_feasibility_certified"] is False


def test_bounded_simulation_grid_always_conserves_atoms_and_molar_mass():
    # Systematically explore 13 x 13 reagent inventories for three reactions.
    cases = [
        (["H2", "O2"], ["H2O"]),
        (["CH4", "O2"], ["CO2", "H2O"]),
        (["Ca(OH)2", "HCl"], ["CaCl2", "H2O"]),
    ]
    count = 0
    for reactants, products in cases:
        for a in range(13):
            for b in range(13):
                report = run_chemistry(
                    reactants, products,
                    amounts_mol={reactants[0]: str(a), reactants[1]: str(b)},
                    approved=True,
                )
                assert report["status"] == "verified_idealized_stoichiometry"
                sim = report["simulation"]
                assert sim["element_inventory_conserved"] is True
                assert sim["mass_conserved_under_fixed_rounded_weights"] is True
                assert all(Fraction(v) >= 0 for v in sim["unreacted_mol"].values())
                assert all(Fraction(v) >= 0 for v in sim["products_mol"].values())
                assert report["laboratory_action_performed"] is False
                count += 1
    assert count == 507


@pytest.mark.parametrize(("reactants", "products", "inventory", "reason"), [
    (["H2", "O2"], ["H2O"], {"H2": "2"}, "chemistry_inventory_names_mismatch"),
    (["H2", "O2"], ["H2O"], {"H2": "-1", "O2": "1"}, "chemistry_amount_negative"),
    (["H2", "O2"], ["H2O"], {"H2": "1.5", "O2": "1"}, "chemistry_amount_invalid"),
    (["H2", "O2"], ["H2O"], {"H2": "__import__('os')", "O2": "1"}, "chemistry_amount_invalid"),
    (["H2", "O2"], ["H2O"], {"H2": "2**1000", "O2": "1"}, "chemistry_amount_invalid"),
    (["O2"], ["CO2"], None, "chemistry_underdetermined_or_inconsistent"),
    (["H2", "O2"], ["H2", "H2O"], None, "chemistry_duplicate_species"),
    (["C", "O2"], ["CO", "CO2"], None, "chemistry_underdetermined_or_inconsistent"),
])
def test_refuses_unsafe_ambiguous_or_inconsistent_cases(
    reactants, products, inventory, reason,
):
    report = run_chemistry(
        reactants, products, amounts_mol=inventory, approved=True,
    )
    assert report["status"] == "blocked"
    assert report["reason"] == reason
    assert report["simulation_executed"] is False


def test_simulation_requires_operator_approval():
    report = run_chemistry(
        ["H2", "O2"], ["H2O"],
        amounts_mol={"H2": "2", "O2": "1"},
    )
    assert report["reason"] == "chemistry_operator_approval_required"
    assert report["calculation_performed"] is False


def test_chemistry_cell_integrates_legacy_cognitive_circuit_without_action():
    task = Task(
        task_id="chemistry-test", content=json.dumps({
            "reactants": ["H2", "O2"], "products": ["H2O"],
            "amounts_mol": {"H2": "3", "O2": "1"},
        }),
        domain_hints=["chemistry"], risk=0.1, novelty=0.1, uncertainty=0.1,
    )
    cortex = CognitiveCircuit(CellRegistry([
        CellSpec(cell_id="chemistry", role=CellRole.CHEMISTRY, domains=["chemistry"])
    ]))
    checked = run_chemistry(
        ["H2", "O2"], ["H2O"],
        amounts_mol={"H2": "3", "O2": "1"}, approved=True,
    )
    result = cortex.run(
        task, approved=True,
        cell_handler=lambda cid, t: chemistry_cell_result(cid, t, approved=True),
        verify_evidence=lambda candidate: (
            candidate.task_id == task.task_id
            and candidate.payload == {
                "balance": checked["balance"], "simulation": checked["simulation"],
            }
            and candidate.evidence_refs == [
                "chemistry:stoichiometric:" + checked["equation_hash"]
            ]
        ),
    )
    assert result["status"] == "verified"
    assert cortex.spine.verify_integrity().ok
    assert task.content not in str(cortex.spine.events)
    original = chemistry_cell_result("chemistry", task, approved=True)
    assert verify_chemistry_cell_result(original, task.content)
    assert not verify_chemistry_cell_result(
        original.model_copy(update={"payload": {"balance": "tampered"}}),
        task.content,
    )


def test_malformed_chemistry_task_never_runs_any_calculation():
    with pytest.raises(ChemistryRefusal, match="chemistry_request_json_invalid"):
        chemistry_cell_result("chemistry", Task(content="{invalid"), approved=True)


def test_receipts_do_not_leak_injection_content():
    report = run_chemistry(
        ["H2", "__import__('secret')"], ["H2O"], approved=True,
    )
    assert report["status"] == "blocked"
    assert "__import__" not in json.dumps(report)
