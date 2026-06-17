from hex_cortex.memory.profile_resync_report import (
    build_profile_resync_report,
    summarize_profile_resync_reports,
)
from hex_cortex.memory.review_propagation import (
    ReviewPropagationJsonlStore,
    ReviewPropagationRecord,
)


def test_profile_resync_blocks_missing_pack(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_profile_resync_report(profile)
    record = payload["resync_record"]

    assert record["resync_decision"] == "resync_blocked"
    assert record["resync_allowed"] is False


def test_profile_resync_summary_after_blocked_record(tmp_path) -> None:
    profile = tmp_path / "profile"
    build_profile_resync_report(profile)
    summary = summarize_profile_resync_reports(profile / "profile-resync-report.jsonl")

    assert summary["latest_resync_decision"] == "resync_blocked"
    assert summary["total_resync_count"] == 1


def test_profile_resync_ready_requires_pack_and_flow(tmp_path) -> None:
    profile = tmp_path / "profile"
    ReviewPropagationJsonlStore(profile / "review-propagation.jsonl").append(
        ReviewPropagationRecord(
            profile_path=str(profile),
            selected_skill="operator_watch_review",
            source_note_id="note_a",
            operator_choice="accept",
            note_allowed=True,
            propagation_status="ready",
            propagation_decision="propagation_ready",
            propagation_allowed=True,
            next_action="rerun_construction_status",
            reasons=["test_flow"],
        )
    )

    payload = build_profile_resync_report(profile)
    record = payload["resync_record"]

    assert record["resync_decision"] == "resync_blocked"
    assert record["active_blockers"] == ["pack_missing"]
