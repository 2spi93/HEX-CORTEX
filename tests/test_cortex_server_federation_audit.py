import hashlib

from hex_cortex.memory.cortex_federation_queue import claim_next_federation_task
from hex_cortex.memory.cortex_federation_queue import complete_federation_task
from hex_cortex.memory.cortex_federation_queue import enqueue_federation_task
from hex_cortex.memory.cortex_federation_queue import project_federation_queue
from hex_cortex.memory.cortex_server_federation_audit import FEDERATION_RECEIPTS_FILENAME
from hex_cortex.memory.cortex_server_federation_audit import append_remote_receipt
from hex_cortex.memory.cortex_server_federation_audit import audit_server_federation
from hex_cortex.memory.cortex_server_federation_audit import build_hermes_autodiscovery_plan
from hex_cortex.memory.cortex_server_federation_audit import build_signed_task_envelope
from hex_cortex.memory.cortex_server_federation_audit import summarize_remote_receipts
from hex_cortex.memory.cortex_server_federation_audit import verify_signed_task_envelope


def _envelope():
    return build_signed_task_envelope(
        issuer="hex-cortex.server",
        target="hermes.local",
        capability="code.review",
        payload_ref="object://tasks/123",
        payload_hash=hashlib.sha256(b"bounded context").hexdigest(),
        signing_key=b"test-signing-key",
    )


def test_hermes_plan_preserves_memory_separation_and_detection_order() -> None:
    plan = build_hermes_autodiscovery_plan()

    assert plan["detection_order"] == [
        "mcp",
        "openai_compatible_v1_models",
        "declared_hermes_api",
        "bounded_cli_stdio",
    ]
    assert plan["memory_policy"] == "separate_no_merge"
    assert plan["raw_memory_exchange_allowed"] is False


def test_signed_envelope_detects_tampering() -> None:
    envelope = _envelope()
    valid = verify_signed_task_envelope(envelope, signing_key=b"test-signing-key")
    envelope["capability"] = "code.write"
    tampered = verify_signed_task_envelope(envelope, signing_key=b"test-signing-key")

    assert valid["signature_valid"] is True
    assert tampered["signature_valid"] is False


def test_federation_queue_lifecycle_is_append_only(tmp_path) -> None:
    envelope = _envelope()
    queued = enqueue_federation_task(
        tmp_path,
        envelope=envelope,
        signing_key=b"test-signing-key",
    )
    claimed = claim_next_federation_task(
        tmp_path,
        worker_id="worker.local",
        capabilities=["code.review"],
    )
    completed = complete_federation_task(
        tmp_path,
        envelope_id=envelope["envelope_id"],
        worker_id="worker.local",
        result_status="completed",
        result_hash=hashlib.sha256(b"result").hexdigest(),
    )
    projection = project_federation_queue(tmp_path / "cortex-federation-queue.jsonl")

    assert queued["queue_allowed"] is True
    assert claimed["claim_allowed"] is True
    assert completed["completion_allowed"] is True
    assert projection["event_count"] == 3
    assert projection["closed_count"] == 1
    assert projection["tasks"][envelope["envelope_id"]]["memory_policy"] == "separate_no_merge"


def test_server_federation_audit_is_ready_with_all_facts() -> None:
    facts = {
        "internal_api_available": True,
        "https_reverse_proxy_available": True,
        "private_or_tunneled_transport_available": True,
        "server_worker_queue_available": True,
        "signed_task_envelopes_available": True,
        "remote_receipts_available": True,
        "hermes_autodiscovery_available": True,
        "gtixt_read_only_audit_available": True,
    }

    audit = audit_server_federation(runtime_facts=facts)

    assert audit["federation_allowed"] is True
    assert audit["status"] == "ready"
    assert audit["gtixt"]["mode"] == "read_only"
    assert audit["gtixt"]["memory_import_allowed"] is False
    assert audit["gtixt"]["score_mutation_allowed"] is False


def test_remote_receipt_persists_summary_not_raw_memory(tmp_path) -> None:
    envelope = _envelope()
    result = append_remote_receipt(
        tmp_path,
        envelope=envelope,
        result_status="completed",
        result_summary="review complete",
        source_node="hermes.local",
    )
    summary = summarize_remote_receipts(tmp_path / FEDERATION_RECEIPTS_FILENAME)

    assert result["receipt_record"]["raw_payload_persisted"] is False
    assert result["receipt_record"]["raw_memory_persisted"] is False
    assert summary["total_receipt_count"] == 1
    assert summary["latest_memory_policy"] == "separate_no_merge"
