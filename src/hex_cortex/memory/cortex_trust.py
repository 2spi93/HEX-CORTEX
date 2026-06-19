from __future__ import annotations


def compute_trusted_plan(
    *,
    operator_intent_known: bool,
    plan_known: bool,
    preference_match: float,
    stability_score: float,
    registered_unit_rate: float,
    receipt_rate: float,
) -> dict[str, object]:
    values = {
        "preference_match": preference_match,
        "stability_score": stability_score,
        "registered_unit_rate": registered_unit_rate,
        "receipt_rate": receipt_rate,
    }
    blockers = [name for name, value in values.items() if value < 0 or value > 1]
    if blockers:
        return {
            "trust_type": "cortex_trusted_plan",
            "trusted_plan": False,
            "blockers": [f"{name}_out_of_range" for name in blockers],
        }
    score = round(
        100
        * (
            0.20 * float(operator_intent_known)
            + 0.20 * float(plan_known)
            + 0.15 * preference_match
            + 0.20 * stability_score
            + 0.15 * registered_unit_rate
            + 0.10 * receipt_rate
        ),
        2,
    )
    trusted = score >= 85 and operator_intent_known and plan_known
    return {
        "trust_type": "cortex_trusted_plan",
        "trusted_plan": trusted,
        "score": score,
        "next_action": "allow_auto_safe_operator_units" if trusted else "request_operator_review",
        "blockers": [] if trusted else _blockers(operator_intent_known, plan_known, score),
    }


def _blockers(operator_intent_known: bool, plan_known: bool, score: float) -> list[str]:
    blockers = []
    if not operator_intent_known:
        blockers.append("operator_intent_unknown")
    if not plan_known:
        blockers.append("plan_unknown")
    if score < 85:
        blockers.append("trust_score_below_threshold")
    return blockers
