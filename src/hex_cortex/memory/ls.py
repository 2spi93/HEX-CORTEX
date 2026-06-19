from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

SOURCE_CONTRACT_FILENAME = "cortex-local-model-backend-probe-contract.jsonl"
CORTEX_LOCAL_RUNTIME_PROBE_FILENAME = "cortex-local-runtime-probe-dry-run.jsonl"

_ALLOWED_BACKENDS = {"mock", "ollama", "llama_cpp", "local_openai_compatible_api"}
_LOCAL_HTTP_BACKENDS = {"ollama", "local_openai_compatible_api"}


def build_cortex_local_runtime_probe_dry_run(
    profile: Path,
    *,
    expected_backend: str | None = None,
) -> dict[str, object]:
    contract = _latest_jsonl(profile / SOURCE_CONTRACT_FILENAME)
    blockers = _blockers(contract=contract, expected_backend=expected_backend)
    allowed = not blockers
    probe_contract = _probe_contract(contract) if contract else {}
    selected_backend = _string(probe_contract.get("backend_kind"))
    selected_model = _string(probe_contract.get("model_name"))
    status = "ready" if allowed else "blocked"
    decision = "local_runtime_probe_dry_run_ready" if allowed else "local_runtime_probe_dry_run_blocked"
    next_action = (
        "ready_for_operator_local_probe_execution"
        if allowed
        else "repair_local_runtime_probe_dry_run"
    )
    reasons = (
        [
            "probe_contract_ready",
            "local_only_probe_shape_validated",
            "dry_run_completed_without_runtime_probe",
        ]
        if allowed
        else blockers
    )
    planned_probe = _planned_probe(probe_contract) if allowed else {}
    planned_probe_hash = _stable_hash(planned_probe) if allowed else None
    dry_run_hash = _hash(
        str(profile),
        _string(contract.get("contract_hash") if contract else None) or "missing_contract",
        decision,
        next_action,
        selected_backend or "missing_backend",
        selected_model or "missing_model",
        planned_probe_hash or "missing_planned_probe_hash",
        *reasons,
    )
    record = {
        "runtime_probe_dry_run_id": f"cortex_local_runtime_probe_dry_run_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_probe_contract_hash": contract.get("contract_hash") if contract else None,
        "runtime_probe_dry_run_status": status,
        "runtime_probe_dry_run_decision": decision,
        "runtime_probe_dry_run_allowed": allowed,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "planned_probe": planned_probe,
        "planned_probe_hash": planned_probe_hash,
        "runtime_binding": "none_probe_dry_run_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "local_probe_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "prompt_material_persisted": False,
        "raw_response_persisted": False,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "runtime_probe_dry_run_hash": dry_run_hash,
    }
    path = profile / CORTEX_LOCAL_RUNTIME_PROBE_FILENAME
    records = _load_jsonl(path)
    if not any(row.get("runtime_probe_dry_run_hash") == dry_run_hash for row in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "runtime_probe_dry_run_type": "cortex_local_runtime_probe_dry_run",
        "profile_path": str(profile),
        "runtime_probe_dry_run_path": str(path),
        "runtime_probe_dry_run_count": len(records),
        "runtime_probe_dry_run_records": [record],
    }


def summarize_cortex_local_runtime_probe_dry_runs(path: Path) -> dict[str, object]:
    records = _load_json(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_runtime_probe_dry_run",
        "path": str(path),
        "exists": path.exists(),
        "total_runtime_probe_dry_run_count": len(records),
        "allowed_runtime_probe_dry_run_count": sum(
            1 for row in records if row.get("runtime_probe_dry_run_allowed") is True
        ),
        "latest_runtime_probe_dry_run_status": latest.get("runtime_probe_dry_run_status")
        if latest
        else None,
        "latest_runtime_probe_dry_run_decision": latest.get("runtime_probe_dry_run_decision")
        if latest
        else None,
        "latest_runtime_probe_dry_run_allowed": latest.get("runtime_probe_dry_run_allowed")
        if latest
        else None,
        "latest_selected_backend": latest.get("selected_backend") if latest else None,
        "latest_selected_model": latest.get("selected_model") if latest else None,
        "latest_runtime_binding": latest.get("runtime_binding") if latest else None,
        "latest_model_call_performed": latest.get("model_call_performed") if latest else None,
        "latest_network_call_performed": latest.get("network_call_performed") if latest else None,
        "latest_local_probe_performed": latest.get("local_probe_performed") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_runtime_probe_dry_run_hash": latest.get("runtime_probe_dry_run_hash")
        if latest
        else None,
    }


