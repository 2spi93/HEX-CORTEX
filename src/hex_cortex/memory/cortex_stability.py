from __future__ import annotations


def compute_cortex_stability(
    *,
    success_rate: float,
    error_rate: float,
    unknown_unit_rate: float,
    citation_rate: float,
    receipt_rate: float,
) -> dict[str, object]:
    values = {
        "success_rate": success_rate,
        "error_rate": error_rate,
        "unknown_unit_rate": unknown_unit_rate,
        "citation_rate": citation_rate,
        "receipt_rate": receipt_rate,
    }
    blockers = [name for name, value in values.items() if value < 0 or value > 1]
    if blockers:
        return {
            "stability_type": "cortex_stability",
            "stability_status": "blocked",
            "stability_allowed": False,
            "blockers": [f"{name}_out_of_range" for name in blockers],
        }
    score = round(
        100
        * (
            0.30 * success_rate
            + 0.20 * (1 - error_rate)
            + 0.15 * (1 - unknown_unit_rate)
            + 0.20 * citation_rate
            + 0.15 * receipt_rate
        ),
        2,
    )
    action = "stable" if score >= 80 else "rebalance"
    return {
        "stability_type": "cortex_stability",
        "stability_status": action,
        "stability_allowed": True,
        "score": score,
        "action": action,
        "repair_suggestions": _suggestions(
            error_rate=error_rate,
            unknown_unit_rate=unknown_unit_rate,
            citation_rate=citation_rate,
            receipt_rate=receipt_rate,
        ),
    }


def _suggestions(
    *,
    error_rate: float,
    unknown_unit_rate: float,
    citation_rate: float,
    receipt_rate: float,
) -> list[str]:
    suggestions = []
    if error_rate > 0.1:
        suggestions.append("add_failure_fixture")
    if unknown_unit_rate > 0:
        suggestions.append("register_or_reject_unknown_units")
    if citation_rate < 0.8:
        suggestions.append("increase_source_citation_coverage")
    if receipt_rate < 0.9:
        suggestions.append("increase_receipt_coverage")
    return suggestions
