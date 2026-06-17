from hex_cortex.memory.reason_deduplicator import deduplicate_reasons, reason_dedup_report


def test_deduplicate_reasons_keeps_order() -> None:
    assert deduplicate_reasons(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_reason_dedup_report_counts_removed() -> None:
    report = reason_dedup_report(["a", "a", "b"])

    assert report["input_count"] == 3
    assert report["output_count"] == 2
    assert report["removed_count"] == 1
    assert report["reasons"] == ["a", "b"]
