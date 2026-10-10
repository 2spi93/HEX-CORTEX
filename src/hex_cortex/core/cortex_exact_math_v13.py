"""ExactMathCell: bounded exact arithmetic without LLM, eval or sympy parsing.

This is a real mathematical computation organ, not a universal theorem prover.
Input is strictly an expression over integer literals, + - * / ** and unary + -.
Every intermediate value is a Fraction and resource-bounded; independent
second traversal checks the result before a verified CellResult is emitted.
No imports, attributes, calls, names, floats, Python execution or I/O.
"""

from __future__ import annotations

import ast
import hashlib
from fractions import Fraction

from hex_cortex.core.schemas import CellResult, Task

_MAX_CHARS = 256
_MAX_NODES = 64
_MAX_DEPTH = 18
_MAX_BITS = 256
_MAX_EXPONENT = 12


class MathRefusal(ValueError):
    """User expressions are rejected with a non-sensitive reason code."""


def _bounded(value: Fraction) -> Fraction:
    if value.numerator.bit_length() > _MAX_BITS or value.denominator.bit_length() > _MAX_BITS:
        raise MathRefusal("math_intermediate_budget_exceeded")
    return value


def _validated_tree(expression: str) -> ast.Expression:
    if not isinstance(expression, str) or not expression or len(expression) > _MAX_CHARS:
        raise MathRefusal("math_input_length_invalid")
    if any(c not in "0123456789+-*/() \t" for c in expression):
        raise MathRefusal("math_forbidden_syntax")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise MathRefusal("math_syntax_invalid") from exc
    count = 0
    def walk(node: ast.AST, depth: int) -> None:
        nonlocal count
        count += 1
        if count > _MAX_NODES or depth > _MAX_DEPTH:
            raise MathRefusal("math_ast_budget_exceeded")
        if isinstance(node, ast.Expression):
            walk(node.body, depth + 1)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int):
                raise MathRefusal("math_integer_literals_only")
            if node.value.bit_length() > _MAX_BITS:
                raise MathRefusal("math_integer_too_large")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            walk(node.operand, depth + 1)
        elif isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
        ):
            walk(node.left, depth + 1)
            walk(node.right, depth + 1)
        else:
            raise MathRefusal("math_disallowed_ast")
    walk(tree, 0)
    return tree


def _fraction_pow(left: Fraction, right: Fraction) -> Fraction:
    if right.denominator != 1 or abs(right.numerator) > _MAX_EXPONENT:
        raise MathRefusal("math_exponent_out_of_range")
    if left == 0 and right.numerator < 0:
        raise MathRefusal("math_division_by_zero")
    if right.numerator and (
        left.numerator.bit_length() * abs(right.numerator) > _MAX_BITS * 2
        or left.denominator.bit_length() * abs(right.numerator) > _MAX_BITS * 2
    ):
        raise MathRefusal("math_exponent_budget_exceeded")
    return _bounded(left ** right.numerator)


def _evaluate_tree(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Expression):
        return _evaluate_tree(node.body)
    if isinstance(node, ast.Constant):
        return _bounded(Fraction(node.value))
    if isinstance(node, ast.UnaryOp):
        value = _evaluate_tree(node.operand)
        return _bounded(-value if isinstance(node.op, ast.USub) else value)
    if isinstance(node, ast.BinOp):
        left = _evaluate_tree(node.left)
        right = _evaluate_tree(node.right)
        if isinstance(node.op, ast.Add):
            return _bounded(left + right)
        if isinstance(node.op, ast.Sub):
            return _bounded(left - right)
        if isinstance(node.op, ast.Mult):
            return _bounded(left * right)
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise MathRefusal("math_division_by_zero")
            return _bounded(left / right)
        return _fraction_pow(left, right)
    raise MathRefusal("math_disallowed_ast")


def _evaluate_stack(tree: ast.Expression) -> Fraction:
    """Separate non-recursive postorder reducer checks recursive evaluation."""
    visiting = [(tree.body, False)]
    values: list[Fraction] = []
    while visiting:
        node, done = visiting.pop()
        if isinstance(node, ast.Constant):
            values.append(_bounded(Fraction(node.value)))
        elif not done:
            visiting.append((node, True))
            if isinstance(node, ast.UnaryOp):
                visiting.append((node.operand, False))
            elif isinstance(node, ast.BinOp):
                visiting.append((node.right, False))
                visiting.append((node.left, False))
            else:
                raise MathRefusal("math_disallowed_ast")
        elif isinstance(node, ast.UnaryOp):
            x = values.pop()
            values.append(_bounded(-x if isinstance(node.op, ast.USub) else x))
        elif isinstance(node, ast.BinOp):
            y, x = values.pop(), values.pop()
            if isinstance(node.op, ast.Add):
                v = x + y
            elif isinstance(node.op, ast.Sub):
                v = x - y
            elif isinstance(node.op, ast.Mult):
                v = x * y
            elif isinstance(node.op, ast.Div):
                if y == 0:
                    raise MathRefusal("math_division_by_zero")
                v = x / y
            else:
                v = _fraction_pow(x, y)
            values.append(_bounded(v))
    if len(values) != 1:
        raise MathRefusal("math_stack_invalid")
    return values[0]


def calculate_exact(expression: str, *, approved: bool = False) -> dict[str, object]:
    """Return an exact checked rational, never run a string as Python code."""
    if not approved:
        return {"status": "blocked", "reason": "math_operator_approval_required",
                "calculation_performed": False}
    try:
        tree = _validated_tree(expression)
        first = _evaluate_tree(tree)
        second = _evaluate_stack(tree)
        if first != second:
            raise MathRefusal("math_cross_verification_failed")
    except MathRefusal as exc:
        return {"status": "blocked", "reason": str(exc), "calculation_performed": False}
    except (ZeroDivisionError, OverflowError, MemoryError, ValueError, RecursionError):
        return {"status": "blocked", "reason": "math_arithmetic_failed",
                "calculation_performed": False}
    return {
        "status": "verified_exact_arithmetic",
        "numerator": first.numerator,
        "denominator": first.denominator,
        "rational": str(first),
        "expression_sha256": hashlib.sha256(expression.encode()).hexdigest(),
        "calculation_performed": True,
        "independent_traversal_agrees": True,
        "scientific_claim_certified": False,
        "model_used": False,
        "code_executed": False,
        "external_tools_called": False,
    }


def math_cell_result(cell_id: str, task: Task, *, approved: bool = False) -> CellResult:
    """Produce a typed result for the existing cognitive circuit."""
    report = calculate_exact(task.content, approved=approved)
    if report["status"] != "verified_exact_arithmetic":
        raise MathRefusal(str(report.get("reason", "math_evidence_missing")))
    return CellResult(
        cell_id=cell_id,
        task_id=task.task_id,
        confidence=1.0,
        uncertainty=0.0,
        payload={"numerator": report["numerator"], "denominator": report["denominator"]},
        evidence_refs=["math:exact:" + str(report["expression_sha256"])],
    )


def verify_math_cell_result(candidate: CellResult, expression: str) -> bool:
    """Compare typed candidate to a new bounded exact evaluation of input."""
    proof = calculate_exact(expression, approved=True)
    return (
        proof["status"] == "verified_exact_arithmetic"
        and candidate.evidence_refs == ["math:exact:" + str(proof["expression_sha256"])]
        and candidate.payload == {
            "numerator": proof["numerator"], "denominator": proof["denominator"]
        }
    )
