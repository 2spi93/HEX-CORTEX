from __future__ import annotations


def build_operator_preference_profile() -> dict[str, object]:
    return {
        "profile_type": "operator_preferences",
        "preferred_execution_style": "fast_branch_first_with_tests",
        "language": "fr",
        "merge_style": "fast_forward_only",
        "validation_required": ["pytest", "ruff"],
        "auto_mode_preference": "auto_safe_when_trusted",
        "risk_posture": "receipts_first_no_hidden_execution",
        "next_action": "use_for_trusted_plan_scoring",
    }


def score_operator_preference_match(*, requested_style: str) -> dict[str, object]:
    profile = build_operator_preference_profile()
    preferred = profile["preferred_execution_style"]
    score = 1.0 if requested_style == preferred else 0.5
    return {
        "score_type": "operator_preference_match",
        "score": score,
        "preferred_execution_style": preferred,
        "requested_style": requested_style,
        "matched": requested_style == preferred,
    }
