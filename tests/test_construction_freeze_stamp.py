from hex_cortex.memory.construction_freeze_stamp import (
    build_construction_freeze_stamp,
    summarize_construction_freeze_stamps,
)


def test_construction_freeze_blocks_missing_status(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_construction_freeze_stamp(profile)
    summary = summarize_construction_freeze_stamps(
        profile / "construction-freeze-stamp.jsonl"
    )
    record = payload["freeze_record"]

    assert record["freeze_decision"] == "freeze_blocked"
    assert record["freeze_allowed"] is False
    assert len(record["freeze_hash"]) == 64
    assert summary["latest_freeze_decision"] == "freeze_blocked"
