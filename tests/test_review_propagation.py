from hex_cortex.memory.manual_review_note import record_manual_review_note
from hex_cortex.memory.review_propagation import (
    build_review_propagation,
    summarize_review_propagations,
)


def test_review_propagation_blocks_missing_note(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_review_propagation(profile)
    record = payload["propagation_record"]

    assert record["propagation_decision"] == "propagation_blocked"
    assert record["propagation_allowed"] is False


def test_review_propagation_readies_accept_note(tmp_path) -> None:
    profile = tmp_path / "profile"
    record_manual_review_note(
        profile,
        selected_skill="operator_watch_review",
        choice="accept",
        note="accepted",
    )

    payload = build_review_propagation(profile)
    summary = summarize_review_propagations(profile / "review-propagation.jsonl")
    record = payload["propagation_record"]

    assert record["propagation_decision"] == "propagation_ready"
    assert record["propagation_allowed"] is True
    assert summary["latest_propagation_decision"] == "propagation_ready"
