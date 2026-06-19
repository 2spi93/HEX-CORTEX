from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_policy import CortexMode
from hex_cortex.memory.cortex_policy import decide_cortex_unit_access
from hex_cortex.memory.cortex_trust import compute_trusted_plan


def evaluate_cortex_auto_plan(
    *,
    registry: dict[str, CortexUnit],
    plan: list[dict[str, object]],
    operator_intent_known: bool,
    plan_known: bool,
    preference_match: float,
    stability_score: float,
    registered_unit_rate: float,
    receipt_rate: float,
    mode: CortexMode = CortexMode.AUTO_SAFE,
) -> dict[str, object]:
    trust = compute_trusted_plan(
        operator_intent_known=operator_intent_known,
        plan_known=plan_known,
        preference_match=preference_match,
        stability_score=stability_score,
        registered_unit_rate=registered_unit_rate,
        receipt_rate=receipt_rate,
    )
    trusted_plan = trust.get("trusted_plan") is True
    decisions = []
    blockers = list(trust.get("blockers", []))
    for index, step in enumerate(plan):
        name = step.get("name")
        if not isinstance(name, str):
            blockers.append(f"step_{index}_missing_name")
            decisions.append(
                {
                    "index": index,
                    "name": None,
                    "allowed": False,
                    "reason": "missing_name",
                    "needs_operator": True,
                }
            )
            continue
        decision = decide_cortex_unit_access(
            mode=mode,
            unit_name=name,
            registry=registry,
            trusted_plan=trusted_plan,
        )
        decisions.append(
            {
                "index": index,
                "name": name,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "needs_operator": decision.needs_operator,
            }
        )
        if not decision.allowed:
            blockers.append(f"step_{index}:{decision.reason}")
    allowed = not blockers
    return {
        "auto_plan_type": "cortex_auto_plan",
        "mode": mode.value,
        "auto_plan_allowed": allowed,
        "trusted_plan": trusted_plan,
        "trust": trust,
        "step_count": len(plan),
        "decisions": decisions,
        "blockers": blockers,
        "next_action": "run_via_cortex_bus" if allowed else "request_operator_review",
    }
