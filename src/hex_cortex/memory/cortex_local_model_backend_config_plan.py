from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME = "cortex-local-model-backend-config-plan.jsonl"
CORTEX_LOCAL_MODEL_ADVICE_FILENAME = "cortex-local-model-advice.jsonl"
CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME = "cortex-local-model-backend-adapter-contract.jsonl"

_SUPPORTED_BACKENDS = ["mock", "ollama", "llama_cpp", "local_openai_compatible_api"]
_DEFAULT_BACKEND = "mock"
_DEFAULT_MODEL_BY_BACKEND = {
    "mock": "mock-null-model",
    "ollama": "qwen2.5-coder:7b-instruct",
    "llama_cpp": "local-gguf-model",
    "local_openai_compatible_api": "local-openai-compatible-model",
}
_BACKEND_PROFILES: dict[str, dict[str, object]] = {
    "mock": {
        "runtime_surface": "in_process_deterministic_stub",
        "endpoint_policy": "none",
        "network_policy": "network_not_required",
        "activation_policy": "enabled_for_contract_validation_only",
        "health_probe": "not_required_for_mock",
    },
    "ollama": {
        "runtime_surface": "local_http_api",
        "endpoint_policy": "localhost_only_default_127_0_0_1_11434",
        "network_policy": "localhost_only_after_explicit_operator_config",
        "activation_policy": "disabled_until_config_dry_run_passes",
        "health_probe": "GET /api/tags or equivalent local probe in future dry run",
    },
    "llama_cpp": {
        "runtime_surface": "local_process_or_local_server",
        "endpoint_policy": "local_path_or_localhost_only",
        "network_policy": "network_not_required_when_using_direct_local_binary",
        "activation_policy": "disabled_until_binary_or_server_config_is_validated",
        "health_probe": "load_metadata_or_local_server_health_in_future_dry_run",
    },
    "local_openai_compatible_api": {
        "runtime_surface": "local_http_api_openai_compatible",
        "endpoint_policy": "localhost_only_base_url_required",
        "network_policy": "localhost_only_after_explicit_operator_config",
        "activation_policy": "disabled_until_base_url_and_model_are_validated",
        "health_probe": "GET /v1/models or equivalent local probe in future dry run",
    },
}
_CONFIG_SCHEMA = {
    "backend_kind": "mock|ollama|llama_cpp|local_openai_compatible_api",
    "model_name": "string",
    "base_url": "string|null",
    "model_path": "string|null",
    "context_window": "int",
    "max_output_tokens": "int",
    "temperature": "float",
    "timeout_seconds": "float",
    "localhost_only": "bool",
    "repo_mutation_allowed": "false",
    "shell_execution_allowed": "false",
    "network_required": "bool",
}
_SAFE_DEFAULTS = {
    "context_window": 4096,
    "max_output_tokens": 768,
    "temperature": 0.2,
    "timeout_seconds": 8.0,
    "localhost_only": True,
    "repo_mutation_allowed": False,
    "shell_execution_allowed": False,
    "fail_closed_on_error": True,
}


def build_cortex_local_model_backend_config_plan(
    profile: Path,
    *,
    preferred_backend: str = _DEFAULT_BACKEND,
    model_name: str | None = None,
) -> dict[str, object]:
    advice = _latest_jsonl(profile / CORTEX_LOCAL_MODEL_ADVICE_FILENAME)
    contract = _latest_jsonl(profile / CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME)
    blockers = _blockers(advice=advice, contract=contract, preferred_backend=preferred_backend)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "local_model_backend_config_plan_ready" if allowed else "local_model_backend_config_plan_blocked"
    next_action = "prepare_local_model_backend_config_dry_run" if allowed else "repair_local_model_backend_config_plan"
    selected_backend = preferred_backend if preferred_backend in _SUPPORTED_BACKENDS else None
    selected_model = model_name or (_DEFAULT_MODEL_BY_BACKEND[selected_backend] if selected_backend else None)
    reasons = (
        [
            "local_model_advice_ready",
            "backend_adapter_contract_ready",
            "allowed_backends_declared",
            "mock_remains_default",
            "real_backends_require_explicit_dry_run",
        ]
        if allowed
        else blockers
    )
    source_hashes = {
        "advice_hash": _field(advice, "record_hash") or _field(advice, "advice_hash"),
        "contract_hash": _field(contract, "contract_hash"),
    }
    config_preview = _config_preview(selected_backend, selected_model) if allowed else {}
    backend_profiles = _backend_profiles() if allowed else []
    plan_hash = _hash(
        str(profile),
        decision,
        next_action,
        str(selected_backend),
        str(selected_model),
        json.dumps(source_hashes, sort_keys=True),
        json.dumps(config_preview, sort_keys=True),
        *reasons,
    )
    record = {
        "config_plan_id": f"cortex_local_model_backend_config_plan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_hashes": source_hashes,
        "config_plan_status": status,
        "config_plan_decision": decision,
        "config_plan_allowed": allowed,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "default_backend": _DEFAULT_BACKEND,
        "allowed_backends": _SUPPORTED_BACKENDS if allowed else [],
        "backend_profiles": backend_profiles,
        "config_schema": _CONFIG_SCHEMA if allowed else {},
        "safe_defaults": _SAFE_DEFAULTS if allowed else {},
        "config_preview": config_preview,
        "runtime_binding": "none_config_plan_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "binding_policy": "mock_default_real_backend_requires_explicit_local_config_and_dry_run",
        "network_policy": _network_policy(selected_backend) if allowed else None,
        "execution_policy": "advisory_only_no_repo_mutation_no_shell",
        "receipt_policy": "persist_config_hash_before_backend_probe",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "config_plan_hash": plan_hash,
    }
    path = profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("config_plan_hash") == plan_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "config_plan_type": "cortex_local_model_backend_config_plan",
        "profile_path": str(profile),
        "config_plan_path": str(path),
        "config_plan_count": len(records),
        "config_plan_records": [record],
    }


