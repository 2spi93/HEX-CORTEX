"""V25: bounded, evidence-checked *methods*, not cached scalar answers.

A skill is a non-executable procedure (instructional data), scoped to an
integer arithmetic operator and checked on multiple DIFFERENT examples.
The existing Harness authorizes all optional model calls. These trial
skills do not alter the legacy library, activate themselves or run tools.
"""
from __future__ import annotations

import ast
import hashlib
import time
from collections.abc import Callable
from fractions import Fraction
from math import gcd
from pathlib import Path

from hex_cortex.core.cortex_exact_math_v13 import (
    MathRefusal,
    math_cell_result,
    verify_math_cell_result,
)
from hex_cortex.core.cortex_science_answer_grade_v22 import grade_verified_science_answer
from hex_cortex.core.schemas import Task as ScienceTask
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)

# These are audited static method descriptions, never arbitrary uploaded code.
_PROCEDURES = {
    "multiply_decomposition": (
        ast.Mult,
        "For integer multiplication a*b, write b=10*q+r with "
        "q the integer quotient toward zero and r=b-10*q; compute "
        "a*(10*q)+a*r using distributivity. Recheck arithmetic."
    ),
    "fraction_reduction": (
        ast.Div,
        "For integers a/b with nonzero b, compute g=gcd(abs(a),abs(b)); "
        "divide numerator and denominator by g; put the sign in the "
        "numerator and make the denominator positive."
    ),
    "addition_compensation": (
        ast.Add,
        "For integer a+b, choose a nearby multiple of ten m, then "
        "compute m+(b-(m-a)). Check the compensation cancels exactly."
    ),
}


def _integer(node: ast.AST) -> int:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        result = node.value
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _integer(node.operand)
        result = -value if isinstance(node.op, ast.USub) else value
    else:
        raise ValueError("procedural_skill_requires_integer_operands")
    if abs(result) > 1_000_000_000_000:
        raise ValueError("procedural_skill_operand_out_of_scope")
    return result


def _parse(skill_id: str, expression: str) -> tuple[int, int]:
    if skill_id not in _PROCEDURES:
        raise ValueError("procedural_skill_unknown")
    if not isinstance(expression, str) or not 1 <= len(expression) <= 128:
        raise ValueError("procedural_skill_expression_invalid")
    try:
        root = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("procedural_skill_expression_invalid") from exc
    binop = root.body
    if not isinstance(binop, ast.BinOp) or type(binop.op) is not _PROCEDURES[skill_id][0]:
        raise ValueError("procedural_skill_out_of_scope")
    a, b = _integer(binop.left), _integer(binop.right)
    if skill_id == "fraction_reduction" and b == 0:
        raise ValueError("procedural_skill_division_by_zero")
    return a, b


