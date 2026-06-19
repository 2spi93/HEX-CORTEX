from hex_cortex.memory.cortex_preferences import build_operator_preference_profile
from hex_cortex.memory.cortex_preferences import score_operator_preference_match


def test_operator_preference_profile_defaults() -> None:
    payload = build_operator_preference_profile()

    assert payload["language"] == "fr"
    assert payload["merge_style"] == "fast_forward_only"
    assert payload["auto_mode_preference"] == "auto_safe_when_trusted"
    assert "pytest" in payload["validation_required"]
    assert "ruff" in payload["validation_required"]


def test_operator_preference_match_full_score() -> None:
    payload = score_operator_preference_match(
        requested_style="fast_branch_first_with_tests",
    )

    assert payload["score"] == 1.0
    assert payload["matched"] is True


def test_operator_preference_match_partial_score() -> None:
    payload = score_operator_preference_match(requested_style="slow_manual")

    assert payload["score"] == 0.5
    assert payload["matched"] is False
