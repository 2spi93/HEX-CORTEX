"""Bounded, opt-in, two-arm local comparison using the existing ExactMathCell.

Uses the actual LocalHarness/CognitiveClock permission and receipt pathway for
both arms; does not fabricate LLM output, persist prompts, or claim causality.
"""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from hex_cortex.core.cortex_exact_math_v13 import (
    MathRefusal,
    math_cell_result,
    verify_math_cell_result,
)
from hex_cortex.core.schemas import Task as CoreTask
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
)

_RATIONAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z")


def _grade(answer: str, expected: Fraction) -> bool:
    """Strict rational-only grading; prose, units, and extra tokens fail."""
    candidate = answer.strip()
    if not _RATIONAL.fullmatch(candidate) or len(candidate) > 256:
        return False
    try:
        return Fraction(candidate) == expected
    except (ValueError, ZeroDivisionError, OverflowError):
        return False


def run_verified_math_pair(
    *,
    project_root: Path,
    expression: str,
    model_id: str,
    brain: Callable[[str, Task], str],
    approve_math: bool = False,
    approve_two_model_calls: bool = False,
    order: str = "baseline-first",
    max_latency_ms: int = 120_000,
    reveal_outputs: bool = False,
) -> dict[str, object]:
    """Two real Harness calls, with/without a separately verified math fact.

    The exact answer is supplied to the CORTEX arm by design: this evaluates a
    calculator-assisted system, NOT intrinsic reasoning or memory uplift.
    """
    if order not in {"baseline-first", "cortex-first"}:
        raise ValueError("invalid_arm_order")
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256:
        raise ValueError("invalid_math_expression")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id_required")
    if not 1 <= max_latency_ms <= 600_000:
        raise ValueError("invalid_latency_budget")
    if not (approve_math and approve_two_model_calls):
        return {
            "status": "blocked",
            "reason": "explicit_math_and_two_model_call_approvals_required",
            "model_calls": 0,
            "math_cell_executed": False,
            "causal_effect_certified": False,
        }

    # Model-independent, typed CellResult with independently repeated
    # verification. The entire expression is supplied by the operator.
    expr_hash = hashlib.sha256(expression.encode("utf-8")).hexdigest()
    task = CoreTask(
        task_id=f"math-expression-{expr_hash[:24]}",
        content=expression,
        domain_hints=["mathematics"],
        latency_budget_ms=max_latency_ms,
    )
    try:
        proof = math_cell_result("exact_math", task, approved=True)
    except MathRefusal:
        return {
            "status": "blocked",
            "reason": "math_expression_not_verifiable",
            "model_calls": 0,
            "math_cell_executed": True,
            "causal_effect_certified": False,
        }
    if not verify_math_cell_result(proof, expression):
        return {
            "status": "blocked",
            "reason": "independent_math_verification_failed",
            "model_calls": 0,
            "math_cell_executed": True,
            "causal_effect_certified": False,
        }
    numerator = proof.payload["numerator"]
    denominator = proof.payload["denominator"]
    expected = Fraction(numerator, denominator)
    reference = str(expected)

    # The original operator question is *identical* in both arms.
    original = (
        f"Compute this expression exactly: {expression}\n"
        "Answer ONLY with the rational number (integer or p/q)."
    )
    augmented = (
        f"{original}\n"
        "\nVerified independent ExactMathCell computation (read-only evidence):\n"
        f"expression_sha256: {expr_hash}\n"
        f"verified_rational: {reference}\n"
        "Return only the rational number. Do not claim to have run the tool yourself."
    )
    order_names = ["baseline", "cortex"] if order == "baseline-first" else [
        "cortex", "baseline"
    ]
    results: dict[str, dict[str, object]] = {}
    for arm in order_names:
        harness = LocalHarness(
            session=Session(
                session_id=f"math-pair-{arm}-{expr_hash[:12]}",
                project_root=Path(project_root).resolve(strict=True),
            ),
            grants=frozenset({Capability.CALL_MODEL}),
            budget=Budget(max_model_calls=1, max_tool_calls=0),
        )
        prompt = original if arm == "baseline" else augmented
        t0 = time.perf_counter()
        result = run_clocked_local_task(
            harness,
            Task(
                task_id=f"math-pair-{arm}-{expr_hash[:24]}",
                domain="mathematics",
                instruction=prompt,
            ),
            models=[model_id],
            brain=brain,
            approved=True,
            max_latency_ms=max_latency_ms,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1_000)
        output = result.get("output")
        valid = (
            result.get("status") == "complete"
            and result.get("clock_completed") is True
            and result.get("canonical_spine_verified") is True
            and harness.verify_replay()
            and isinstance(output, str)
        )
        if not valid:
            return {
                "status": "incomplete",
                "reason": f"{arm}_harness_or_model_failed",
                "completed_arms": len(results),
                "model_calls": sum(int(x["model_calls_used"]) for x in results.values())
                + harness._model_calls,
                "math_cell_verified": True,
                "causal_effect_certified": False,
            }
        receipt = result.get("receipt")
        results[arm] = {
            "correct": _grade(output, expected),
            "latency_ms": elapsed_ms,
            "model_calls_used": 1,
            "receipt_sha256": receipt["sha256"],
            "answer_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "answer": output if reveal_outputs else None,
            "context_contains_exact_math_evidence": arm == "cortex",
        }

    return {
        "status": "paired_observations_recorded",
        "model_id": model_id,
        "model_revision_independently_verified": False,
        "expression_sha256": expr_hash,
        "expression_operator_supplied": True,
        "math_evidence_refs": list(proof.evidence_refs),
        "verified_result": reference,
        "math_cell_verified": True,
        "evaluation_type": "single_operator_selected_case_exact_calculator_assistance",
        "arm_order": order_names,
        "baseline": results["baseline"],
        "cortex": results["cortex"],
        "delta_correct": int(results["cortex"]["correct"]) - int(
            results["baseline"]["correct"]
        ),
        "model_calls": 2,
        "held_out_independently_attested": False,
        "real_model_calls_independently_attested": False,
        "causal_effect_certified": False,
        "general_intelligence_certified": False,
        "memory_uplift_evaluated": False,
        "physical_action_authorized": False,
        "files_saved": False,
    }
