from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_local_model_backend_config_plan import (
    CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME,
)

CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME = (
    "cortex-local-model-backend-config-dry-run.jsonl"
)

_ALLOWED_BACKENDS = {"mock", "ollama", "llama_cpp", "local_openai_compatible_api"}
_LOCAL_HTTP_BACKENDS = {"ollama", "local_openai_compatible_api"}
_REQUIRED_CONFIG_KEYS = {
    "backend_kind",
    "model_name",
    "context_window",
    "max_output_tokens",
    "temperature",
    "timeout_seconds",
    "localhost_only",
    "repo_mutation_allowed",
    "shell_execution_allowed",
    "network_required",
}


def build_cortex_local_model_backend_config_dry_run(
    profile: Path,
    *,
    expected_backend: str | None = None,
) -> dict[str, object]:
    plan = _latest_jsonl(profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME)
    blockers = _blockers(plan=plan, expected_backend=expected_backend)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = (
        "local_model_backend_config_dry_run_ready"
        if allowed
        else "local_model_backend_config_dry_run_blocked"
    )
    next_action = (
        "prepare_local_model_backend_probe_contract"
        if allowed
        else "repair_local_model_backend_config_dry_run"
    )
    config_preview = _config_preview(plan) if plan else {}
    validation_checks = _validation_checks(config_preview) if plan else []
    selected_backend = _string(config_preview.get("backend_kind"))
    selected_model = _string(config_preview.get("model_name"))
    config_hash = _stable_hash(config_preview) if allowed else None
    reasons = (
        [
            "backend_config_plan_ready",
            "config_schema_validated",
            "localhost_policy_validated",
            "dry_run_completed_without_backend_call",
        ]
        if allowed
        else blockers
    )
    dry_run_hash = _hash(
        str(profile),
        _string(plan.get("config_plan_hash") if plan else None) or "missing_plan",
        decision,
        next_action,
        selected_backend or "missing_backend",
        selected_model or "missing_model",
        config_hash or "missing_config_hash",
        *reasons,
    )
    record = {
        "config_dry_run_id": f"cortex_local_model_backend_config_dry_run_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_config_plan_hash": plan.get("config_plan_hash") if plan else None,
        "config_dry_run_status": status,
        "config_dry_run_decision": decision,
        "config_dry_run_allowed": allowed,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "validated_config": config_preview if allowed else {},
        "validated_config_hash": config_hash,
        "validation_checks": validation_checks,
        "runtime_binding": "none_config_dry_run_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "local_probe_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "binding_policy": "dry_run_only_probe_contract_required_before_runtime_binding",
        "network_policy": _network_policy(selected_backend) if allowed else None,
        "execution_policy": "advisory_only_no_model_no_network_no_repo_mutation_no_shell",
        "receipt_policy": "persist_config_dry_run_hash_before_local_probe_contract",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "config_dry_run_hash": dry_run_hash,
    }
    path = profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("config_dry_run_hash") == dry_run_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "config_dry_run_type": "cortex_local_model_backend_config_dry_run",
        "profile_path": str(profile),
        "config_dry_run_path": str(path),
        "config_dry_run_count": len(records),
        "config_dry_run_records": [record],
    }


def summarize_cortex_local_model_backend_config_dry_runs(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_model_backend_config_dry_run",
        "path": str(path),
        "exists": path.exists(),
        "total_config_dry_run_count": len(records),
        "allowed_config_dry_run_count": sum(
            1 for item in records if item.get("config_dry_run_allowed") is True
        ),
        "latest_config_dry_run_status": latest.get("config_dry_run_status") if latest else None,
        "latest_config_dry_run_decision": latest.get("config_dry_run_decision")
        if latest
        else None,
        "latest_config_dry_run_allowed": latest.get("config_dry_run_allowed")
        if latest
        else None,
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
        "latest_config_dry_run_hash": latest.get("config_dry_run_hash") if latest else None,
    }


def _blockers(*, plan: dict[str, object] | None, expected_backend: str | None) -> list[str]:
    blockers = []
    if expected_backend is not None and expected_backend not in _ALLOWED_BACKENDS:
        blockers.append("unsupported_expected_backend")
    if not plan:
        blockers.append("missing_local_model_backend_config_plan")
        return blockers
    if plan.get("config_plan_allowed") is not True:
        blockers.append("backend_config_plan_not_allowed")
    if plan.get("next_action") != "prepare_local_model_backend_config_dry_run":
        blockers.append("backend_config_plan_not_waiting_config_dry_run")
    if plan.get("runtime_binding") != "none_config_plan_only":
        blockers.append("backend_config_plan_runtime_binding_not_plan_only")
    for flag in (
        "model_call_performed",
        "network_call_performed",
        "repo_mutation_performed",
        "shell_execution_performed",
    ):
        if plan.get(flag) is not False:
            blockers.append(f"backend_config_plan_{flag}_not_false")
    config_preview = _config_preview(plan)
    if not config_preview:
        blockers.append("missing_config_preview")
        return blockers
    if expected_backend and config_preview.get("backend_kind") != expected_backend:
        blockers.append("expected_backend_mismatch")
    checks = _validation_checks(config_preview)
    blockers.extend(check["check"] for check in checks if check.get("passed") is not True)
    return blockers


def _validation_checks(config: dict[str, object]) -> list[dict[str, object]]:
    backend_kind = _string(config.get("backend_kind"))
    return [
        {"check": "required_config_keys_present", "passed": _REQUIRED_CONFIG_KEYS <= set(config)},
        {"check": "backend_kind_supported", "passed": backend_kind in _ALLOWED_BACKENDS},
        {"check": "model_name_present", "passed": bool(_string(config.get("model_name")))},
        {"check": "context_window_valid", "passed": _positive_int(config.get("context_window"))},
        {
            "check": "max_output_tokens_valid",
            "passed": _positive_int(config.get("max_output_tokens")),
        },
        {"check": "temperature_valid", "passed": _temperature_valid(config.get("temperature"))},
        {
            "check": "timeout_seconds_valid",
            "passed": _positive_number(config.get("timeout_seconds")),
        },
        {"check": "localhost_only_true", "passed": config.get("localhost_only") is True},
        {
            "check": "repo_mutation_disabled",
            "passed": config.get("repo_mutation_allowed") is False,
        },
        {
            "check": "shell_execution_disabled",
            "passed": config.get("shell_execution_allowed") is False,
        },
        {
            "check": "network_required_consistent",
            "passed": _network_required_consistent(backend_kind, config),
        },
        {
            "check": "base_url_localhost_only",
            "passed": _base_url_localhost_only(backend_kind, config.get("base_url")),
        },
    ]


def _config_preview(plan: dict[str, object]) -> dict[str, object]:
    value = plan.get("config_preview")
    return value if isinstance(value, dict) else {}


def _network_required_consistent(backend_kind: str | None, config: dict[str, object]) -> bool:
    expected = backend_kind in _LOCAL_HTTP_BACKENDS
    return config.get("network_required") is expected


def _base_url_localhost_only(backend_kind: str | None, value: object) -> bool:
    if backend_kind not in _LOCAL_HTTP_BACKENDS:
        return value is None
    if not isinstance(value, str):
        return False
    return value.startswith("http://127.0.0.1") or value.startswith("http://localhost")


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _temperature_valid(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 2


def _network_policy(backend_kind: str | None) -> str:
    if backend_kind in _LOCAL_HTTP_BACKENDS:
        return "localhost_only_config_validated_no_probe_performed"
    return "network_not_required"


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
