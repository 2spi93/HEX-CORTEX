from hex_cortex.memory.construction_status_report import (
    build_construction_status_report,
    summarize_construction_status_reports,
)


def test_construction_status_blocks_missing_pack(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_construction_status_report(profile)
    summary = summarize_construction_status_reports(
        profile / "construction-status-report.jsonl"
    )
    record = payload["status_record"]

    assert record["construction_decision"] == "construction_blocked"
    assert record["construction_complete"] is False
    assert record["blocker_count"] == 1
    assert len(record["report_hash"]) == 64
    assert summary["latest_construction_decision"] == "construction_blocked"
