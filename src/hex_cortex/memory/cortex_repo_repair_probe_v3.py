"""Offline, no-exec repository repair benchmark for locally selected models.

Models propose complete replacements for tiny Python package snapshots. The
grader NEVER executes generated Python, applies a patch, uses a subprocess, or
writes to the user's checkout. A deliberately restricted AST interpreter
checks functional behavior against deterministic, held-out inputs. Results
are indicative only and never auto-certify routing or editing permissions.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass

_SUITE_VERSION = "repo-repair-v3.0"
_MAX_SOURCE_BYTES = 12_000
_MAX_RESPONSE_BYTES = 32_000


@dataclass(frozen=True)
class RepairCase:
    case_id: str
    description: str
    files: dict[str, str]
    function: str
    split: str = "holdout"


CASES: tuple[RepairCase, ...] = (
    RepairCase(
        "fees_sign",
        "Correct the net P&L calculation so trading fees reduce gross profit.",
        {"calc/pnl.py": "def net_pnl(gross, fees):\n    return gross + fees\n"},
        "net_pnl",
        "validation",
    ),
    RepairCase(
        "risk_floor",
        "Ensure remaining risk capacity never becomes negative.",
        {"risk/limits.py": "def position_room(limit, used):\n    return limit - used\n"},
        "position_room",
        "validation",
    ),
    RepairCase(
        "boundary_two_files",
        "Correct risk capacity and ensure an order exactly at the remaining limit is allowed.",
        {
            "risk/limits.py": "def position_room(limit, used):\n    return limit - used\n",
            "desk/order.py": (
                "from risk.limits import position_room\n\n"
                "def can_open(limit, used, request):\n"
                "    return request < position_room(limit, used)\n"
            ),
        },
        "can_open",
        "holdout",
    ),
    RepairCase(
        "zero_division",
        "Return zero for an empty trade sample, otherwise wins divided by total trades.",
        {
            "metrics/win_rate.py": (
                "def win_rate(wins, losses):\n    return wins / (wins + losses)\n"
            )
        },
        "win_rate",
        "holdout",
    ),
)


def suite_manifest() -> dict[str, object]:
    tasks = [
        {
            "task_id": case.case_id,
            "description": case.description,
            "file_paths": sorted(case.files),
            "split": case.split,
        }
        for case in CASES
    ]
    digest = hashlib.sha256(
        json.dumps(tasks, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "suite_version": _SUITE_VERSION,
        "suite_hash": digest,
        "tasks": tasks,
        "task_count": len(tasks),
        "evaluation_kind": "restricted_ast_semantics_no_generated_code_execution",
        "production_coding_certification": False,
    }


def render_task_prompt(case: RepairCase) -> str:
    lines = [
        "Repair the buggy Python repository snapshot below.",
        case.description,
        "Return ONLY a JSON object with the key 'files' mapping every listed path",
        "to its complete corrected Python source string. No markdown or prose.",
        "You may edit only these files. Keep the documented function signatures.",
        "Do not import third-party modules or call external commands.",
        "",
    ]
    for path, source in sorted(case.files.items()):
        lines.extend((f"FILE: {path}", source, ""))
    return "\n".join(lines)


def parse_candidate(text: str, case: RepairCase) -> dict[str, str]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
        raise ValueError("model response is missing or oversized")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("response must be strict JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"files"}:
        raise ValueError("response must contain only files")
    files = payload["files"]
    if not isinstance(files, dict) or set(files) != set(case.files):
        raise ValueError("only exactly the listed files may be replaced")
    if any(
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > _MAX_SOURCE_BYTES
        for value in files.values()
    ):
        raise ValueError("invalid replacement content or oversized file")
    return dict(files)


def _build_functions(files: Mapping[str, str]) -> dict[str, ast.FunctionDef]:
    functions: dict[str, ast.FunctionDef] = {}
    imports: dict[str, str] = {}
    modules: dict[str, str] = {
        path.removesuffix(".py").replace("/", "."): path for path in files
    }
    for path, content in files.items():
        try:
            tree = ast.parse(content, filename=path)
        except (SyntaxError, ValueError) as exc:
            raise ValueError("replacement contains invalid Python syntax") from exc
        local_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.level != 0 or node.module not in modules:
                    raise ValueError("external or relative imports forbidden")
                for alias in node.names:
                    if alias.asname is not None or alias.name.startswith("_"):
                        raise ValueError("import aliases/private symbols forbidden")
                    imports[alias.name] = node.module
            elif isinstance(node, ast.FunctionDef):
                args = node.args
                if (
                    node.decorator_list or node.returns is not None or args.defaults
                    or args.kw_defaults or args.vararg or args.kwarg or args.posonlyargs
                    or args.kwonlyargs or any(arg.annotation for arg in args.args)
                ):
                    raise ValueError("only simple, undecorated functions permitted")
                if any(arg.arg.startswith("_") for arg in args.args):
                    raise ValueError("private or dynamic names forbidden")
                if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
                    raise ValueError("one pure return expression required")
                if node.name.startswith("_") or node.name in local_names:
                    raise ValueError("private or duplicate function")
                local_names.add(node.name)
                if node.name in functions:
                    raise ValueError("ambiguous exported function")
                functions[node.name] = node
            else:
                raise ValueError("top-level statements other than functions/imports forbidden")
    for name, module in imports.items():
        target_path = modules[module]
        target_tree = ast.parse(files[target_path])
        if not any(isinstance(node, ast.FunctionDef) and node.name == name for node in target_tree.body):
            raise ValueError("imported function not found")
    return functions


def _eval_expr(
    node: ast.AST, scope: Mapping[str, object], functions: Mapping[str, ast.FunctionDef],
    meter: list[int], depth: int,
) -> object:
    meter[0] += 1
    if meter[0] > 2000 or depth > 20:
        raise ValueError("AST evaluation budget exceeded")
    if isinstance(node, ast.Constant) and type(node.value) in {int, float, bool}:
        if isinstance(node.value, float) and not math.isfinite(node.value):
            raise ValueError("nonfinite constant")
        return node.value
    if isinstance(node, ast.Name) and node.id in scope:
        return scope[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in {
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod
    }:
        left = _eval_expr(node.left, scope, functions, meter, depth + 1)
        right = _eval_expr(node.right, scope, functions, meter, depth + 1)
        if type(left) not in {int, float} or type(right) not in {int, float}:
            raise ValueError("numeric operands required")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ValueError("division by zero")
        if isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.Mult):
            value = left * right
        elif isinstance(node.op, ast.Div):
            value = left / right
        elif isinstance(node.op, ast.FloorDiv):
            value = left // right
        else:
            value = left % right
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ValueError("numeric output out of bounds")
        return value
    if isinstance(node, ast.UnaryOp) and type(node.op) in {ast.USub, ast.UAdd, ast.Not}:
        value = _eval_expr(node.operand, scope, functions, meter, depth + 1)
        if isinstance(node.op, ast.Not):
            return not value
        if type(value) not in {int, float}:
            raise ValueError("numeric operand required")
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.IfExp):
        predicate = _eval_expr(node.test, scope, functions, meter, depth + 1)
        return _eval_expr(
            node.body if predicate else node.orelse, scope, functions, meter, depth + 1
        )
    if isinstance(node, ast.BoolOp) and type(node.op) in {ast.And, ast.Or}:
        values = node.values
        current: object = False
        for value in values:
            current = _eval_expr(value, scope, functions, meter, depth + 1)
            if isinstance(node.op, ast.And) and not current:
                return current
            if isinstance(node.op, ast.Or) and current:
                return current
        return current
    if isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators):
        left = _eval_expr(node.left, scope, functions, meter, depth + 1)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval_expr(comparator, scope, functions, meter, depth + 1)
            if type(op) is ast.Lt:
                valid = left < right
            elif type(op) is ast.LtE:
                valid = left <= right
            elif type(op) is ast.Gt:
                valid = left > right
            elif type(op) is ast.GtE:
                valid = left >= right
            elif type(op) is ast.Eq:
                valid = left == right
            elif type(op) is ast.NotEq:
                valid = left != right
            else:
                raise ValueError("unsupported comparator")
            if not valid:
                return False
            left = right
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name = node.func.id
        args = [_eval_expr(arg, scope, functions, meter, depth + 1) for arg in node.args]
        if name in {"min", "max", "abs"}:
            if not args or any(type(arg) not in {int, float} for arg in args):
                raise ValueError("invalid safe builtin parameters")
            if name == "abs" and len(args) != 1:
                raise ValueError("abs requires one argument")
            return {"min": min, "max": max, "abs": abs}[name](*args)
        if name in functions:
            return _call_function(functions, name, args, meter, depth + 1)
    raise ValueError("unsafe or unsupported Python AST node")


def _call_function(
    functions: Mapping[str, ast.FunctionDef], name: str,
    args: list[object], meter: list[int], depth: int,
) -> object:
    if name not in functions:
        raise ValueError("missing evaluated function")
    fn = functions[name]
    names = [arg.arg for arg in fn.args.args]
    if len(names) != len(args):
        raise ValueError("function signature mismatch")
    assert isinstance(fn.body[0], ast.Return)
    assert fn.body[0].value is not None
    return _eval_expr(fn.body[0].value, dict(zip(names, args, strict=True)), functions, meter, depth)


def _test_inputs(case_id: str, seed: int) -> list[tuple[object, ...]]:
    rng = random.Random(seed)
    if case_id == "fees_sign":
        return [(25, 3), (0, 0), (10.5, 0.25)] + [
            (rng.randint(0, 500), rng.randint(0, 30)) for _ in range(12)
        ]
    if case_id == "risk_floor":
        return [(10, 10), (10, 11), (10, 0)] + [
            (rng.randint(1, 100), rng.randint(0, 150)) for _ in range(12)
        ]
    if case_id == "boundary_two_files":
        return [(10, 7, 3), (10, 11, 0), (10, 0, 11)] + [
            (rng.randint(1, 100), rng.randint(0, 100), rng.randint(0, 100))
            for _ in range(12)
        ]
    if case_id == "zero_division":
        return [(0, 0), (5, 0), (0, 10)] + [
            (rng.randint(0, 50), rng.randint(0, 50)) for _ in range(12)
        ]
    raise ValueError("unknown repair task")


def _oracle(case_id: str, values: tuple[object, ...]) -> object:
    if case_id == "fees_sign":
        gross, fees = values
        return gross - fees
    if case_id == "risk_floor":
        limit, used = values
        return max(0, limit - used)
    if case_id == "boundary_two_files":
        limit, used, request = values
        return request <= max(0, limit - used)
    if case_id == "zero_division":
        wins, losses = values
        return wins / (wins + losses) if wins + losses else 0
    raise ValueError("unknown repair task")


def score_repair(case: RepairCase, candidate: str, *, seed: int = 20261009) -> dict[str, object]:
    inputs = _test_inputs(case.case_id, seed)
    try:
        files = parse_candidate(candidate, case)
        functions = _build_functions(files)
        if case.function not in functions:
            raise ValueError("required function not implemented")
        passed = 0
        for values in inputs:
            try:
                output = _call_function(functions, case.function, list(values), [0], 0)
                expected = _oracle(case.case_id, values)
                match = (
                    type(output) is bool and output is expected
                    if type(expected) is bool else (
                        type(output) in {int, float}
                        and math.isclose(output, expected, rel_tol=1e-9, abs_tol=1e-9)
                    )
                )
                passed += bool(match)
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                pass
        return {
            "task_id": case.case_id, "split": case.split, "passed": passed == len(inputs),
            "correct_cases": passed, "total_cases": len(inputs),
            "error_code": None if passed == len(inputs) else "behavior_mismatch",
        }
    except (ValueError, TypeError) as exc:
        _ = exc  # Do not persist arbitrary model-supplied source or exception text.
        return {
            "task_id": case.case_id, "split": case.split, "passed": False,
            "correct_cases": 0, "total_cases": len(inputs), "error_code": "candidate_rejected",
        }


def score_repository_benchmark(
    responses: Mapping[str, str], *, model_id: str, model_digest: str,
    quantization: str, hardware_id: str, seed: int = 20261009,
) -> dict[str, object]:
    if not all(isinstance(s, str) and s.strip() for s in (
        model_id, model_digest, quantization, hardware_id
    )):
        raise ValueError("model/hardware identity required")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be a uint32")
    if set(responses) - {case.case_id for case in CASES}:
        raise ValueError("unknown benchmark task id")
    rows = [
        score_repair(case, responses.get(case.case_id, ""), seed=seed)
        for case in CASES
    ]
    holdout = [row for row in rows if row["split"] == "holdout"]
    passed_count = sum(bool(row["passed"]) for row in rows)
    manifest = suite_manifest()
    return {
        "report_type": "hex_cortex_repo_repair_probe_v3",
        "suite_version": manifest["suite_version"],
        "suite_hash": manifest["suite_hash"],
        "seed": seed,
        "model_id": model_id,
        "model_digest": model_digest,
        "quantization": quantization,
        "hardware_id": hardware_id,
        "task_count": len(rows),
        "passed_count": passed_count,
        "overall_score": round(passed_count / len(rows), 6),
        "holdout_score": round(sum(bool(row["passed"]) for row in holdout) / len(holdout), 6),
        "task_results": rows,
        "quality_label": "restricted_ast_repository_probe_not_certified",
        "generated_code_executed": False,
        "checkout_modified": False,
        "routing_prior_authorized": False,
        "raw_candidates_persisted": False,
    }
