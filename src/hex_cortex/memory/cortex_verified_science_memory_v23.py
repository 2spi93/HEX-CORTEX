"""Opt-in, source-checked physics/chemistry facts for Replay and durable memory.

Uses already existing deterministic cognitive circuit calculations. This does
not establish experimental physical truth, reaction feasibility, or tool rights.
"""
from __future__ import annotations

import json

from hex_cortex.core.cortex_verified_science_circuit import run_verified_science_circuit
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _proof(domain: str, task_id: str, request_text: str) -> dict[str, object]:
    if domain not in {"physics", "chemistry"}:
        raise ValueError("unsupported_science_fact_domain")
    if (
        not isinstance(task_id, str) or not task_id.strip()
        or not isinstance(request_text, str)
        or not 1 <= len(request_text) <= 4096
    ):
        raise ValueError("science_fact_input_invalid")
    try:
        obj = json.loads(request_text)
    except (ValueError, TypeError) as exc:
        raise ValueError("science_fact_request_json_invalid") from exc
    if not isinstance(obj, dict):
        raise ValueError("science_fact_request_shape_invalid")
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    report = run_verified_science_circuit(
        domain=domain, task_id=task_id, request=canonical, approved=True,
    )
    if (
        report["status"] != "verified_science_circuit"
        or not report["spine_integrity_ok"]
        or report["verified_cell_count"] != 1
        or not report["evidence_refs"]
    ):
        raise ValueError("science_fact_not_verified")
    result = report["verified_payload"]
    if not isinstance(result, dict):
        raise ValueError("science_fact_invalid_cell_payload")

    if domain == "physics":
        summary = (
            f"Verified idealized physics formula {result['law']}: "
            f"{result['numerator']}/{result['denominator']} {result['unit']}"
        )
    else:
        # Original ChemistryCell guarantees atom balance under the allowlist.
        balance = result["balance"]
        summary = (
            "Verified idealized chemistry atom balance: "
            + json.dumps(balance, sort_keys=True, separators=(",", ":"))
        )
    if len(summary) > 1800:
        raise ValueError("science_fact_summary_too_long")
    return {
        "domain": domain,
        "request": obj,
        "result": result,
        "evidence_refs": list(report["evidence_refs"]),
        "goal": f"Review verified idealized {domain} calculation",
        "observations": [summary],
    }


def append_verified_science_fact(
    spine: CanonicalSpine,
    *,
    domain: str,
    task_id: str,
    request_text: str,
    approved: bool = False,
) -> dict[str, object]:
    """Operator-approved append; no implicit persistence or model inference."""
    if not approved:
        raise PermissionError("science_fact_operator_approval_required")
    if not spine.verify_integrity().ok:
        raise ValueError("science_fact_spine_integrity_failed")
    if spine.events_for_task(task_id):
        raise ValueError("science_fact_task_id_already_used")
    fact = _proof(domain, task_id, request_text)
    first = spine.append(
        event_type="science.verified_domain_fact",
        task_id=task_id,
        source="VerifiedScienceCircuit",
        payload=fact,
        confidence=1.0,
    )
    spine.append(
        event_type="clock.completed", task_id=task_id,
        source="VerifiedScienceMemory",
        payload={"completed": True},
        confidence=1.0,
    )
    return {
        "status": "verified_science_fact_recorded",
        "domain": domain,
        "task_id": task_id,
        "source_event_id": first.event_id,
        "spine_integrity_ok": spine.verify_integrity().ok,
        "model_called": False,
        "file_saved": False,
        "physical_action_authorized": False,
    }


def verify_science_fact_task(spine: CanonicalSpine, task_id: str) -> bool:
    """Repeat the science cell and reject even coherently rehashed forgeries."""
    if not spine.verify_integrity().ok:
        return False
    events = spine.events_for_task(task_id)
    if len(events) != 2:
        return False
    first, second = events
    if (
        first.event_type != "science.verified_domain_fact"
        or first.source != "VerifiedScienceCircuit"
        or first.confidence != 1.0
        or second.event_type != "clock.completed"
        or second.source != "VerifiedScienceMemory"
        or second.confidence != 1.0
        or second.payload != {"completed": True}
    ):
        return False
    payload = first.payload
    domain = payload.get("domain")
    request = payload.get("request")
    if not isinstance(domain, str) or not isinstance(request, dict):
        return False
    try:
        expected = _proof(
            domain,
            task_id,
            json.dumps(request, sort_keys=True, separators=(",", ":")),
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return False
    return payload == expected
