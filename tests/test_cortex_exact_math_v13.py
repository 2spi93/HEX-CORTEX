"""Real exact arithmetic organ and hostile-input regression coverage."""
from __future__ import annotations

from fractions import Fraction

import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_exact_math_v13 import (
    MathRefusal,
    calculate_exact,
    math_cell_result,
    verify_math_cell_result,
)
from hex_cortex.core.schemas import CellRole, CellSpec, Task


@pytest.mark.parametrize(("expression", "expected"), [
    ("1 / 3 + 1 / 6", Fraction(1, 2)),
    ("(2 + 3) * 7", Fraction(35)),
    ("2 ** 10", Fraction(1024)),
    ("(-2) ** 3", Fraction(-8)),
    ("-2 ** 2", Fraction(-4)),
    ("5 / (2 + 3)", Fraction(1)),
    ("(-3 / 2) ** -2", Fraction(4, 9)),
    ("1 / 3 + 1 / 7 + 1 / 11", Fraction(1, 3) + Fraction(1, 7) + Fraction(1, 11)),
])
def test_exact_math_true_rational_no_roundoff(expression: str, expected: Fraction):
    result = calculate_exact(expression, approved=True)
    assert result["status"] == "verified_exact_arithmetic"
    assert (result["numerator"], result["denominator"]) == (
        expected.numerator, expected.denominator,
    )
    assert result["independent_traversal_agrees"] is True
    assert result["model_used"] is False
    assert result["code_executed"] is False


@pytest.mark.parametrize("expression", [
    '__import__("os").system("echo NO")',
    "open('secrets.txt')", "[1,2,3]", "2 // 2", "2 % 3",
    "1.1 + 0.2", "True", "pi", "2[0]", "2 ** 100000",
    "2 ** (1 / 2)", "0 ** -1", "1 / 0", "1 / (2 - 2)",
    "2 ** 12 ** 12", "1e9999",
    "1" * 260, "(" * 140 + "1" + ")" * 140,
    "1 << 20", "0x12",
])
def test_reject_invalid_unbounded_and_python_syntax(expression: str):
    result = calculate_exact(expression, approved=True)
    assert result["status"] == "blocked"
    assert result["calculation_performed"] is False
    assert "traceback" not in str(result).lower()


def test_unapproved_math_is_never_calculated():
    assert calculate_exact("42 / 6") == {
        "status": "blocked", "reason": "math_operator_approval_required",
        "calculation_performed": False,
    }


def test_math_result_is_verifiable_and_tamper_detected():
    task = Task(task_id="math-one", content="1 / 3 + 1 / 6",
                domain_hints=["mathematics"])
    result = math_cell_result("math", task, approved=True)
    assert verify_math_cell_result(result, task.content)
    assert result.payload == {"numerator": 1, "denominator": 2}
    assert not verify_math_cell_result(
        result.model_copy(update={"payload": {"numerator": 100, "denominator": 1}}),
        task.content,
    )


def test_math_cell_plugs_into_existing_cognitive_circuit():
    registry = CellRegistry([
        CellSpec(cell_id="math", role=CellRole.MATH, domains=["mathematics"])
    ])
    circuit = CognitiveCircuit(registry)
    task = Task(task_id="math-task", content="2 ** 6 + 1 / 2",
                domain_hints=["mathematics"], risk=0.1, novelty=0.1,
                uncertainty=0.1, latency_budget_ms=600)
    report = circuit.run(
        task, approved=True,
        cell_handler=lambda cell_id, item: math_cell_result(cell_id, item, approved=True),
        verify_evidence=lambda candidate: verify_math_cell_result(candidate, task.content),
    )
    assert report["status"] == "verified"
    assert report["verified_cell_count"] == 1
    assert circuit.spine.verify_integrity().ok
    assert "2 ** 6" not in str(circuit.spine.events)


def test_invalid_math_cell_never_returns_false_verification():
    task = Task(task_id="math-nope", content="1 / 0")
    with pytest.raises(MathRefusal, match="math_division_by_zero"):
        math_cell_result("math", task, approved=True)


def test_independent_computation_detects_injected_mismatch(monkeypatch):
    from hex_cortex.core import cortex_exact_math_v13 as math_module

    monkeypatch.setattr(math_module, "_evaluate_stack", lambda _: Fraction(999))
    assert calculate_exact("10 / 2", approved=True)["reason"] == (
        "math_cross_verification_failed"
    )
