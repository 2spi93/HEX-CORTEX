from hex_cortex.memory.manual_review_note import (
    record_manual_review_note,
    summarize_manual_review_notes,
)


def test_manual_review_note_records_hold(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = record_manual_review_note(
        profile,
        selected_skill="operator_watch_review",
        choice="hold",
        note="manual review pending",
    )
    summary = summarize_manual_review_notes(profile / "manual-review-note.jsonl")
    record = payload["note_record"]

    assert record["operator_choice"] == "hold"
    assert record["note_allowed"] is False
    assert record["next_action"] == "prepare_skill_activation_review"
    assert summary["latest_operator_choice"] == "hold"


def test_manual_review_note_records_accept(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = record_manual_review_note(
        profile,
        selected_skill="operator_watch_review",
        choice="accept",
        note="operator accepted review",
    )
    record = payload["note_record"]

    assert record["operator_choice"] == "accept"
    assert record["note_allowed"] is True
    assert record["next_action"] == "rerun_construction_status"
