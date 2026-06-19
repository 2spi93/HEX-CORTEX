from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

FEDERATION_RECEIPTS_FILENAME = "cortex-federation-receipts.jsonl"
_HERMES_DETECTION_ORDER = (
    "mcp",
    "openai_compatible_v1_models",
    "declared_hermes_api",
    "bounded_cli_stdio",
)
_GTIXT_READ_ONLY_CAPABILITIES = (
    "gtixt.health",
    "gtixt.runtime_summary",
    "gtixt.current_blockers",
    "gtixt.latest_artifacts",
    "gtixt.evidence_coverage",
    "gtixt.open_tasks",
    "gtixt.capability_map",
)


def build_hermes_autodiscovery_plan() -> dict[str, object]:
    return {
        "plan_type": "hermes_autodiscovery_plan",
        "detection_order": list(_HERMES_DETECTION_ORDER),
        "local_adapter_id": "hermes.local",
        "server_adapter_id": "hermes.server",
        "memory_policy": "separate_no_merge",
        "exchange_contract": [
            "task_envelope",
            "capability_request",
            "bounded_context_ref",
            "result",
            "receipt",
        ],
        "raw_memory_exchange_allowed": False,
        "next_action": "run_declared_transport_probes",
    }


def build_signed_task_envelope(
    *,
    issuer: str,
    target: str,
    capability: str,
    payload_ref: str,
    payload_hash: str,
    signing_key: bytes,
    expires_at: str | None = None,
) -> dict[str, object]:
    for label, value in {
        "issuer": issuer,
        "target": target,
        "capability": capability,
        "payload_ref": payload_ref,
        "payload_hash": payload_hash,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if len(payload_hash) != 64 or any(char not in "0123456789abcdef" for char in payload_hash.lower()):
        raise ValueError("payload_hash must be a sha256 hex digest")
    if not signing_key:
        raise ValueError("signing_key must be non-empty")
    unsigned = {
        "envelope_id": f"cortex_task_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at,
        "issuer": issuer,
        "target": target,
        "capability": capability,
        "payload_ref": payload_ref,
        "payload_hash": payload_hash.lower(),
        "memory_policy": "separate_no_merge",
        "bounded_context_only": True,
        "raw_memory_exchange_allowed": False,
    }
    signature = hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    return {
        **unsigned,
        "signature_algorithm": "hmac-sha256",
        "signature": signature,
    }


def verify_signed_task_envelope(
    envelope: dict[str, object],
    *,
    signing_key: bytes,
) -> dict[str, object]:
    signature = envelope.get("signature")
    unsigned = {
        key: value
        for key, value in envelope.items()
        if key not in {"signature", "signature_algorithm"}
    }
    expected = hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    valid = (
        isinstance(signature, str)
        and hmac.compare_digest(signature, expected)
        and envelope.get("memory_policy") == "separate_no_merge"
        and envelope.get("raw_memory_exchange_allowed") is False
    )
    return {
        "verification_type": "signed_task_envelope_verification",
        "envelope_id": envelope.get("envelope_id"),
        "signature_valid": valid,
        "memory_separation_valid": envelope.get("memory_policy") == "separate_no_merge",
        "raw_memory_exchange_allowed": envelope.get("raw_memory_exchange_allowed"),
        "blockers": [] if valid else ["task_envelope_verification_failed"],
    }


def audit_server_federation(
    *,
    runtime_facts: dict[str, bool] | None = None,
) -> dict[str, object]:
    facts = dict(runtime_facts or {})
    required = {
        "internal_api_available": "internal_api_not_available",
        "https_reverse_proxy_available": "https_reverse_proxy_not_available",
        "private_or_tunneled_transport_available": "private_or_tunneled_transport_not_available",
        "server_worker_queue_available": "server_worker_queue_not_available",
        "signed_task_envelopes_available": "signed_task_envelopes_not_available",
        "remote_receipts_available": "remote_receipts_not_available",
        "hermes_autodiscovery_available": "hermes_autodiscovery_not_available",
        "gtixt_read_only_audit_available": "gtixt_read_only_audit_not_available",
    }
    blockers = [blocker for fact, blocker in required.items() if facts.get(fact) is not True]
    service_health = {
        "internal_api": facts.get("internal_api_available") is True,
        "https_reverse_proxy": facts.get("https_reverse_proxy_available") is True,
        "private_or_tunneled_transport": facts.get("private_or_tunneled_transport_available") is True,
        "server_worker_queue": facts.get("server_worker_queue_available") is True,
        "hermes_autodiscovery": facts.get("hermes_autodiscovery_available") is True,
        "gtixt_read_only": facts.get("gtixt_read_only_audit_available") is True,
    }
    return {
        "audit_type": "server_federation_audit_v1",
        "status": "ready" if not blockers else "blocked",
        "federation_allowed": not blockers,
        "service_health": service_health,
        "hermes": build_hermes_autodiscovery_plan(),
        "gtixt": {
            "mode": "read_only",
            "allowed_capabilities": list(_GTIXT_READ_ONLY_CAPABILITIES),
            "memory_import_allowed": False,
            "predictor_duplication_allowed": False,
            "canonical_ledger_duplication_allowed": False,
            "score_mutation_allowed": False,
            "publication_allowed": False,
        },
        "task_envelope_policy": {
            "signature_required": True,
            "bounded_context_only": True,
            "memory_policy": "separate_no_merge",
            "payload_hash_required": True,
        },
        "runtime_facts": facts,
        "blockers": blockers,
        "next_action": "operate_federation" if not blockers else "configure_federation_services",
    }


def append_remote_receipt(
    profile: Path,
    *,
    envelope: dict[str, object],
    result_status: str,
    result_summary: str,
    source_node: str,
) -> dict[str, object]:
    if result_status not in {"completed", "blocked", "failed"}:
        raise ValueError("result_status must be completed, blocked, or failed")
    summary = result_summary[:500]
    record = {
        "receipt_id": f"cortex_remote_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "envelope_id": envelope.get("envelope_id"),
        "issuer": envelope.get("issuer"),
        "target": envelope.get("target"),
        "capability": envelope.get("capability"),
        "source_node": source_node,
        "result_status": result_status,
        "result_summary": summary,
        "result_hash": hashlib.sha256(summary.encode("utf-8")).hexdigest(),
        "raw_payload_persisted": False,
        "raw_memory_persisted": False,
        "memory_policy": "separate_no_merge",
    }
    path = profile / FEDERATION_RECEIPTS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {
        "receipt_type": "remote_federation_receipt",
        "receipt_path": str(path),
        "receipt_record": record,
    }


def summarize_remote_receipts(path: Path) -> dict[str, object]:
    rows = []
    if path.exists():
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "remote_federation_receipts",
        "path": str(path),
        "exists": path.exists(),
        "total_receipt_count": len(rows),
        "latest_envelope_id": latest.get("envelope_id") if latest else None,
        "latest_result_status": latest.get("result_status") if latest else None,
        "latest_memory_policy": latest.get("memory_policy") if latest else None,
    }


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
