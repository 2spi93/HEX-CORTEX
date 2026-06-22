"""Cognitive loop plan — the operational loop that ties the organs together.

The limit was never raw intelligence; it was wiring the organs into one coherent
loop. This is that wiring. Given a task and the current world (the brain ledger
plus a GPU snapshot) it composes, in order:

    1. strategy   adaptive compute policy picks a strategy + requested tier
    2. resource   the GPU governor admits / downgrades / defers that tier
    3. inference  the verified-inference planner routes a primary + escalation
                  brain and a self-consistency sampling/escalation plan

into a single execution plan. It runs nothing — pure composition over the pure
components, advisory only. A runtime (autonomy step 4+) executes the result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_adaptive_compute_policy import select_compute_strategy
from hex_cortex.memory.cortex_gpu_governor import decide_gpu_admission
from hex_cortex.memory.cortex_verified_inference_plan import build_verified_inference_plan

_PLAN_TYPE = "cortex_cognitive_loop_plan_v1"


def build_cognitive_loop_plan(
    ledger: Path,
    gpu_snapshot: dict[str, object],
    *,
    task_domain: str,
    context_sensitivity: str,
    difficulty: str = "medium",
    risk: str = "low",
    prior_confidence: float | None = None,
    maximum_latency_ms: float = 5000.0,
    cost_pressure: float = 0.5,
    remote_allowed: bool = False,
    target_confidence: float = 0.7,
    is_benchmark: bool = False,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Compose strategy + GPU admission + verified inference into one plan."""
    exact = task_domain.strip().lower() in {
        "arithmetic_reasoning",
        "arithmetic",
        "math",
        "exact_numeric",
    }
    large_available = _ledger_has_remote_capable_brain(ledger)
    strategy = select_compute_strategy(
        difficulty=difficulty,
        risk=risk,
        domain=task_domain,
        prior_confidence=prior_confidence,
        large_model_available=large_available,
        target_confidence=target_confidence,
    )

    gpu_decision = decide_gpu_admission(
        gpu_snapshot,
        {"tier": str(strategy["requested_tier"]), "is_benchmark": is_benchmark},
    )
    gpu_action = str(gpu_decision["action"])

    inference_plan = build_verified_inference_plan(
        ledger,
        task_domain=task_domain,
        context_sensitivity=context_sensitivity,
        maximum_latency_ms=maximum_latency_ms,
        cost_pressure=cost_pressure,
        remote_allowed=remote_allowed,
        initial_samples=int(strategy["samples"]),
        target_confidence=target_confidence,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if gpu_action in {"defer", "reject"}:
        blockers.append(f"gpu_{gpu_action}")
    if inference_plan["status"] != "ready":
        blockers.extend(str(b) for b in inference_plan.get("blockers", []) or ["no_primary_brain"])

    needs_independent_critic = bool(
        strategy.get("escalate_to_second_model") or strategy.get("use_adversarial_critique")
    )
    independent_critic_available = bool(inference_plan.get("escalation_brain_id"))
    verification_gap = needs_independent_critic and not independent_critic_available
    if verification_gap:
        warnings.append("independent_model_unavailable_human_review_required")

    require_human_validation = bool(strategy["require_human_validation"] or verification_gap)

    if blockers:
        status, next_action = "blocked", "retry_after_cooldown_or_escalate"
    elif gpu_action == "queue":
        status, next_action = "queued", "wait_for_gpu_slot_then_execute"
    elif verification_gap:
        status, next_action = "ready", "execute_primary_then_human_review"
    else:
        status, next_action = "ready", "execute_cognitive_loop_plan"

    record = {
        "record_type": _PLAN_TYPE,
        "event_id": f"loopplan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "task_domain": task_domain,
        "context_sensitivity": context_sensitivity,
        "difficulty": difficulty,
        "risk": risk,
        "target_confidence": target_confidence,
        "granted_tier": gpu_decision["granted_tier"],
        "strategy": strategy["strategy"],
        "use_deterministic_tool": strategy["use_deterministic_tool"],
        "use_self_consistency": strategy["use_self_consistency"],
        "use_adversarial_critique": strategy["use_adversarial_critique"],
        "samples": strategy["samples"],
        "primary_brain_id": inference_plan.get("primary_brain_id"),
        "escalation_brain_id": inference_plan.get("escalation_brain_id"),
        "independent_critic_available": independent_critic_available,
        "verification_gap": verification_gap,
        "require_human_validation": require_human_validation,
        "exact_arithmetic_domain": exact,
        "components": {
            "strategy": strategy,
            "gpu_decision": gpu_decision,
            "inference_plan_hash": inference_plan.get("plan_hash"),
            "escalation_diversity": inference_plan.get("escalation_diversity"),
        },
        "model_call_performed": False,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": next_action,
    }
    record["plan_hash"] = _stable_hash(record)
    if receipt_path is not None:
        _append_jsonl(receipt_path, record)
    return record


def _ledger_has_remote_capable_brain(ledger: Path) -> bool:
    """A large/escalation tier is available if any non-local brain is registered."""
    try:
        from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry

        registry = project_brain_registry(ledger)
    except (ValueError, OSError):
        return False
    brains = registry.get("brains")
    table = brains if isinstance(brains, dict) else {}
    return any(
        isinstance(b, dict) and b.get("provider_scope") in {"private_remote", "metered_remote"}
        for b in table.values()
    )


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
