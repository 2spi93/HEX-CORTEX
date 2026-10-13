"""Source-checked exact arithmetic facts for the existing replay/memory circuit.

Mathematical truth is checked independently, not inferred from Spine hashes
or a LLM-generated description. No implicit persistence, inference or promotion.
"""
from __future__ import annotations

import hashlib
from fractions import Fraction

from hex_cortex.core.cortex_exact_math_v13 import (
    MathRefusal,
    math_cell_result,
    verify_math_cell_result,
)
from hex_cortex.core.schemas import Task as CoreTask
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _expected_fact(expression: str, task_id: str) -> dict[str, object]:
    expression = expression.strip()
    if not expression or len(expression) > 256 or not task_id.strip():
        raise ValueError("verified_math_invalid_input")
    task = CoreTask(task_id=task_id, content=expression, domain_hints=["mathematics"])
    try:
        proof = math_cell_result("exact_math", task, approved=True)
    except MathRefusal as exc:
        raise ValueError("verified_math_expression_rejected") from exc
    if not verify_math_cell_result(proof, expression):
        raise ValueError("verified_math_independent_check_failed")
    value = str(Fraction(proof.payload["numerator"], proof.payload["denominator"]))
    return {
        "expression": expression,
        "expression_sha256": hashlib.sha256(expression.encode("utf-8")).hexdigest(),
        "numerator": proof.payload["numerator"],
        "denominator": proof.payload["denominator"],
        "evidence_ref": proof.evidence_refs[0],
        "goal": f"Compute exact arithmetic {expression}",
        "observations": [f"Verified exact arithmetic: {expression} = {value}"],
    }


def append_verified_math_fact(
    spine: CanonicalSpine,
    *,
    task_id: str,
    expression: str,
    approved: bool = False,
) -> dict[str, object]:
    """Append one complete, source-checked math episode to a verified Spine."""
    if not approved:
        raise PermissionError("math_fact_requires_explicit_approval")
    if not spine.verify_integrity().ok:
        raise ValueError("invalid_math_fact_spine")
    if spine.events_for_task(task_id):
        raise ValueError("math_fact_task_id_already_exists")
    payload = _expected_fact(expression, task_id)
    first = spine.append(
        event_type="math.exact_verified", task_id=task_id,
        source="ExactMathCell", payload=payload, confidence=1.0,
    )
    spine.append(
        event_type="clock.completed", task_id=task_id,
        source="VerifiedMathMemory", payload={"completed": True}, confidence=1.0,
    )
    return {
        "status": "verified_math_fact_recorded",
        "task_id": task_id,
        "event_id": first.event_id,
        "expression_sha256": payload["expression_sha256"],
        "evidence_ref": payload["evidence_ref"],
        "spine_integrity_ok": spine.verify_integrity().ok,
        "model_called": False,
        "persisted": False,
    }


def verify_math_fact_task(spine: CanonicalSpine, task_id: str) -> bool:
    """Validate exact proof payload and the single-task completion envelope.

    Useful before any memory containing math.exact_verified is injected into
    a Brain. A valid hash chain *alone* does not certify arithmetic truth.
    """
    if not spine.verify_integrity().ok:
        return False
    events = spine.events_for_task(task_id)
    if len(events) != 2:
        return False
    proof_event, completion = events
    if (
        proof_event.event_type != "math.exact_verified"
        or proof_event.source != "ExactMathCell"
        or proof_event.confidence != 1.0
        or completion.event_type != "clock.completed"
        or completion.source != "VerifiedMathMemory"
        or completion.payload != {"completed": True}
        or completion.confidence != 1.0
    ):
        return False
    expression = proof_event.payload.get("expression")
    if not isinstance(expression, str):
        return False
    try:
        expected = _expected_fact(expression, task_id)
    except ValueError:
        return False
    return proof_event.payload == expected
