from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_FIRST_LOCAL_MODEL_DRY_RUN_FILENAME = "cortex-first-local-model-dry-run.jsonl"
LOCAL_MODEL_CONTRACT_FILENAME = "cortex-local-model-backend-adapter-contract.jsonl"

_DEFAULT_TASK_TEXT = "Use the local compact expert contract to produce advisory planning output only."
_DEFAULT_SYSTEM_CONTRACT = "HEX-CORTEX local model dry run: advisory only, no repo mutation, no shell, no network."


def build_cortex_first_local_model_dry_run(
    profile: Path,
    *,
    task_text: str = _DEFAULT_TASK_TEXT,
    selected_skill_key: str | None = None,
    backend_kind: str = "mock",
) -> dict[str, object]:
    contract = _latest_jsonl(profile / LOCAL_MODEL_CONTRACT_FILENAME)
    blockers = _blockers(contract, backend_kind)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "first_local_model_dry_run_ready" if allowed else "first_local_model_dry_run_blocked"
    next_action = "prepare_local_model_advice_cli" if allowed else "repair_first_local_model_dry_run"
    reasons = ["local_model_contract_ready", "mock_backend_selected", "dry_run_completed_without_model_call"] if allowed else blockers

    request = _request_payload(profile, task_text=task_text, selected_skill_key=selected_skill_key, backend_kind=backend_kind)
    response = _mock_response(request) if allowed else {}
    request_hash = _stable_hash(request)
    response_hash = _stable_hash(response) if response else None
    run_hash = _hash(str(profile), str(contract.get("contract_hash") if contract else "missing_contract"), request_hash, str(response_hash), decision, next_action, *reasons)

    record = {
        "dry_run_id": f"cortex_first_local_model_dry_run_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_contract_hash": contract.get("contract_hash") if contract else None,
        "dry_run_status": status,
        "dry_run_decision": decision,
        "dry_run_allowed": allowed,
        "backend_kind": backend_kind,
        "backend_status": response.get("backend_status") if response else "blocked",
        "model_call_performed": False,
        "network_call_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "request_hash": request_hash,
        "response_hash": response_hash,
        "request_preview": request if allowed else {},
        "response_preview": response,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "dry_run_hash": run_hash,
    }

    path = profile / CORTEX_FIRST_LOCAL_MODEL_DRY_RUN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("dry_run_hash") == run_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "dry_run_type": "cortex_first_local_model_dry_run",
        "profile_path": str(profile),
        "dry_run_path": str(path),
        "dry_run_count": len(records),
        "dry_run_records": [record],
    }


def summarize_cortex_first_local_model_dry_runs(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_first_local_model_dry_run",
        "path": str(path),
        "exists": path.exists(),
        "total_dry_run_count": len(records),
        "allowed_dry_run_count": sum(1 for item in records if item.get("dry_run_allowed") is True),
        "latest_dry_run_status": latest.get("dry_run_status") if latest else None,
        "latest_dry_run_decision": latest.get("dry_run_decision") if latest else None,
        "latest_dry_run_allowed": latest.get("dry_run_allowed") if latest else None,
        "latest_backend_kind": latest.get("backend_kind") if latest else None,
        "latest_backend_status": latest.get("backend_status") if latest else None,
        "latest_model_call_performed": latest.get("model_call_performed") if latest else None,
        "latest_repo_mutation_performed": latest.get("repo_mutation_performed") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_dry_run_hash": latest.get("dry_run_hash") if latest else None,
    }


def _request_payload(profile: Path, *, task_text: str, selected_skill_key: str | None, backend_kind: str) -> dict[str, object]:
    return {
        "request_id": f"cortex_local_model_request_{uuid4().hex}",
        "profile_path": str(profile),
        "backend_kind": backend_kind,
        "task_text": task_text,
        "system_contract": _DEFAULT_SYSTEM_CONTRACT,
        "context_packet": "dry_run_context_packet_empty",
        "selected_skill_key": selected_skill_key,
        "safety_mode": "advisory_only",
    }


def _mock_response(request: dict[str, object]) -> dict[str, object]:
    return {
        "response_id": f"cortex_local_model_response_{uuid4().hex}",
        "backend_status": "ready",
        "answer": "Mock local compact expert dry run completed. Produce advisory guidance only; require receipts before any future mutation.",
        "confidence": 0.74,
        "risk_flags": [],
        "raw_response_hash": _stable_hash({"mock_answer": request.get("task_text"), "backend_kind": request.get("backend_kind")}),
        "next_action": "prepare_local_model_advice_cli",
    }


def _blockers(contract: dict[str, object] | None, backend_kind: str) -> list[str]:
    blockers = []
    if not contract:
        blockers.append("missing_local_model_backend_adapter_contract")
        return blockers
    if contract.get("contract_allowed") is not True:
        blockers.append("local_model_contract_not_allowed")
    if contract.get("next_action") != "prepare_first_local_model_dry_run":
        blockers.append("local_model_contract_not_waiting_first_dry_run")
    if contract.get("default_backend") != "mock":
        blockers.append("default_backend_not_mock")
    if backend_kind != "mock":
        blockers.append("non_mock_backend_requires_future_explicit_config")
    if contract.get("execution_policy") != "advisory_only_no_repo_mutation_no_shell":
        blockers.append("unexpected_execution_policy")
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


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
