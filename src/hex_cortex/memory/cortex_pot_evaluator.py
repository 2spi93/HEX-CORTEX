"""Program-of-Thoughts evaluator — deterministic arithmetic, never mental.

The benchmark's "coding" domain was really exact arithmetic, and a language
model computing in its head is the wrong tool. Program-of-Thoughts separates
reasoning from calculation: the model proposes an arithmetic *expression*, and a
deterministic engine computes the result. This module is that engine and the
matching grader — a reusable external verifier for exact-numeric tasks (the
competence rule "never trust the LLM's mental arithmetic" made executable).

Safety: expressions are evaluated through an AST whitelist — numeric literals, a
fixed set of arithmetic operators, and a short list of math functions. No
builtins, names, attributes, subscripts, comprehensions, or imports are ever
reachable, and exponent / factorial magnitudes are bounded to prevent blowups.
It runs no model and touches no I/O.
"""

from __future__ import annotations

import ast
import math
import re

_MAX_POW_EXPONENT = 1000
_MAX_FACTORIAL = 2000

_BINARY_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}
_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}
_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "factorial": math.factorial,
    "comb": math.comb,
    "perm": math.perm,
    "gcd": math.gcd,
    "lcm": math.lcm,
}
_FENCE = re.compile(r"```(?:python|py)?\s*(.+?)```", re.DOTALL)


class PoTError(ValueError):
    """Raised when a candidate is missing, unsafe, or not pure arithmetic."""


def evaluate_arithmetic(text: str) -> float:
    """Extract and safely evaluate the arithmetic expression in ``text``."""
    if not isinstance(text, str):
        raise PoTError("text must be a string")
    last_error: Exception | None = None
    for candidate in _candidate_expressions(text):
        try:
            tree = ast.parse(candidate, mode="eval")
        except SyntaxError as exc:
            last_error = exc
            continue
        try:
            return _eval(tree.body)
        except PoTError as exc:
            last_error = exc
            continue
    raise PoTError(f"no safe arithmetic expression found ({last_error})")


def grade_arithmetic(text: str, expected: float, *, tolerance: float = 1e-9) -> dict[str, object]:
    """Deterministically grade a Program-of-Thoughts answer. Fails closed."""
    try:
        value = evaluate_arithmetic(text)
    except PoTError as exc:
        return {
            "correct": False,
            "value": None,
            "method": "deterministic_python",
            "error": str(exc),
        }
    correct = abs(value - expected) <= tolerance
    return {"correct": correct, "value": value, "method": "deterministic_python", "error": None}


def _candidate_expressions(text: str) -> list[str]:
    """Ordered candidates to try: fenced blocks, then trailing lines/fragments."""
    candidates: list[str] = []

    def add(value: str) -> None:
        value = value.strip().rstrip(".")
        if value and value not in candidates:
            candidates.append(value)

    for block in _FENCE.findall(text):
        for line in reversed(block.splitlines()):
            add(line)
    stripped = text.strip()
    add(stripped)
    for line in reversed(stripped.splitlines()):
        add(line)
        # Common phrasings: "answer = 6", "result: 6".
        for separator in ("=", ":"):
            if separator in line:
                add(line.rsplit(separator, 1)[1])
    return candidates


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise PoTError("only numeric literals are allowed")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BINARY_OPS.get(type(node.op))
        if op is None:
            raise PoTError("operator not allowed")
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_POW_EXPONENT:
            raise PoTError("exponent too large")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise PoTError("unary operator not allowed")
        return op(_eval(node.operand))
    if isinstance(node, ast.Call):
        return _eval_call(node)
    raise PoTError(f"disallowed expression node: {type(node).__name__}")


def _eval_call(node: ast.Call) -> float:
    if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
        raise PoTError("only whitelisted math functions may be called")
    if node.keywords:
        raise PoTError("keyword arguments are not allowed")
    args = [_eval(arg) for arg in node.args]
    name = node.func.id
    if name == "factorial":
        if not args or args[0] != int(args[0]) or not 0 <= args[0] <= _MAX_FACTORIAL:
            raise PoTError("factorial argument out of bounds")
    return _FUNCTIONS[name](*args)
