from hex_cortex.memory.cortex_channels import evaluate_cortex_channel_candidate
from hex_cortex.memory.cortex_channels import list_cortex_channels
from hex_cortex.memory.cortex_outputs import get_cortex_output
from hex_cortex.memory.cortex_outputs import list_cortex_outputs


def test_output_catalog_has_expected_entries() -> None:
    rows = list_cortex_outputs()
    ids = {row["output_id"] for row in rows}

    assert "write_text" in ids
    assert "write_code" in ids
    assert "write_document" in ids
    assert "write_structured_data" in ids
    assert "generate_plan" in ids
    assert "generate_image" in ids
    assert "generate_video" in ids
    assert "generate_3d_scene" in ids
    assert "render_3d_asset" in ids
    assert "annotate_visual" in ids
    assert "publish_social_content" in ids
    assert "manage_social_inbox" in ids


def test_get_known_output() -> None:
    payload = get_cortex_output("write_code")

    assert payload["state"] == "candidate"
    assert payload["requires_operator"] is False
    assert payload["raw_input_persistence_allowed"] is False


def test_social_publication_requires_operator() -> None:
    payload = get_cortex_output("publish_social_content")

    assert payload["state"] == "candidate"
    assert payload["requires_operator"] is True
    assert payload["raw_input_persistence_allowed"] is False


def test_external_channels_are_cold() -> None:
    rows = list_cortex_channels()

    assert len(rows) == 5
    assert all(row["state"] == "candidate" for row in rows)
    assert all(row["network_calls_enabled"] is False for row in rows)
    assert all(row["content_published"] is False for row in rows)
    assert all(row["messages_read"] is False for row in rows)


def test_external_channel_write_gate() -> None:
    channel_id = str(list_cortex_channels()[0]["channel_id"])
    blocked = evaluate_cortex_channel_candidate(
        channel_id=channel_id,
        mode="write",
        credentials_available=True,
        operator_approved=False,
    )
    ready = evaluate_cortex_channel_candidate(
        channel_id=channel_id,
        mode="write",
        credentials_available=True,
        operator_approved=True,
    )

    assert blocked["candidate_ready"] is False
    assert ready["candidate_ready"] is True
    assert ready["network_call_allowed"] is False
    assert ready["content_published"] is False


def test_unknown_output_is_blocked() -> None:
    payload = get_cortex_output("unknown")

    assert payload["state"] == "blocked"
    assert payload["blocker"] == "unknown_output_capability"
