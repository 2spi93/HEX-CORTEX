"""One actual CognitiveCircuit for three separately implemented science cells."""
from __future__ import annotations

import json

import pytest

from hex_cortex.core.cortex_verified_science_circuit import (
    run_verified_science_circuit,
)


@pytest.mark.parametrize(("domain", "request", "check"), [
    ("mathematics", "127*413", {"numerator": 52451, "denominator": 1}),
    ("physics", json.dumps({
        "law": "force", "inputs": {
            "mass": {"value": "2", "unit": "kg"},
            "acceleration": {"value": "3", "unit": "m/s^2"},
        }
    }), {"numerator": 6, "denominator": 1, "unit": "N"}),
])
def test_scientific_cells_run_through_real_router_and_clock(
    domain: str, request: str, check: dict[str, object]
) -> None:
    result = run_verified_science_circuit(
        domain=domain, task_id="science-task", request=request, approved=True
    )
    assert result["status"] == "verified_science_circuit"
    assert result["circuit_status"] == "verified"
    assert result["verified_cell_count"] == 1
    assert result["spine_integrity_ok"] is True
    assert result["spine_event_count"] > 0
    assert result["evidence_refs"]
    assert all(result["verified_payload"][key] == value for key, value in check.items())
    assert result["model_called"] is False
    assert result["physical_action_authorized"] is False


def test_chemistry_cell_existing_balancer_is_routed() -> None:
    request = json.dumps({"reactants": ["H2", "O2"], "products": ["H2O"]})
    result = run_verified_science_circuit(
        domain="chemistry", task_id="science-task", request=request, approved=True
    )
    assert result["status"] == "verified_science_circuit"
    assert result["verified_cell_count"] == 1
    assert result["spine_integrity_ok"] is True
    assert result["verified_payload"]["balance"]["reactants"] == [
        {"formula": "H2", "coefficient": 2},
        {"formula": "O2", "coefficient": 1},
    ]
    assert result["verified_payload"]["balance"]["products"] == [
        {"formula": "H2O", "coefficient": 2},
    ]


def test_missing_permission_never_routes_or_writes() -> None:
    result = run_verified_science_circuit(
        domain="mathematics", task_id="no", request="17*23"
    )
    assert result["status"] == "blocked"
    assert result["spine_event_count"] == 0


def test_failing_verifier_blocks_without_exposing_raw_input() -> None:
    result = run_verified_science_circuit(
        domain="mathematics", task_id="wrong", request="17*23", approved=True,
        verifier_override=lambda _candidate: False,
    )
    assert result["status"] == "blocked"
    assert result["verified_payload"] is None
    assert not result["evidence_refs"]
    assert result["spine_integrity_ok"] is True


@pytest.mark.parametrize(("domain", "request"), [
    ("mathematics", "__import__('os')"),
    ("physics", "{}"),
    ("chemistry", "{}"),
])
def test_reject_invalid_scientific_request_without_evidence(
    domain: str, request: str
) -> None:
    result = run_verified_science_circuit(
        domain=domain, task_id="bad", request=request, approved=True
    )
    assert result["status"] == "blocked"
    assert result["verified_payload"] is None
    assert result["evidence_refs"] == []


def test_unknown_domain_is_never_inferred() -> None:
    with pytest.raises(ValueError, match="unsupported_or_empty_science_request"):
        run_verified_science_circuit(
            domain="robotics", task_id="bad", request="move 5m", approved=True
        )
