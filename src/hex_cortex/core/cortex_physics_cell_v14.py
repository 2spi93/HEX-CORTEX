"""PhysicsCell V14: exact rational, dimensionally checked classical equations.

The laws are narrowly defined mathematical models, not simulation of a
real device or scientific certification. No dynamic Python execution,
model inference, arbitrary SI conversion, network or hardware interface.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact
from hex_cortex.core.schemas import CellResult, Task

# SI base dimension vector (L, M, T, electric current, temperature,
# amount of substance, luminous intensity) per BIPM/NIST SI conventions.
Dims = tuple[int, int, int, int, int, int, int]
_ZERO: Dims = (0, 0, 0, 0, 0, 0, 0)
_UNITS: dict[str, Dims] = {
    "1": _ZERO,
    "m": (1, 0, 0, 0, 0, 0, 0),
    "kg": (0, 1, 0, 0, 0, 0, 0),
    "s": (0, 0, 1, 0, 0, 0, 0),
    "m/s": (1, 0, -1, 0, 0, 0, 0),
    "m/s^2": (1, 0, -2, 0, 0, 0, 0),
    "m^3": (3, 0, 0, 0, 0, 0, 0),
    "kg/m^3": (-3, 1, 0, 0, 0, 0, 0),
    "N": (1, 1, -2, 0, 0, 0, 0),
    "J": (2, 1, -2, 0, 0, 0, 0),
    "W": (2, 1, -3, 0, 0, 0, 0),
}
_LAWS: dict[str, tuple[dict[str, str], str]] = {
    "force": ({"mass": "kg", "acceleration": "m/s^2"}, "N"),
    "kinetic_energy": ({"mass": "kg", "speed": "m/s"}, "J"),
    "momentum": ({"mass": "kg", "speed": "m/s"}, "kg*m/s"),
    "speed": ({"distance": "m", "duration": "s"}, "m/s"),
    "power": ({"energy": "J", "duration": "s"}, "W"),
    "density": ({"mass": "kg", "volume": "m^3"}, "kg/m^3"),
}
_UNITS["kg*m/s"] = (1, 1, -1, 0, 0, 0, 0)
_POSITIVE = {"mass", "duration", "volume"}
_NONNEGATIVE = {"speed", "distance", "energy"}
_MAX_BITS = 256


class PhysicsRefusal(ValueError):
    """Clear error codes without embedding private user input."""


def _bounded(value: Fraction) -> Fraction:
    if value.numerator.bit_length() > _MAX_BITS or value.denominator.bit_length() > _MAX_BITS:
        raise PhysicsRefusal("physics_numeric_budget_exceeded")
    return value


@dataclass(frozen=True)
class Quantity:
    magnitude: Fraction
    dimensions: Dims

    def multiply(self, other: Quantity) -> Quantity:
        dims: Dims = tuple(a + b for a, b in zip(
            self.dimensions, other.dimensions, strict=True
        ))
        return Quantity(_bounded(self.magnitude * other.magnitude), dims)

    def divide(self, other: Quantity) -> Quantity:
        if other.magnitude == 0:
            raise PhysicsRefusal("physics_division_by_zero")
        dims: Dims = tuple(a - b for a, b in zip(
            self.dimensions, other.dimensions, strict=True
        ))
        return Quantity(_bounded(self.magnitude / other.magnitude), dims)

    def square(self) -> Quantity:
        dims: Dims = tuple(2 * d for d in self.dimensions)
        return Quantity(_bounded(self.magnitude ** 2), dims)

    def half(self) -> Quantity:
        return Quantity(_bounded(self.magnitude / 2), self.dimensions)


def _parse_operand(spec: Any, expected_unit: str, *, name: str) -> Quantity:
    if not isinstance(spec, dict) or set(spec) != {"value", "unit"}:
        raise PhysicsRefusal("physics_input_shape_invalid")
    unit = spec["unit"]
    if not isinstance(unit, str) or unit not in _UNITS:
        raise PhysicsRefusal("physics_unit_not_allowlisted")
    if unit != expected_unit:
        raise PhysicsRefusal("physics_input_unit_mismatch")
    expression = spec["value"]
    if not isinstance(expression, str):
        raise PhysicsRefusal("physics_numeric_input_invalid")
    proof = calculate_exact(expression, approved=True)
    if proof["status"] != "verified_exact_arithmetic":
        raise PhysicsRefusal("physics_numeric_expression_rejected")
    q = Quantity(
        Fraction(int(proof["numerator"]), int(proof["denominator"])),
        _UNITS[unit],
    )
    if name in _POSITIVE and q.magnitude <= 0:
        raise PhysicsRefusal("physics_positive_quantity_required")
    if name in _NONNEGATIVE and q.magnitude < 0:
        raise PhysicsRefusal("physics_nonnegative_quantity_required")
    return q


def calculate_physics(
    law: str,
    inputs: dict[str, dict[str, str]],
    *,
    approved: bool = False,
) -> dict[str, object]:
    """Calculate one explicit classical formula and verify SI dimensions."""
    def blocked(reason: str) -> dict[str, object]:
        return {
            "status": "blocked", "reason": reason,
            "calculation_performed": False,
            "hardware_actuation_allowed": False,
            "model_used": False,
        }

    if not approved:
        return blocked("physics_operator_approval_required")
    if not isinstance(law, str) or law not in _LAWS:
        return blocked("physics_law_not_supported")
    if not isinstance(inputs, dict) or set(inputs) != set(_LAWS[law][0]):
        return blocked("physics_operand_names_mismatch")
    expected_units, output_unit = _LAWS[law]
    try:
        q = {
            name: _parse_operand(inputs[name], unit, name=name)
            for name, unit in expected_units.items()
        }
        if law == "force":
            result = q["mass"].multiply(q["acceleration"])
            inverse = result.divide(q["mass"]) == q["acceleration"]
        elif law == "kinetic_energy":
            result = q["mass"].multiply(q["speed"].square()).half()
            inverse = (
                result.magnitude * 2
                == q["mass"].magnitude * q["speed"].magnitude ** 2
            )
        elif law == "momentum":
            result = q["mass"].multiply(q["speed"])
            inverse = result.divide(q["mass"]) == q["speed"]
        elif law == "speed":
            result = q["distance"].divide(q["duration"])
            inverse = result.multiply(q["duration"]) == q["distance"]
        elif law == "power":
            result = q["energy"].divide(q["duration"])
            inverse = result.multiply(q["duration"]) == q["energy"]
        else:
            result = q["mass"].divide(q["volume"])
            inverse = result.multiply(q["volume"]) == q["mass"]

        if result.dimensions != _UNITS[output_unit]:
            raise PhysicsRefusal("physics_dimension_check_failed")
        if not inverse:
            raise PhysicsRefusal("physics_inverse_invariant_failed")
    except PhysicsRefusal as exc:
        return blocked(str(exc))
    except (OverflowError, ValueError, ZeroDivisionError):
        return blocked("physics_arithmetic_failed")
    source = {
        "law": law, "inputs": inputs, "output": {
            "numerator": result.magnitude.numerator,
            "denominator": result.magnitude.denominator, "unit": output_unit
        },
    }
    return {
        "status": "verified_classical_formula",
        "law": law,
        "numerator": result.magnitude.numerator,
        "denominator": result.magnitude.denominator,
        "unit": output_unit,
        "si_dimensions": list(result.dimensions),
        "reversible_identity_checked": True,
        "source_inputs_sha256": hashlib.sha256(
            json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "physical_world_measurement_verified": False,
        "scientific_model_domain": "idealized_classical",
        "hardware_actuation_allowed": False,
        "calculation_performed": True,
        "model_used": False,
    }


def physics_cell_result(
    cell_id: str, task: Task, *, approved: bool = False,
) -> CellResult:
    """Use a bounded JSON law envelope as a typed cell request."""
    if len(task.content) > 2048:
        raise PhysicsRefusal("physics_input_too_long")
    try:
        request = json.loads(task.content)
    except (ValueError, TypeError) as exc:
        raise PhysicsRefusal("physics_request_json_invalid") from exc
    if not isinstance(request, dict) or set(request) != {"law", "inputs"}:
        raise PhysicsRefusal("physics_request_shape_invalid")
    report = calculate_physics(request["law"], request["inputs"], approved=approved)
    if report["status"] != "verified_classical_formula":
        raise PhysicsRefusal(str(report.get("reason", "physics_invalid")))
    return CellResult(
        task_id=task.task_id, cell_id=cell_id,
        confidence=1.0, uncertainty=0.0,
        payload={
            "law": report["law"], "numerator": report["numerator"],
            "denominator": report["denominator"], "unit": report["unit"],
            "si_dimensions": report["si_dimensions"],
        },
        evidence_refs=["physics:idealized:" + str(report["source_inputs_sha256"])],
    )