def summarize_cortex_local_model_backend_config_plans(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_model_backend_config_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_config_plan_count": len(records),
        "allowed_config_plan_count": sum(1 for item in records if item.get("config_plan_allowed") is True),
        "latest_config_plan_status": latest.get("config_plan_status") if latest else None,
        "latest_config_plan_decision": latest.get("config_plan_decision") if latest else None,
        "latest_config_plan_allowed": latest.get("config_plan_allowed") if latest else None,
        "latest_selected_backend": latest.get("selected_backend") if latest else None,
        "latest_selected_model": latest.get("selected_model") if latest else None,
        "latest_runtime_binding": latest.get("runtime_binding") if latest else None,
        "latest_model_call_performed": latest.get("model_call_performed") if latest else None,
        "latest_network_call_performed": latest.get("network_call_performed") if latest else None,
        "latest_repo_mutation_performed": latest.get("repo_mutation_performed") if latest else None,
        "latest_shell_execution_performed": latest.get("shell_execution_performed") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_config_plan_hash": latest.get("config_plan_hash") if latest else None,
    }


def _blockers(
    *,
    advice: dict[str, object] | None,
    contract: dict[str, object] | None,
    preferred_backend: str,
) -> list[str]:
    blockers = []
    if preferred_backend not in _SUPPORTED_BACKENDS:
        blockers.append("unsupported_preferred_backend")
    if not advice:
        blockers.append("missing_local_model_advice")
    elif advice.get("advice_allowed") is not True:
        blockers.append("local_model_advice_not_allowed")
    elif advice.get("next_action") != "prepare_local_model_backend_config_plan":
        blockers.append("local_model_advice_not_waiting_backend_config_plan")
    if advice and advice.get("model_call_performed") is not False:
        blockers.append("local_model_advice_model_call_was_performed")
    if advice and advice.get("repo_mutation_performed") is not False:
        blockers.append("local_model_advice_repo_mutation_was_performed")
    if not contract:
        blockers.append("missing_backend_adapter_contract")
    elif contract.get("contract_allowed") is not True:
        blockers.append("backend_adapter_contract_not_allowed")
    elif contract.get("default_backend") != _DEFAULT_BACKEND:
        blockers.append("backend_adapter_contract_default_backend_not_mock")
    if contract and preferred_backend in _SUPPORTED_BACKENDS:
        supported = contract.get("supported_initial_backends")
        if isinstance(supported, list) and preferred_backend not in supported:
            blockers.append("preferred_backend_not_allowed_by_adapter_contract")
    return blockers


def _backend_profiles() -> list[dict[str, object]]:
    return [
        {
            "backend_kind": backend_kind,
            "default_model": _DEFAULT_MODEL_BY_BACKEND[backend_kind],
            **profile,
        }
        for backend_kind, profile in _BACKEND_PROFILES.items()
    ]


def _config_preview(backend_kind: str | None, model_name: str | None) -> dict[str, object]:
    if backend_kind is None or model_name is None:
        return {}
    return {
        "backend_kind": backend_kind,
        "model_name": model_name,
        "base_url": _base_url_for(backend_kind),
        "model_path": None,
        "enabled": backend_kind == _DEFAULT_BACKEND,
        "activation_required": backend_kind != _DEFAULT_BACKEND,
        **_SAFE_DEFAULTS,
        "network_required": backend_kind in {"ollama", "local_openai_compatible_api"},
    }


def _base_url_for(backend_kind: str) -> str | None:
    if backend_kind == "ollama":
        return "http://127.0.0.1:11434"
    if backend_kind == "local_openai_compatible_api":
        return "http://127.0.0.1:8000/v1"
    return None


def _network_policy(backend_kind: str | None) -> str:
    if backend_kind in {"ollama", "local_openai_compatible_api"}:
        return "localhost_only_after_explicit_operator_config"
    return "network_not_required"


def _field(row: dict[str, object] | None, key: str) -> str | None:
    value = row.get(key) if row else None
    return value if isinstance(value, str) else None


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
