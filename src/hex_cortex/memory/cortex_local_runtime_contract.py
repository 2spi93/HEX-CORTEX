from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_local_model_backend_config_dry_run import (
    CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME,
)

CORTEX_LOCAL_MODEL_BACKEND_PROBE_CONTRACT_FILENAME = (
    "cortex-local-model-backend-probe-contract.jsonl"
)

_ALLOWED_BACKENDS = {"mock", "ollama", "llama_cpp", "local_openai_compatible_api"}
_LOCAL_HTTP_BACKENDS = {"ollama", "local_openai_compatible_api"}


def build_cortex_local_model_backend_probe_contract(
    profile: Path,
    *,
    expected_backend: str | None = None,
) -> dict[str, object]:
    dry_run = _latest_jsonl(profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME)
    blockers = _blockers(dry_run=dry_run, expected_backend=expected_backend)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = (
        "local_model_backend_probe_contract_ready"
        if allowed
        else "local_model_backend_probe_contract_blocked"
    )
    next_action = (
        "prepare_local_model_backend_probe_dry_run"
        if allowed
        else "repair_local_model_backend_probe_contract"
    )
    validated_config = _validated_config(dry_run) if dry_run else {}
    selected_backend = _string(validated_config.get("backend_kind"))
    selected_model = _string(validated_config.get("model_name"))
    probe_contract = _probe_contract(validated_config) if allowed else {}
    probe_contract_hash = _stable_hash(probe_contract) if allowed else None
    reasons = (
        [
            "config_dry_run_ready",
            "probe_contract_declared",
            "localhost_probe_only",
            "no_probe_performed",
        ]
        if allowed
        else blockers
    )
    contract_hash = _hash(
        str(profile),
        _string(dry_run.get("config_dry_run_hash") if dry_run else None) or "missing_dry_run",
        decision,
        next_action,
        selected_backend or "missing_backend",
        selected_model or "missing_model",
        probe_contract_hash or "missing_probe_contract_hash",
        *reasons,
    )
    record = {
        "probe_contract_id": f"cortex_local_model_backend_probe_contract_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_config_dry_run_hash": dry_run.get("config_dry_run_hash") if dry_run else None,
        "probe_contract_status": status,
        "probe_contract_decision": decision,
        "probe_contract_allowed": allowed,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "validated_config_hash": dry_run.get("validated_config_hash") if dry_run else None,
        "probe_contract": probe_contract,
        "probe_contract_hash": probe_contract_hash,
        "runtime_binding": "none_probe_contract_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "local_probe_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "probe_policy": "contract_only_no_probe_until_next_dry_run",
        "redaction_policy": "never_persist_prompt_or_secret_material",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "contract_hash": contract_hash,
    }
    path = profile / CORTEX_LOCAL_MODEL_BACKEND_PROBE_CONTRACT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("contract_hash") == contract_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "probe_contract_type": "cortex_local_model_backend_probe_contract",
        "profile_path": str(profile),
        "probe_contract_path": str(path),
        "probe_contract_count": len(records),
        "probe_contract_records": [record],
    }


def summarize_cortex_local_model_backend_probe_contracts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_model_backend_probe_contract",
        "path": str(path),
        "exists": path.exists(),
        "total_probe_contract_count": len(records),
        "allowed_probe_contract_count": sum(
            1 for item in records if item.get("probe_contract_allowed") is True
        ),
        "latest_probe_contract_status": latest.get("probe_contract_status") if latest else None,
        "latest_probe_contract_decision": latest.get("probe_contract_decision") if latest else None,
        "latest_probe_contract_allowed": latest.get("probe_contract_allowed") if latest else None,
        "latest_selected_backend": latest.get("selected_backend") if latest else None,
        "latest_selected_model": latest.get("selected_model") if latest else None,
        "latest_runtime_binding": latest.get("runtime_binding") if latest else None,
        "latest_model_call_performed": latest.get("model_call_performed") if latest else None,
        "latest_network_call_performed": latest.get("network_call_performed") if latest else None,
        "latest_local_probe_performed": latest.get("local_probe_performed") if latest else None,
        "latest_repo_mutation_performed": latest.get("repo_mutation_performed")
        if latest
        else None,
        "latest_shell_execution_performed": latest.get("shell_execution_performed")
        if latest
        else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_contract_hash": latest.get("contract_hash") if latest else None,
    }


def _blockers(
    *,
    dry_run: dict[str, object] | None,
    expected_backend: str | None,
) -> list[str]:
    blockers = []
    if expected_backend is not None and expected_backend not in _ALLOWED_BACKENDS:
        blockers.append("unsupported_expected_backend")
    if not dry_run:
        blockers.append("missing_local_model_backend_config_dry_run")
        return blockers
    if dry_run.get("config_dry_run_allowed") is not True:
        blockers.append("config_dry_run_not_allowed")
    if dry_run.get("next_action") != "prepare_local_model_backend_probe_contract":
        blockers.append("config_dry_run_not_waiting_probe_contract")
    if dry_run.get("runtime_binding") != "none_config_dry_run_only":
        blockers.append("config_dry_run_runtime_binding_not_dry_run_only")
    for flag in (
        "model_call_performed",
        "network_call_performed",
        "local_probe_performed",
        "repo_mutation_performed",
        "shell_execution_performed",
    ):
        if dry_run.get(flag) is not False:
            blockers.append(f"config_dry_run_{flag}_not_false")
    config = _validated_config(dry_run)
    if not config:
        blockers.append("missing_validated_config")
        return blockers
    backend = _string(config.get("backend_kind"))
    if backend not in _ALLOWED_BACKENDS:
        blockers.append("unsupported_backend")
    if expected_backend and backend != expected_backend:
        blockers.append("expected_backend_mismatch")
    if config.get("localhost_only") is not True:
        blockers.append("localhost_only_not_true")
    if backend in _LOCAL_HTTP_BACKENDS and not _local_url(config.get("base_url")):
        blockers.append("base_url_not_localhost")
    if backend not in _LOCAL_HTTP_BACKENDS and config.get("base_url") is not None:
        blockers.append("unexpected_base_url_for_non_http_backend")
    if config.get("repo_mutation_allowed") is not False:
        blockers.append("repo_mutation_not_disabled")
    if config.get("shell_execution_allowed") is not False:
        blockers.append("shell_execution_not_disabled")
    return blockers


def _probe_contract(config: dict[str, object]) -> dict[str, object]:
    backend = _string(config.get("backend_kind"))
    local_http = backend in _LOCAL_HTTP_BACKENDS
    return {
        "contract_version": "local_backend_probe_contract_v1",
        "backend_kind": backend,
        "model_name": _string(config.get("model_name")),
        "base_url": config.get("base_url") if local_http else None,
        "model_path": config.get("model_path"),
        "probe_mode": "metadata_or_health_only",
        "allowed_probe_surface": "localhost_http_only" if local_http else "metadata_only",
        "max_probe_timeout_seconds": min(float(config.get("timeout_seconds", 8.0)), 8.0),
        "prompt_allowed": False,
        "completion_allowed": False,
        "repo_mutation_allowed": False,
        "shell_execution_allowed": False,
        "persist_raw_response": False,
    }


def _validated_config(dry_run: dict[str, object]) -> dict[str, object]:
    value = dry_run.get("validated_config")
    return value if isinstance(value, dict) else {}


def _local_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith("http://127.0.0.1") or value.startswith("http://localhost")


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    records = _load_jsonl(path)
    return records[-1] if records else None


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    path.write_text(content, encoding="utf-8")


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
