from hex_cortex.memory.cortex_encode import CORTEX_ENCODE_FILENAME
from hex_cortex.memory.cortex_encode import build_cortex_encode_receipt
from hex_cortex.memory.cortex_encode import list_cortex_encoders
from hex_cortex.memory.cortex_encode import summarize_cortex_encode_receipts


def test_encoder_catalog_covers_all_modalities() -> None:
    rows = list_cortex_encoders()
    modalities = {row["modality"] for row in rows}

    assert modalities == {
        "text",
        "image",
        "video",
        "audio",
        "geometry_3d",
    }
    assert all(row["encoding_enabled"] is False for row in rows)
    assert all(
        row["raw_input_persistence_allowed"] is False
        for row in rows
    )


def test_encoder_receipt_is_ready_without_encoding(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_encode_receipt(
        profile,
        encoder_id="geometry_encoder",
        source_hash="geometry-source-hash",
        adapter_available=True,
        embedding_dimensions=1024,
        batch_size=2,
    )

    record = payload["encode_records"][0]
    assert record["encode_allowed"] is True
    assert record["modality"] == "geometry_3d"
    assert record["raw_input_persisted"] is False
    assert record["embedding_persisted"] is False
    assert record["encoding_performed"] is False
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["next_action"] == "run_local_encoder"

    summary = summarize_cortex_encode_receipts(
        profile / CORTEX_ENCODE_FILENAME
    )
    assert summary["latest_encode_allowed"] is True
    assert summary["latest_modality"] == "geometry_3d"


def test_encoder_receipt_blocks_missing_adapter(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_encode_receipt(
        profile,
        encoder_id="image_encoder",
        source_hash="image-source-hash",
        adapter_available=False,
        embedding_dimensions=768,
    )

    record = payload["encode_records"][0]
    assert record["encode_allowed"] is False
    assert "encoder_adapter_unavailable" in record["blockers"]


def test_encoder_receipt_blocks_invalid_dimensions(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_encode_receipt(
        profile,
        encoder_id="video_encoder",
        source_hash="video-source-hash",
        adapter_available=True,
        embedding_dimensions=0,
        batch_size=0,
    )

    record = payload["encode_records"][0]
    assert record["encode_allowed"] is False
    assert "embedding_dimensions_out_of_range" in record["blockers"]
    assert "encoder_batch_size_out_of_range" in record["blockers"]


def test_encoder_receipt_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "encoder_id": "text_encoder",
        "source_hash": "text-source-hash",
        "adapter_available": True,
        "embedding_dimensions": 512,
    }

    first = build_cortex_encode_receipt(profile, **kwargs)
    second = build_cortex_encode_receipt(profile, **kwargs)

    assert first["encode_count"] == 1
    assert second["encode_count"] == 1
    assert first["encode_records"][0]["encode_receipt_hash"] == second[
        "encode_records"
    ][0]["encode_receipt_hash"]
