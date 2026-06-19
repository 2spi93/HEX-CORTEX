from hex_cortex.memory.cortex_lane import CORTEX_LANE_FILENAME
from hex_cortex.memory.cortex_lane import build_cortex_output_receipt
from hex_cortex.memory.cortex_lane import build_cortex_tool_receipt
from hex_cortex.memory.cortex_lane import build_cortex_visual_receipt
from hex_cortex.memory.cortex_lane import build_cortex_voice_receipt


def test_all_lane_receipts_are_ready_without_effects(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    cases = [
        (build_cortex_output_receipt, "local_output", "run_local_output_adapter"),
        (build_cortex_tool_receipt, "tool", "run_tool_adapter"),
        (build_cortex_voice_receipt, "voice", "run_voice_adapter"),
        (build_cortex_visual_receipt, "visual", "run_visual_adapter"),
    ]

    for index, (builder, lane, next_action) in enumerate(cases):
        payload = builder(
            profile,
            route_record=_route(lane, index),
            request_hash=f"request-{index}",
        )
        record = payload["lane_receipt_records"][0]
        assert record["lane_allowed"] is True
        assert record["lane"] == lane
        assert record["raw_request_persisted"] is False
        assert record["external_effect_performed"] is False
        assert record["tool_call_performed"] is False
        assert record["network_call_performed"] is False
        assert record["local_process_started"] is False
        assert record["next_action"] == next_action

    assert (profile / CORTEX_LANE_FILENAME).exists()


def test_lane_receipt_blocks_mismatch(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_voice_receipt(
        profile,
        route_record=_route("tool", 0),
        request_hash="request-hash",
    )

    record = payload["lane_receipt_records"][0]
    assert record["lane_allowed"] is False
    assert "route_lane_mismatch" in record["blockers"]
    assert record["next_action"] == "repair_lane_receipt"


def test_lane_receipt_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "route_record": _route("local_output", 0),
        "request_hash": "request-hash",
    }

    first = build_cortex_output_receipt(profile, **kwargs)
    second = build_cortex_output_receipt(profile, **kwargs)

    assert first["lane_receipt_count"] == 1
    assert second["lane_receipt_count"] == 1
    assert first["lane_receipt_records"][0]["lane_receipt_hash"] == second[
        "lane_receipt_records"
    ][0]["lane_receipt_hash"]


def _route(lane: str, index: int) -> dict[str, object]:
    return {
        "route_allowed": True,
        "route_hash": f"route-{index}",
        "action_id": f"action-{index}",
        "output_id": "test-output",
        "lane": lane,
    }
