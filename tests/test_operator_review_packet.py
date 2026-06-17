from hex_cortex.memory.operator_review_packet import (
    build_operator_review_packet,
    summarize_operator_review_packets,
)


def test_operator_review_packet_blocks_missing_inputs(tmp_path) -> None:
    profile = tmp_path / "profile"
    payload = build_operator_review_packet(profile)
    summary = summarize_operator_review_packets(profile / "operator-review-packet.jsonl")
    record = payload["review_record"]

    assert record["review_decision"] == "review_blocked"
    assert record["approval_allowed"] is False
    assert record["operator_action"] == "build_registry_review_gate"
    assert summary["latest_review_decision"] == "review_blocked"
