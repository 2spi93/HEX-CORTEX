from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_TASK_CLASSES = {
    "repository_index",
    "routine_patch",
    "complex_patch",
    "critique",
    "final_review",
    "test_failure_repair",
}


def build_coding_model_catalog(
    *,
    local_endpoint: str = "http://127.0.0.1:8080",
    local_model: str = "Qwen3-Coder-30B-A3B-Instruct",
    remote_provider: str = "openai",
    remote_model: str = "gpt-5.5",
    remote_api_key_ref: str = "env:OPENAI_API_KEY",
) -> dict[str, object]:
    local_base = _validated_local_endpoint(local_endpoint)
    secret_scheme = remote_api_key_ref.partition(":")[0]
    blockers = []
    if secret_scheme not in {"env", "vault", "keyring", "systemd-credential", "docker-secret"}:
        blockers.append("remote_api_key_ref_scheme_invalid")
    if not local_model.strip():
        blockers.append("local_model_missing")
    if not remote_provider.strip() or not remote_model.strip():
        blockers.append("remote_model_descriptor_invalid")
    providers = [
        {
            "provider_id": "local_open_weight",
            "provider_kind": "openai_compatible_local",
            "endpoint": local_base,
            "model": local_model,
            "privacy_tier": "local_only",
            "cost_tier": "local_compute",
            "secret_ref": None,
            "raw_secret_persisted": False,
            "preferred_tasks": [
                "repository_index",
                "routine_patch",
                "test_failure_repair",
            ],
        },
        {
            "provider_id": "remote_api",
            "provider_kind": remote_provider,
            "endpoint": None,
            "model": remote_model,
            "privacy_tier": "bounded_remote_context",
            "cost_tier": "metered_api",
            "secret_ref": remote_api_key_ref,
            "raw_secret_persisted": False,
            "preferred_tasks": [
                "complex_patch",
                "critique",
                "final_review",
            ],
        },
    ]
    payload = {
        "catalog_type": "coding_model_catalog_v2",
        "status": "ready" if not blockers else "blocked",
        "providers": providers,
        "fallback_policy": "explicit_receipted_no_silent_substitution",
        "prompt_persistence_allowed": False,
        "raw_response_persistence_allowed": False,
        "raw_secret_persistence_allowed": False,
        "blockers": blockers,
        "next_action": "route_coding_task" if not blockers else "repair_model_catalog",
    }
    payload["catalog_hash"] = _stable_hash(payload)
    return payload


def route_coding_task(
    *,
    task_class: str,
    context_sensitivity: str = "private",
    complexity: str = "medium",
    local_available: bool = True,
    remote_available: bool = False,
    operator_allows_remote: bool = False,
) -> dict[str, object]:
    blockers = []
    if task_class not in _TASK_CLASSES:
        blockers.append("task_class_invalid")
    if context_sensitivity not in {"public", "private", "secret"}:
        blockers.append("context_sensitivity_invalid")
    if complexity not in {"low", "medium", "high"}:
        blockers.append("complexity_invalid")
    if blockers:
        return _blocked(blockers)

    selected: str | None = None
    reason = ""
    if context_sensitivity == "secret":
        if local_available:
            selected = "local_open_weight"
            reason = "secret_context_requires_local_provider"
        else:
            blockers.append("local_provider_required_for_secret_context")
    elif task_class in {"repository_index", "routine_patch", "test_failure_repair"} and local_available:
        selected = "local_open_weight"
        reason = "local_provider_preferred_for_routine_private_work"
    elif task_class in {"complex_patch", "critique", "final_review"} or complexity == "high":
        if remote_available and operator_allows_remote:
            selected = "remote_api"
            reason = "remote_provider_authorized_for_high_complexity_review"
        elif local_available:
            selected = "local_open_weight"
            reason = "remote_provider_unavailable_or_not_authorized_fallback_local"
        else:
            blockers.append("no_eligible_provider")
    elif local_available:
        selected = "local_open_weight"
        reason = "local_provider_available"
    elif remote_available and operator_allows_remote and context_sensitivity == "public":
        selected = "remote_api"
        reason = "public_context_remote_fallback_authorized"
    else:
        blockers.append("no_eligible_provider")

    payload = {
        "route_type": "coding_model_route_v2",
        "status": "ready" if selected and not blockers else "blocked",
        "task_class": task_class,
        "context_sensitivity": context_sensitivity,
        "complexity": complexity,
        "selected_provider_id": selected,
        "selection_reason": reason or None,
        "local_available": local_available,
        "remote_available": remote_available,
        "operator_allows_remote": operator_allows_remote,
        "fallback_silent": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "raw_context_persisted": False,
        "blockers": blockers,
        "next_action": "build_reviewable_coding_task" if selected and not blockers else "repair_provider_readiness",
    }
    payload["route_hash"] = _stable_hash(payload)
    return payload


def _validated_local_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("local endpoint must be explicit localhost HTTP with port")
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def _blocked(blockers: list[str]) -> dict[str, object]:
    payload = {
        "route_type": "coding_model_route_v2",
        "status": "blocked",
        "selected_provider_id": None,
        "model_call_performed": False,
        "network_call_performed": False,
        "raw_context_persisted": False,
        "blockers": blockers,
        "next_action": "repair_coding_model_route_inputs",
    }
    payload["route_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
