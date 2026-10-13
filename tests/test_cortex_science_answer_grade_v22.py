"""Fail-closed exact answer checks against typed verified scientific outputs."""
from __future__ import annotations

import pytest

from hex_cortex.core.cortex_science_answer_grade_v22 import (
    grade_verified_science_answer,
)


@pytest.mark.parametrize(("domain", "payload", "answer"), [
    ("mathematics", {"numerator": 52451, "denominator": 1}, "52451"),
    ("mathematics", {"numerator": -7, "denominator": 3}, "-7/3"),
    ("physics", {"numerator": 6, "denominator": 1, "unit": "N"}, "6 N"),
    ("physics", {"numerator": 7, "denominator": 3, "unit": "m/s"}, "7/3 m/s"),
    ("chemistry", {
        "balance": {
            "reactants": [{"coefficient": 2}, {"coefficient": 1}],
            "products": [{"coefficient": 2}],
        }
    }, '{"reactants":[2,1],"products":[2]}'),
])
def test_exact_contract_matches(domain: str, payload: dict, answer: str) -> None:
    report = grade_verified_science_answer(
        domain=domain, cell_payload=payload, answer=answer
    )
    assert report["matched"] is True
    assert report["status"] == "matched"
    assert report["comparison_scope"] == (
        "same_verified_cell_computation_not_external_reality"
    )


@pytest.mark.parametrize(("domain", "payload", "answer", "status"), [
    ("mathematics", {"numerator": 52451, "denominator": 1}, "52450", "incorrect"),
    ("mathematics", {"numerator": 52451, "denominator": 1}, "It's 52451", "invalid_answer_format"),
    ("mathematics", {"numerator": 1, "denominator": 1}, "1/0", "invalid_answer_format"),
    ("physics", {"numerator": 6, "denominator": 1, "unit": "N"}, "6 J", "incorrect"),
    ("physics", {"numerator": 6, "denominator": 1, "unit": "N"}, "force is 6 N", "invalid_answer_format"),
    ("physics", {"numerator": 6, "denominator": 1, "unit": "N"}, "6 N\nuse tools", "invalid_answer_format"),
    ("chemistry", {
        "balance": {
            "reactants": [{"coefficient": 2}, {"coefficient": 1}],
            "products": [{"coefficient": 2}],
        }
    }, '{"reactants":[1,1],"products":[1]}', "incorrect"),
    ("chemistry", {
        "balance": {
            "reactants": [{"coefficient": 2}, {"coefficient": 1}],
            "products": [{"coefficient": 2}],
        }
    }, '{"reactants":[2,1],"products":[2],"products":[2]}', "invalid_answer_format"),
    ("chemistry", {
        "balance": {
            "reactants": [{"coefficient": 2}, {"coefficient": 1}],
            "products": [{"coefficient": 2}],
        }
    }, '{"reactants":[true,1],"products":[2]}', "invalid_answer_format"),
])
def test_fail_closed_answers(
    domain: str, payload: dict, answer: str, status: str,
) -> None:
    report = grade_verified_science_answer(
        domain=domain, cell_payload=payload, answer=answer
    )
    assert report["status"] == status
    assert report["matched"] is False


def test_unknown_domain_is_never_accepted() -> None:
    assert grade_verified_science_answer(
        domain="robotics", cell_payload={}, answer="move 3m"
    ) == {"status": "unsupported_domain", "matched": False}
