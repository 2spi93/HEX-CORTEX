"""Fail-closed applicability gate for a single verified arithmetic fact.

A correct prior *answer* is not a reusable general mathematical rule.
Only the same syntactic arithmetic expression may reuse that answer.
Anything else must be treated as a new task for a calculator/verifier.
"""
from __future__ import annotations

import ast
import hashlib

from hex_cortex.memory.cortex_verified_math_memory import verify_math_fact_task
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _canonical_expression(expression: str) -> str:
    if not isinstance(expression, str) or not 1 <= len(expression.strip()) <= 256:
        raise ValueError("math_scope_expression_invalid")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, TypeError, MemoryError) as exc:
        raise ValueError("math_scope_expression_invalid") from exc
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.UAdd,
               ast.USub)
    for node in ast.walk(tree):
        if type(node) not in allowed:
            raise ValueError("math_scope_expression_unsupported")
        if isinstance(node, ast.Constant) and (
            type(node.value) is not int or len(str(node.value)) > 256
        ):
            raise ValueError("math_scope_constant_invalid")
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def math_fact_applicability(
    spine: CanonicalSpine,
    *,
    source_task_id: str,
    target_expression: str | None,
) -> dict[str, object]:
    """Return explicit refusal/relevance; never substitute equality of values.

    Provenance corruption is an ERROR, not a harmless no-match. A missing
    target means the model cannot safely know that the old scalar is relevant.
    """
    if not verify_math_fact_task(spine, source_task_id):
        raise ValueError("math_fact_applicability_provenance_invalid")
    source_events = spine.events_for_task(source_task_id)
    source = source_events[0].payload["expression"]
    normalized_source = _canonical_expression(source)
    source_hash = hashlib.sha256(normalized_source.encode()).hexdigest()
    if target_expression is None:
        return {
            "eligible": False,
            "reason": "target_expression_unavailable",
            "source_expression_signature": source_hash,
        }
    try:
        normalized_target = _canonical_expression(target_expression)
    except ValueError:
        return {
            "eligible": False,
            "reason": "target_expression_unverifiable",
            "source_expression_signature": source_hash,
        }
    if normalized_source != normalized_target:
        return {
            "eligible": False,
            "reason": "different_arithmetic_expression",
            "source_expression_signature": source_hash,
        }
    return {
        "eligible": True,
        "reason": "identical_verified_expression",
        "source_expression_signature": source_hash,
    }
