"""Bounded static Python code context for genuine model-assisted code review.

Only structural metadata is returned; no source strings, comments, expression
values, function bodies, secrets, or imports are executed.
"""
from __future__ import annotations

import ast


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    return None


def describe_python_structure(source: str) -> dict[str, object]:
    if not isinstance(source, str) or len(source.encode("utf-8")) > 128_000:
        raise ValueError("code_structure_source_too_large")
    tree = ast.parse(source, filename="<approved_python_code>")
    functions = []
    for item in ast.walk(tree):
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        scoped = [node for statement in item.body for node in ast.walk(statement)]
        calls = sorted({name for n in scoped if (name := _call_name(n))})[:16]
        functions.append({
            "name": item.name[:100],
            "line": item.lineno,
            "parameters": len(item.args.posonlyargs) + len(item.args.args)
            + len(item.args.kwonlyargs),
            "branches": sum(isinstance(n, (ast.If, ast.Match, ast.IfExp))
                            for n in scoped),
            "loops": sum(isinstance(n, (ast.For, ast.AsyncFor, ast.While))
                         for n in scoped),
            "exception_handlers": sum(isinstance(n, ast.ExceptHandler)
                                      for n in scoped),
            "returns": sum(isinstance(n, ast.Return) for n in scoped),
            "calls": calls,
        })
        if len(functions) >= 20:
            break
    return {
        "functions": functions,
        "function_metadata_truncated": sum(isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) for n in ast.walk(tree)) > 20,
        "class_names": [n.name[:100] for n in ast.walk(tree)
                        if isinstance(n, ast.ClassDef)][:12],
        "total_lines": len(source.splitlines()),
        "syntax_valid": True,
        "contents_disclosed": False,
        "source_semantics_verified": False,
    }


def assess_review_substance(
    plan: dict[str, object],
    *,
    source_disclosed: bool,
) -> dict[str, object]:
    """Separate schema validity from actual evidentiary review value."""
    if not isinstance(plan, dict):
        return {"status": "unassessable", "actionable": False}
    summary = str(plan.get("summary", "")).strip()
    changes = plan.get("proposed_changes")
    risks = plan.get("risks")
    unknowns = plan.get("unknowns")
    template_copy = (
        summary == "Review based only on available structural evidence"
        and changes == []
        and risks == ["Source logic was not read"]
        and unknowns == ["Implementation details not available"]
    )
    if template_copy:
        return {
            "status": "prompt_template_echo",
            "actionable": False,
            "reason": "copied_provided_example_without_review",
        }
    if not isinstance(changes, list) or not changes:
        return {
            "status": "no_specific_change_proposed",
            "actionable": False,
            "reason": "valid_json_is_not_a_substantive_code_review",
        }
    if not source_disclosed:
        return {
            "status": "structural_suggestions_only",
            "actionable": False,
            "reason": "implementation_not_read_by_model",
        }
    return {
        "status": "source_informed_proposal_unverified",
        "actionable": False,
        "reason": "suggestion_requires_independent_human_or_test_validation",
    }
