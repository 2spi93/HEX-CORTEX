from hex_cortex.memory.cortex_modal_receipt import CORTEX_MODAL_RECEIPT_FILENAME
from hex_cortex.memory.cortex_modal_receipt import build_cortex_modal_receipt
from hex_cortex.memory.cortex_modal_receipt import summarize_cortex_modal_receipts


def test_modal_receipt_imports() -> None:
    assert CORTEX_MODAL_RECEIPT_FILENAME == "cortex-modal-receipt.jsonl"


def test_modal_receipt_ready_for_screen(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_modal_receipt(
        profile,
        capability_id="screen_vision",
        operator_approved=True,
    )

    record = payload["modal_receipt_records"][0]
    assert record["modal_allowed"] is True
    assert record["modal_status"] == "ready"
    assert record["capability_id"] == "screen_vision"
    assert record["operator_approved"] is True
    assert record["capture_performed"] is False
    assert record["audio_performed"] is False
    assert record["camera_performed"] is False
    assert record["screen_performed"] is False
    assert record["raw_input_saved"] is False
    assert record["raw_input_persistence_allowed"] is False
    assert record["next_action"] == "candidate_adapter_receipt"

    summary = summarize_cortex_modal_receipts(profile / CORTEX_MODAL_RECEIPT_FILENAME)
    assert summary["latest_modal_allowed"] is True
    assert summary["latest_capability_id"] == "screen_vision"


def test_modal_receipt_blocks_without_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_modal_receipt(
        profile,
        capability_id="camera_vision",
        operator_approved=False,
    )

    record = payload["modal_receipt_records"][0]
    assert record["modal_allowed"] is False
    assert "operator_approval_required" in record["blockers"]


def test_modal_receipt_blocks_unknown_capability(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_modal_receipt(
        profile,
        capability_id="unknown",
        operator_approved=True,
    )

    record = payload["modal_receipt_records"][0]
    assert record["modal_allowed"] is False
    assert "unknown_multimodal_capability" in record["blockers"]
