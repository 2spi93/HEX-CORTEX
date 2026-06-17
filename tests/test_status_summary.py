from hex_cortex.memory.receipt_summary import (
    build_receipt_summary,
    summarize_receipt_summaries,
)


def test_status_summary_handles_empty_profile(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_receipt_summary(profile)
    summary = summarize_receipt_summaries(profile / "receipt-summary.jsonl")
    record = payload["summary_record"]

    assert record["summary_decision"] == "summary_blocked"
    assert record["summary_score"] == 0.0
    assert summary["latest_summary_decision"] == "summary_blocked"