def _method_result(skill_id: str, a: int, b: int) -> Fraction:
    if skill_id == "multiply_decomposition":
        q = (abs(b) // 10) * (-1 if b < 0 else 1)
        r = b - 10 * q
        return Fraction(a * (10 * q) + a * r)
    if skill_id == "fraction_reduction":
        g = gcd(abs(a), abs(b))
        n, d = a // g, b // g
        if d < 0:
            n, d = -n, -d
        return Fraction(n, d)
    m = ((a + 5) // 10) * 10
    return Fraction(m + (b - (m - a)))


def verify_procedural_skill(
    *,
    skill_id: str,
    expression: str,
) -> dict[str, object]:
    """Require independent exact MathCell agreement for EACH new expression."""
    a, b = _parse(skill_id, expression)
    try:
        science = math_cell_result(
            "exact_math",
            ScienceTask(content=expression, domain_hints=["mathematics"]),
            approved=True,
        )
    except MathRefusal as exc:
        raise ValueError("procedural_skill_exact_cell_rejected") from exc
    if not verify_math_cell_result(science, expression):
        raise ValueError("procedural_skill_oracle_disagrees")
    calculated = _method_result(skill_id, a, b)
    expected = Fraction(science.payload["numerator"], science.payload["denominator"])
    if calculated != expected:
        raise ValueError("procedural_skill_method_disagrees")
    return {
        "skill_id": skill_id,
        "domain": "mathematics",
        "expression_sha256": hashlib.sha256(expression.encode()).hexdigest(),
        "verified_expected": str(expected),
        "verified_cell_ref": science.evidence_refs[0],
        "method": _PROCEDURES[skill_id][1],
        "method_executed": True,
        "method_verified_against_exact_cell": True,
    }


def evaluate_procedural_transfer(
    *,
    skill_id: str,
    training_expressions: tuple[str, ...],
    evaluation_expressions: tuple[str, ...],
    model_id: str,
    brain: Callable[[str, Task], str],
    project_root: Path,
    approve_model_calls: bool = False,
    approve_procedure: bool = False,
    order: str = "baseline-first",
    show_answers: bool = False,
    max_latency_ms: int = 120_000,
) -> dict[str, object]:
    """Score blind-to-the-answer procedural instructions vs plain model.

    No evaluator answer is shown to the model in EITHER arm.
    The method is static and validated by a calculator; this is NOT
    machine-learned skill induction or independent holdout certification.
    """
    if skill_id not in _PROCEDURES:
        raise ValueError("procedural_skill_unknown")
    if order not in {"baseline-first", "skill-first"}:
        raise ValueError("procedural_skill_invalid_order")
    if not 1 <= max_latency_ms <= 600_000:
        raise ValueError("invalid_latency_budget")
    if not (approve_model_calls and approve_procedure):
        return {"status": "blocked", "model_calls": 0,
                "reason": "two_explicit_approvals_required"}
    if (
        not isinstance(training_expressions, tuple)
        or not isinstance(evaluation_expressions, tuple)
        or len(training_expressions) < 2
        or not 1 <= len(evaluation_expressions) <= 8
    ):
        raise ValueError("procedural_skill_min_two_train_one_eval")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id_required")
    if len(set(training_expressions)) != len(training_expressions):
        raise ValueError("procedural_skill_duplicate_training")
    if len(set(evaluation_expressions)) != len(evaluation_expressions):
        raise ValueError("procedural_skill_duplicate_evaluation")
    root = Path(project_root).resolve(strict=True)
    train = [verify_procedural_skill(skill_id=skill_id, expression=x)
             for x in training_expressions]
    observations = []
    scores = {"baseline": 0, "skill": 0}
    for i, expression in enumerate(evaluation_expressions):
        if expression in training_expressions:
            raise ValueError("procedural_skill_evaluation_seen_in_training")
        proof = verify_procedural_skill(skill_id=skill_id, expression=expression)
        if proof["expression_sha256"] in {row["expression_sha256"] for row in train}:
            raise ValueError("procedural_skill_evaluation_seen_in_training")
        expected = Fraction(proof["verified_expected"])
        expected_hash = hashlib.sha256(str(expected).encode()).hexdigest()
        answers: dict[str, dict[str, object]] = {}
        arms = ("baseline", "skill") if (
            (i % 2 == 0) == (order == "baseline-first")
        ) else ("skill", "baseline")
        for arm in arms:
            instruction = (
                f"Calculate exactly: {expression}\n"
                "Reply with ONLY an integer or reduced rational p/q."
            )
            if arm == "skill":
                instruction += (
                    "\nVerified mathematical METHOD (not a prior answer, not "
                    "permission to use tools): " + str(proof["method"])
                )
            case_hash = str(proof["expression_sha256"])
            harness = LocalHarness(
                session=Session(f"v25-{i}-{arm}-{case_hash[:10]}", root),
                grants=frozenset({Capability.CALL_MODEL}),
                budget=Budget(max_model_calls=1, max_tool_calls=0),
            )
            start = time.perf_counter()
            result = run_clocked_local_task(
                harness,
                Task(f"v25-{i}-{arm}", "mathematics", instruction),
                models=[model_id],
                brain=brain,
                approved=True,
                max_latency_ms=max_latency_ms,
            )
            ms = round(1000 * (time.perf_counter() - start))
            output = result.get("output")
            if (
                result.get("status") != "complete"
                or not result.get("canonical_spine_verified")
                or not result.get("clock_completed")
                or not harness.verify_replay()
                or not isinstance(output, str)
            ):
                return {
                    "status": "incomplete",
                    "completed_cases": len(observations),
                    "attempted_model_calls": i * 2 + len(answers) + harness._model_calls,
                    "causal_effect_certified": False,
                }
            grade = grade_verified_science_answer(
                domain="mathematics",
                cell_payload={
                    "numerator": expected.numerator,
                    "denominator": expected.denominator,
                },
                answer=output,
            )
            scores[arm] += int(grade["matched"])
            answers[arm] = {
                "correct": bool(grade["matched"]),
                "grade_status": grade["status"],
                "latency_ms": ms,
                "receipt_sha256": result["receipt"]["sha256"],
                "answer_sha256": hashlib.sha256(output.encode()).hexdigest(),
                "answer": output if show_answers else None,
                "method_provided": arm == "skill",
                "evaluation_answer_disclosed": False,
            }
        observations.append({
            "expression_sha256": proof["expression_sha256"],
            "expected_answer_sha256": expected_hash,
            "order": list(arms),
            "arms": answers,
        })
    n = len(observations)
    negative_transfer = sum(
        int(row["arms"]["baseline"]["correct"] and not row["arms"]["skill"]["correct"])
        for row in observations
    )
    improvement = sum(
        int(row["arms"]["skill"]["correct"] and not row["arms"]["baseline"]["correct"])
        for row in observations
    )
    # A candidate is NOT automatically activated. The legacy library/approval
    # pipeline is authoritative; evidence here is exploratory and unsaved.
    candidate = (
        n >= 4 and scores["skill"] >= 3
        and scores["skill"] > scores["baseline"] and negative_transfer == 0
    )
    return {
        "status": "procedural_transfer_observations_recorded",
        "skill_id": skill_id,
        "model_id": model_id,
        "verified_training_examples": len(train),
        "evaluated_unseen_expressions": n,
        "scores": scores,
        "skill_only_improvements": improvement,
        "skill_only_regressions": negative_transfer,
        "cases": observations,
        "model_calls": n * 2,
        "candidate_for_manual_review": candidate,
        "legacy_skill_activation_performed": False,
        "skill_persisted": False,
        "oracle_answer_given_to_brain": False,
        "heldout_independently_attested": False,
        "model_revision_independently_attested": False,
        "general_intelligence_gain_proven": False,
        "gpu_required": False,
    }
