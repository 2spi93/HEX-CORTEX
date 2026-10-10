"""Bounded PhysicsCell classical equations with NIST SI dimensional checks."""
from __future__ import annotations

import json

import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_physics_cell_v14 import (
    PhysicsRefusal,
    calculate_physics,
    physics_cell_result,
)
from hex_cortex.core.schemas import CellRole, CellSpec, Task


def q(value: str, unit: str) -> dict[str, str]:
    return {"value": value, "unit": unit}


@pytest.mark.parametrize(("law", "inputs", "num", "den", "unit", "dims"), [
    ("force", {"mass": q("3", "kg"), "acceleration": q("2/3", "m/s^2")},
     2, 1, "N", [1, 1, -2, 0, 0, 0, 0]),
    ("kinetic_energy", {"mass": q("2", "kg"), "speed": q("3", "m/s")},
     9, 1, "J", [2, 1, -2, 0, 0, 0, 0]),
    ("momentum", {"mass": q("3", "kg"), "speed": q("2/3", "m/s")},
     2, 1, "kg*m/s", [1, 1, -1, 0, 0, 0, 0]),
    ("speed", {"distance": q("100", "m"), "duration": q("8", "s")},
     25, 2, "m/s", [1, 0, -1, 0, 0, 0, 0]),
    ("power", {"energy": q("600", "J"), "duration": q("30", "s")},
     20, 1, "W", [2, 1, -3, 0, 0, 0, 0]),
    ("density", {"mass": q("3", "kg"), "volume": q("2", "m^3")},
     3, 2, "kg/m^3", [-3, 1, 0, 0, 0, 0, 0]),
])
def test_classical_laws_with_exact_si_dimensions(
    law, inputs, num, den, unit, dims,
):
    report = calculate_physics(law, inputs, approved=True)
    assert report["status"] == "verified_classical_formula"
    assert (report["numerator"], report["denominator"], report["unit"]) == (num, den, unit)
    assert report["si_dimensions"] == dims
    assert report["reversible_identity_checked"] is True
    assert report["physical_world_measurement_verified"] is False
    assert report["hardware_actuation_allowed"] is False


@pytest.mark.parametrize(("law", "inputs", "reason"), [
    ("force", {"mass": q("3", "m"), "acceleration": q("4", "m/s^2")},
     "physics_input_unit_mismatch"),
    ("speed", {"distance": q("10", "m"), "duration": q("0", "s")},
     "physics_positive_quantity_required"),
    ("density", {"mass": q("-1", "kg"), "volume": q("2", "m^3")},
     "physics_positive_quantity_required"),
    ("kinetic_energy", {"mass": q("2", "kg"), "speed": q("-3", "m/s")},
     "physics_nonnegative_quantity_required"),
    ("force", {"mass": q('open("c")', "kg"), "acceleration": q("2", "m/s^2")},
     "physics_numeric_expression_rejected"),
    ("force", {"mass": q("3", "stone"), "acceleration": q("4", "m/s^2")},
     "physics_unit_not_allowlisted"),
    ("force", {"mass": q("3", "kg")}, "physics_operand_names_mismatch"),
    ("freefall", {"mass": q("3", "kg")}, "physics_law_not_supported"),
])
def test_scientific_units_misuse_and_code_injection_refused(law, inputs, reason):
    report = calculate_physics(law, inputs, approved=True)
    assert report["status"] == "blocked"
    assert report["reason"] == reason
    assert report["calculation_performed"] is False


def test_physics_requires_operator_approval():
    denied = calculate_physics(
        "force", {"mass": q("5", "kg"), "acceleration": q("2", "m/s^2")}
    )
    assert denied["reason"] == "physics_operator_approval_required"
    assert denied["calculation_performed"] is False


def test_idealized_physics_cell_integrates_into_existing_router():
    request = {
        "law": "force",
        "inputs": {"mass": q("6", "kg"), "acceleration": q("1/3", "m/s^2")}
    }
    task = Task(task_id="physics-1", content=json.dumps(request),
                domain_hints=["physics"], risk=0.1, novelty=0.1, uncertainty=0.1)
    circuit = CognitiveCircuit(CellRegistry([
        CellSpec(cell_id="physics", role=CellRole.PHYSICS, domains=["physics"])
    ]))
    report = circuit.run(
        task, approved=True,
        cell_handler=lambda cid, t: physics_cell_result(cid, t, approved=True),
        verify_evidence=lambda row: row.payload == {
            "law": "force", "numerator": 2, "denominator": 1,
            "unit": "N", "si_dimensions": [1, 1, -2, 0, 0, 0, 0],
        },
    )
    assert report["status"] == "verified"
    assert circuit.spine.verify_integrity().ok
    assert task.content not in str(circuit.spine.events)


def test_physics_cell_malformed_json_refused_not_executed():
    with pytest.raises(PhysicsRefusal, match="physics_request_json_invalid"):
        physics_cell_result("physics", Task(content="import os"), approved=True)


def test_physics_report_does_not_reveal_raw_user_expression():
    inputs = {"mass": q("(100+23)", "kg"), "acceleration": q("1/3", "m/s^2")}
    report = calculate_physics("force", inputs, approved=True)
    assert report["status"] == "verified_classical_formula"
    assert "(100+23)" not in json.dumps(report)
    assert len(report["source_inputs_sha256"]) == 64
