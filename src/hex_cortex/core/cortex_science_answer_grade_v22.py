"""Deterministic strict grading against *typed* verified cell payloads.

A matched response is agreement with an idealized verified computation, not
proof that a scientific measurement is true or that an LLM reasons generally.
Unexpected prose/JSON structures are refused rather than weakly inferred.
"""
from __future__ import annotations

import json
import re
from fractions import Fraction

_RATIONAL = re.compile(r"-?(?:0|[1-9]\d*)(?:/[1-9]\d*)?\Z")
_PHYSICAL = re.compile(r"(-?(?:0|[1-9]\d*)(?:/[1-9]\d*)?) ([A-Za-z][A-Za-z0-9*/^]*)\Z")
_MAX_ANSWER = 1024


def _fraction(value: str) -> Fraction | None:
    if len(value) > 256 or _RATIONAL.fullmatch(value) is None:
        return None
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def _coefficients(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) > 8:
        return None
    if any(type(number) is not int or not 1 <= number <= 10_000 for number in value):
        return None
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for name, value in pairs:
        if name in obj:
            raise ValueError("duplicate_json_key")
        obj[name] = value
    return obj


def grade_verified_science_answer(
    *,
    domain: str,
    cell_payload: dict[str, object],
    answer: str,
) -> dict[str, object]:
    """Accept only a complete exact result, no arbitrary prose or tool claims.

    Strict contracts:
      mathematics: 52451 or -7/3
      physics:     6 N or -7/3 m/s
      chemistry:   {"reactants":[2,1],"products":[2]}
    """
    if domain not in {"mathematics", "physics", "chemistry"}:
        return {"status": "unsupported_domain", "matched": False}
    if not isinstance(answer, str) or len(answer) > _MAX_ANSWER:
        return {"status": "invalid_answer_format", "matched": False}
    raw = answer.strip()
    try:
        if domain in {"mathematics", "physics"}:
            expected = Fraction(
                int(cell_payload["numerator"]), int(cell_payload["denominator"])
            )
            if domain == "mathematics":
                actual = _fraction(raw)
                valid_format = actual is not None
                matched = valid_format and actual == expected
            else:
                found = _PHYSICAL.fullmatch(raw)
                valid_format = found is not None
                if not valid_format:
                    matched = False
                else:
                    actual = _fraction(found.group(1))
                    matched = (
                        actual is not None
                        and actual == expected
                        and found.group(2) == cell_payload["unit"]
                    )
        else:
            balance = cell_payload["balance"]
            if not isinstance(balance, dict):
                raise ValueError("invalid_cell_payload")
            parsed = json.loads(raw, object_pairs_hook=_unique_object)
            valid_format = isinstance(parsed, dict) and set(parsed) == {
                "reactants", "products"
            }
            if valid_format:
                reactants = _coefficients(parsed["reactants"])
                products = _coefficients(parsed["products"])
                valid_format = reactants is not None and products is not None
            matched = bool(
                valid_format
                and reactants == [row["coefficient"] for row in balance["reactants"]]
                and products == [row["coefficient"] for row in balance["products"]]
            )
    except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError):
        valid_format = False
        matched = False
    return {
        "status": "matched" if matched else (
            "incorrect" if valid_format else "invalid_answer_format"
        ),
        "matched": bool(matched),
        "comparison_scope": "same_verified_cell_computation_not_external_reality",
    }
