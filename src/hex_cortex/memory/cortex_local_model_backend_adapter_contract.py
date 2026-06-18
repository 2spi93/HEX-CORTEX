from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME = "cortex-local-model-backend-adapter-contract.jsonl"
V14_EVALUATION_HARNESS_FILENAME = "cortex-v14-evaluation-harness.jsonl"

_BACKEND_INTERFACE = {
    "backend_kind": "ollama|llama_cpp|local_openai_compatible_api|mock",
    "model_name": "string",
    "context_window": "int",
    "max_output_tokens": "int",
    "temperature": "float",
    "timeout_seconds": "float",
    "offline_allowed": "bool",
}

_REQUEST_SCHEMA = {
    "request_id": "string",
    "task_text": "string",
    "system_contract": "string",
    "context_packet": "string",
    "selected_skill_key": "string|null",
    "safety_mode": "advisory_only",
}

_RESPONSE_SCHEMA = {
    "response_id": "string",
    "backend_status": "ready|blocked|timeout|error",
    "answer": "string",
    "confidence": "float[0,1]",
    "risk_flags": "list[string]",
    "raw_response_hash": "string",
    "next_action": "string",
}


def build_cortex_local_model_backend_adapter_contract(profile: Path) -> dict[str, object]:
    harness = _latest_jsonl(profile / V14_EVALUATION_HARNESS_FILENAME)
    blockers = _blockers(harness)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "local_model_backend_adapter_contract_ready" if allowed else "local_model_backend_adapter_contract_blocked"
    next_action = "prepare_first_local_model_dry_run" if allowed else "repair_local_model_backend_adapter_contract"
    reasons = ["evaluation_harness_ready", "backend_interface_defined", "dry_run_contract_ready"] if allowed else blockers
    contract_hash = _hash(
        str(profile),
        str(harness.get("harness_hash") if harness else "missing_harness"),
        decision,
        next_action,
        json.dumps(_BACKEND_INTERFACE, sort_keys=True),
        json.dumps(_REQUEST_SCHEMA, sort_keys=True),
        json.dumps(_RESPONSE_SCHEMA, sort_keys=True),
        *reasons,
    )
    record = {
        "contract_id": f"cortex_local_model_backend_adapter_contract_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_harness_hash": harness.get("harness_hash") if harness else None,
        "contract_status": status,
        "contract_decision": decision,
        "contract_allowed": allowed,
        "backend_interface": _BACKEND_INTERFACE if allowed else {},
        "request_schema": _REQUEST_SCHEMA if allowed else {},
        "response_schema": _RESPONSE_SCHEMA if allowed else {},
        "supported_initial_backends": ["mock", "ollama", "llama_cpp", "local_openai_compatible_api"] if allowed else [],
        "default_backend": "mock",
        "binding_policy": "mock_first_real_backend_requires_explicit_local_config",
        "execution_policy": "advisory_only_no_repo_mutation_no_shell",
        "offline_policy": "must_fail_closed_when_backend_unavailable",
        "receipt_policy": "persist_request_response_hashes_before_reuse",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "contract_hash": contract_hash,
    }
    path = profile / CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("contract_hash") == contract_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"contract_type": "cortex_local_model_backend_adapter_contract", "profile_path": str(profile), "contract_path": str(path), "contract_count": len(records), "contract_records": [record]}


def summarize_cortex_local_model_backend_adapter_contracts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_model_backend_adapter_contract",
        "path": str(path),
        "exists": path.exists(),
        "total_contract_count": len(records),
        "allowed_contract_count": sum(1 for item in records if item.get("contract_allowed") is True),
        "latest_contract_status": latest.get("contract_status") if latest else None,
        "latest_contract_decision": latest.get("contract_decision") if latest else None,
        "latest_contract_allowed": latest.get("contract_allowed") if latest else None,
        "latest_default_backend": latest.get("default_backend") if latest else None,
        "latest_binding_policy": latest.get("binding_policy") if latest else None,
        "latest_execution_policy": latest.get("execution_policy") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_contract_hash": latest.get("contract_hash") if latest else None,
    }


def _blockers(harness: dict[str, object] | None) -> list[str]:
    blockers = []
    if not harness:
        blockers.append("missing_v14_evaluation_harness")
        return blockers
    if harness.get("harness_allowed") is not True:
        blockers.append("v14_evaluation_harness_not_allowed")
    if harness.get("next_action") != "prepare_local_model_backend_adapter_contract":
        blockers.append("v14_evaluation_harness_not_waiting_backend_adapter_contract")
    if harness.get("model_runtime_binding_allowed") is not False:
        blockers.append("evaluation_harness_model_binding_not_closed")
    return blockers


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    records = _load_jsonl(path)
    return records[-1] if records else None


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