def _blockers(
    *,
    contract: dict[str, object] | None,
    expected_backend: str | None,
) -> list[str]:
    blockers = []
    if expected_backend is not None and expected_backend not in _ALLOWED_BACKENDS:
        blockers.append("unsupported_expected_backend")
    if not contract:
        blockers.append("missing_probe_contract")
        return blockers
    if contract.get("probe_contract_allowed") is not True:
        blockers.append("probe_contract_not_allowed")
    if contract.get("next_action") != "prepare_local_model_backend_probe_dry_run":
        blockers.append("probe_contract_not_waiting_runtime_probe_dry_run")
    if contract.get("runtime_binding") != "none_probe_contract_only":
        blockers.append("probe_contract_runtime_binding_not_contract_only")
    for flag in (
        "model_call_performed",
        "network_call_performed",
        "local_probe_performed",
        "repo_mutation_performed",
        "shell_execution_performed",
    ):
        if contract.get(flag) is not False:
            blockers.append(f"probe_contract_{flag}_not_false")
    probe_contract = _probe_contract(contract)
    if not probe_contract:
        blockers.append("missing_probe_contract_payload")
        return blockers
    backend = _string(probe_contract.get("backend_kind"))
    if backend not in _ALLOWED_BACKENDS:
        blockers.append("unsupported_backend")
    if expected_backend and backend != expected_backend:
        blockers.append("expected_backend_mismatch")
    if probe_contract.get("prompt_allowed") is not False:
        blockers.append("prompt_not_disabled")
    if probe_contract.get("completion_allowed") is not False:
        blockers.append("completion_not_disabled")
    if probe_contract.get("repo_mutation_allowed") is not False:
        blockers.append("repo_mutation_not_disabled")
    if probe_contract.get("shell_execution_allowed") is not False:
        blockers.append("shell_execution_not_disabled")
    if probe_contract.get("persist_raw_response") is not False:
        blockers.append("raw_response_persistence_not_disabled")
    if backend in _LOCAL_HTTP_BACKENDS and not _local_url(probe_contract.get("base_url")):
        blockers.append("base_url_not_localhost")
    if backend not in _LOCAL_HTTP_BACKENDS and probe_contract.get("base_url") is not None:
        blockers.append("unexpected_base_url_for_non_http_backend")
    return blockers


def _planned_probe(probe_contract: dict[str, object]) -> dict[str, object]:
    return {
        "backend_kind": _string(probe_contract.get("backend_kind")),
        "model_name": _string(probe_contract.get("model_name")),
        "base_url": probe_contract.get("base_url"),
        "model_path": probe_contract.get("model_path"),
        "probe_mode": probe_contract.get("probe_mode"),
        "allowed_probe_surface": probe_contract.get("allowed_probe_surface"),
        "max_probe_timeout_seconds": probe_contract.get("max_probe_timeout_seconds"),
        "prompt_allowed": False,
        "completion_allowed": False,
        "persist_raw_response": False,
        "operator_execution_required": True,
    }


def _probe_contract(contract: dict[str, object]) -> dict[str, object]:
    value = contract.get("probe_contract")
    return value if isinstance(value, dict) else {}


def _local_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith("http://127.0.0.1") or value.startswith("http://localhost")


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _latest_json(path: Path) -> dict[str, object] | None:
    records = _load_json(path)
    return records[-1] if records else None


def _load_json(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    path.write_text(content, encoding="utf-8")


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
