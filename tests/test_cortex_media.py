from hex_cortex.memory.cortex_media import evaluate_cortex_media_candidate
from hex_cortex.memory.cortex_media import list_cortex_media_providers
from hex_cortex.memory.cortex_media_receipt import CORTEX_MEDIA_RECEIPT_FILENAME
from hex_cortex.memory.cortex_media_receipt import build_cortex_media_receipt
from hex_cortex.memory.cortex_media_receipt import summarize_cortex_media_receipts


def test_media_catalog_covers_image_video_and_3d() -> None:
    rows = list_cortex_media_providers()
    outputs = {
        output_id
        for row in rows
        for output_id in row["supported_outputs"]
    }

    assert "generate_image" in outputs
    assert "generate_video" in outputs
    assert "generate_3d_scene" in outputs
    assert "render_3d_asset" in outputs
    assert all(row["execution_enabled"] is False for row in rows)


def test_local_media_candidate_requires_local_provider() -> None:
    blocked = evaluate_cortex_media_candidate(
        provider_id="local_image_service",
        output_id="generate_image",
        local_available=False,
        credentials_available=False,
        operator_approved=False,
    )
    ready = evaluate_cortex_media_candidate(
        provider_id="local_image_service",
        output_id="generate_image",
        local_available=True,
        credentials_available=False,
        operator_approved=False,
    )

    assert blocked["candidate_ready"] is False
    assert "local_media_provider_unavailable" in blocked["blockers"]
    assert ready["candidate_ready"] is True
    assert ready["generation_performed"] is False


def test_remote_media_candidate_requires_credentials_and_approval() -> None:
    blocked = evaluate_cortex_media_candidate(
        provider_id="remote_media_service",
        output_id="generate_video",
        local_available=False,
        credentials_available=False,
        operator_approved=False,
    )
    ready = evaluate_cortex_media_candidate(
        provider_id="remote_media_service",
        output_id="generate_video",
        local_available=False,
        credentials_available=True,
        operator_approved=True,
    )

    assert blocked["candidate_ready"] is False
    assert "media_credentials_required" in blocked["blockers"]
    assert "operator_approval_required_for_remote_media" in blocked["blockers"]
    assert ready["candidate_ready"] is True
    assert ready["network_call_allowed"] is False


def test_media_receipt_is_ready_without_generation(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    candidate = evaluate_cortex_media_candidate(
        provider_id="local_3d_service",
        output_id="generate_3d_scene",
        local_available=True,
        credentials_available=False,
        operator_approved=False,
    )

    payload = build_cortex_media_receipt(
        profile,
        candidate=candidate,
        request_hash="request-hash",
        source_state_hash="state-hash",
    )

    record = payload["media_receipt_records"][0]
    assert record["media_receipt_allowed"] is True
    assert record["provider_id"] == "local_3d_service"
    assert record["raw_prompt_persisted"] is False
    assert record["raw_media_persisted"] is False
    assert record["generation_performed"] is False
    assert record["network_call_performed"] is False
    assert record["local_process_started"] is False
    assert record["next_action"] == "run_local_media_adapter"

    summary = summarize_cortex_media_receipts(
        profile / CORTEX_MEDIA_RECEIPT_FILENAME
    )
    assert summary["latest_media_receipt_allowed"] is True
    assert summary["latest_output_id"] == "generate_3d_scene"


def test_media_receipt_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    candidate = evaluate_cortex_media_candidate(
        provider_id="local_video_service",
        output_id="generate_video",
        local_available=True,
        credentials_available=False,
        operator_approved=False,
    )
    kwargs = {
        "candidate": candidate,
        "request_hash": "request-hash",
    }

    first = build_cortex_media_receipt(profile, **kwargs)
    second = build_cortex_media_receipt(profile, **kwargs)

    assert first["media_receipt_count"] == 1
    assert second["media_receipt_count"] == 1
    assert first["media_receipt_records"][0]["media_receipt_hash"] == second[
        "media_receipt_records"
    ][0]["media_receipt_hash"]
