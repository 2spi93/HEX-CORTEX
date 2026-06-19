from hex_cortex.memory.cortex_route import CORTEX_ROUTE_FILENAME
from hex_cortex.memory.cortex_route import build_cortex_route_receipt
from hex_cortex.memory.cortex_route import list_cortex_routes


def test_route_catalog_covers_all_output_families() -> None:
    rows = list_cortex_routes()
    lanes = {row["lane"] for row in rows}

    assert lanes == {
        "asset",
        "account",
        "tool",
        "voice",
        "visual",
        "local_output",
    }


def test_route_media_selection(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_route_receipt(
        profile,
        pick_record=_pick("generate_image"),
    )

    record = payload["route_records"][0]
    assert record["route_allowed"] is True
    assert record["lane"] == "asset"
    assert record["next_unit"] == "asset.receipt"
    assert record["external_effect_performed"] is False
    assert record["network_call_performed"] is False
    assert record["local_process_started"] is False


def test_route_account_selection(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_route_receipt(
        profile,
        pick_record=_pick("publish_social_content"),
    )

    record = payload["route_records"][0]
    assert record["route_allowed"] is True
    assert record["lane"] == "account"
    assert record["next_unit"] == "account.receipt"


def test_route_blocks_unready_pick(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    pick = _pick("write_text")
    pick["ready_for_next_receipt"] = False

    payload = build_cortex_route_receipt(profile, pick_record=pick)

    record = payload["route_records"][0]
    assert record["route_allowed"] is False
    assert "pick_not_ready_for_route" in record["blockers"]


def test_route_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    pick = _pick("generate_video")

    first = build_cortex_route_receipt(profile, pick_record=pick)
    second = build_cortex_route_receipt(profile, pick_record=pick)

    assert first["route_count"] == 1
    assert second["route_count"] == 1
    assert first["route_records"][0]["route_hash"] == second[
        "route_records"
    ][0]["route_hash"]
    assert (profile / CORTEX_ROUTE_FILENAME).exists()


def _pick(output_id: str) -> dict[str, object]:
    return {
        "pick_allowed": True,
        "ready_for_next_receipt": True,
        "pick_hash": "pick-hash",
        "action_id": "selected-action",
        "selected_action": {
            "action_id": "selected-action",
            "output_id": output_id,
        },
    }
