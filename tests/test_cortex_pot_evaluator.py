import pytest

from hex_cortex.memory.cortex_pot_evaluator import PoTError
from hex_cortex.memory.cortex_pot_evaluator import evaluate_arithmetic
from hex_cortex.memory.cortex_pot_evaluator import grade_arithmetic


def test_evaluates_plain_expression() -> None:
    assert evaluate_arithmetic("2 + 3 * 4") == 14


def test_extracts_from_fenced_block() -> None:
    text = "Here is the computation:\n```python\n(10 + 2) * 5\n```\n"
    assert evaluate_arithmetic(text) == 60


def test_extracts_from_trailing_answer_phrasing() -> None:
    assert evaluate_arithmetic("Reasoning blah blah\nanswer = 6 * 7") == 42
    assert evaluate_arithmetic("result: 100 // 7") == 14


def test_whitelisted_functions() -> None:
    assert evaluate_arithmetic("factorial(5)") == 120
    assert evaluate_arithmetic("comb(10, 2)") == 45
    assert evaluate_arithmetic("gcd(48, 36)") == 12


def test_inclusion_exclusion_style_expression() -> None:
    # Sum of multiples of 3 or 5 below 1000 (the classic residual example).
    expr = "sum(range(1000))"  # not allowed -> must fail closed, see below
    result = grade_arithmetic(expr, 233168)
    assert result["correct"] is False  # range/sum are not whitelisted
    # The deterministic, whitelisted form instead:
    ie = "3*333*334//2 + 5*199*200//2 - 15*66*67//2"
    assert evaluate_arithmetic(ie) == 233168


def test_rejects_unsafe_constructs() -> None:
    for hostile in (
        "__import__('os').system('echo hi')",
        "open('x')",
        "[i for i in range(3)]",
        "1 .__class__",
        "x + 1",
    ):
        with pytest.raises(PoTError):
            evaluate_arithmetic(hostile)


def test_bounds_exponent_and_factorial() -> None:
    with pytest.raises(PoTError):
        evaluate_arithmetic("2 ** 100000")
    with pytest.raises(PoTError):
        evaluate_arithmetic("factorial(99999)")


def test_grade_is_fail_closed_on_garbage() -> None:
    result = grade_arithmetic("I think it is probably around forty-two", 42)
    assert result["correct"] is False
    assert result["value"] is None
    assert result["method"] == "deterministic_python"


def test_grade_correct_within_tolerance() -> None:
    result = grade_arithmetic("1 / 3", 0.3333333333, tolerance=1e-6)
    assert result["correct"] is True
    assert result["method"] == "deterministic_python"
