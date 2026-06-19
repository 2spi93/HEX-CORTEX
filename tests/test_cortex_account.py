from hex_cortex.memory.cortex_account import CORTEX_ACCOUNT_FILENAME
from hex_cortex.memory.cortex_account import build_cortex_account_receipt
from hex_cortex.memory.cortex_account import summarize_cortex_account_receipts
from hex_cortex.memory.cortex_channels import evaluate_cortex_channel_candidate
from hex_cortex.memory.cortex_channels import list_cortex_channels


def test_read_account_receipt_is_ready_without_network(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    channel_id = str(list_cortex_channels()[0]["channel_id"])
    candidate = evaluate_cortex_channel_candidate(
        channel_id=channel_id,
        mode="read",
        credentials_available=True,
        operator_approved=False,
    )

    payload = build_cortex_account_receipt(
        profile,
        candidate=candidate,
        account_ref_hash="account-ref-hash",
        scopes=["read_profile", "read_profile"],
        callback_mode="polling",
    )

    record = payload["account_records"][0]
    assert record["account_allowed"] is True
    assert record["scopes"] == ["read_profile"]
    assert record["credential_persisted"] is False
    assert record["secret_persisted"] is False
    assert record["network_call_performed"] is False
    assert record["messages_read"] is False
    assert record["next_action"] == "run_account_read_probe"

    summary = summarize_cortex_account_receipts(
        profile / CORTEX_ACCOUNT_FILENAME
    )
    assert summary["latest_account_allowed"] is True
    assert summary["latest_mode"] == "read"


def test_write_account_receipt_requires_ready_candidate(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    channel_id = str(list_cortex_channels()[0]["channel_id"])
    candidate = evaluate_cortex_channel_candidate(
        channel_id=channel_id,
        mode="write",
        credentials_available=True,
        operator_approved=True,
    )

    payload = build_cortex_account_receipt(
        profile,
        candidate=candidate,
        account_ref_hash="account-ref-hash",
        scopes=["write_content"],
        callback_mode="webhook",
    )

    record = payload["account_records"][0]
    assert record["account_allowed"] is True
    assert record["content_published"] is False
    assert record["next_action"] == "prepare_account_write_adapter"


def test_account_receipt_blocks_invalid_candidate_and_scopes(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    candidate = {
        "candidate_ready": False,
        "channel_id": "unknown",
        "mode": "read",
        "network_call_allowed": False,
    }

    payload = build_cortex_account_receipt(
        profile,
        candidate=candidate,
        account_ref_hash="",
        scopes=[],
        callback_mode="invalid",
    )

    record = payload["account_records"][0]
    assert record["account_allowed"] is False
    assert "account_candidate_not_ready" in record["blockers"]
    assert "missing_account_reference_hash" in record["blockers"]
    assert "account_scopes_invalid" in record["blockers"]
    assert "account_callback_mode_invalid" in record["blockers"]


def test_account_receipt_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    channel_id = str(list_cortex_channels()[0]["channel_id"])
    candidate = evaluate_cortex_channel_candidate(
        channel_id=channel_id,
        mode="read",
        credentials_available=True,
        operator_approved=False,
    )
    kwargs = {
        "candidate": candidate,
        "account_ref_hash": "account-ref-hash",
        "scopes": ["read_profile"],
    }

    first = build_cortex_account_receipt(profile, **kwargs)
    second = build_cortex_account_receipt(profile, **kwargs)

    assert first["account_count"] == 1
    assert second["account_count"] == 1
    assert first["account_records"][0]["account_receipt_hash"] == second[
        "account_records"
    ][0]["account_receipt_hash"]
