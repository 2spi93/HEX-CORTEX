from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LOCAL_MODEL_ADVICE_FILENAME = "cortex-local-model-advice.jsonl"
FIRST_LOCAL_MODEL_DRY_RUN_FILENAME = "cortex-first-local-model-dry-run.jsonl"

_DEFAULT_TASK_TEXT = "Produce an optimized advisory plan for the next HEX-CORTEX local model integration step."
_OPTIMIZATION_PROFILE = {
    "max_context_chars": 2400,
    "max_output_items": 6,
    "temperature": 0.2,
    "timeout_seconds": 8.0,
    "prefer_local_backend": True,
    "fail_closed_on_backend_error": True,
    "repo_mutation_allowed": False,
    "shell_execution_allowed": False,
    "network_required": False,
}


def build_cortex_local_model_advice(
    profile: Path,
    *,
    task_text: str = _DEFAULT_TASK_TEXT,
    selected_skill_key: str | None = None,
) -> dict[str, object]:
    dry_run = _latest_jsonl(profile / FIRST_LOCAL_MODEL_DRY_RUN_FILENAME)
    blockers = _blockers(dry_run)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "local_model_advice_ready" if allowed else "local_model_advice_blocked"
    next_action = "prepare_local_model_backend_config_plan" if allowed else "repair_local_model_advice"
    reasons = ["first_local_model_dry_run_ready", "optimized_advisory_profile_applied", "mock_advice_generated"] if allowed else blockers

    request = _request_payload(profile, task_text=task_text, selected_skill_key=selected_skill_key)
    advice = _mock_advice(task_text=task_text, selected_skill_key=selected_skill_key) if allowed else {}
    request_hash = _stable_hash(request)
    advice_hash = _stable_hash(advice) if advice else None
    record_hash = _hash(
        str(profile),
        str(dry_run.get("dry_run_hash") if dry_run else "missing_dry_run"),
        request_hash,
        str(advice_hash),
        decision,
        next_action,
        *reasons,
    )

    record = {
        "advice_id": f"cortex_local_model_advice_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_dry_run_hash": dry_run.get("dry_run_hash") if dry_run else None,
        "advice_status": status,
        "advice_decision": decision,
        "advice_allowed": allowed,
        "backend_kind": "mock",
        "model_call_performed": False,
        "network_call_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "optimization_profile": _OPTIMIZATION_PROFILE if allowed else {},
        "request_hash": request_hash,
        "advice_hash": advice_hash,
        "request_preview": request if allowed else {},
        "advice": advice,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "record_hash": record_hash,
    }

    path = profile / CORTEX_LOCAL_MODEL_ADVICE_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("record_hash") == record_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "advice_type": "cortex_local_model_advice",
        "profile_path": str(profile),
        "advice_path": str(path),
        "advice_count": len(records),
        "advice_records": [record],
    }


def summarize_cortex_local_model_advice(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_model_advice",
        "path": str(path),
        "exists": path.exists(),
        "total_advice_count": len(records),
        "allowed_advice_count": sum(1 for item in records if item.get("advice_allowed") is True),
        "latest_advice_status": latest.get("advice_status") if latest else None,
        "latest_advice_decision": latest.get("advice_decision") if latest else None,
        "latest_advice_allowed": latest.get("advice_allowed") if latest else None,
        "latest_backend_kind": latest.get("backend_kind") if latest else None,
        "latest_model_call_performed": latest.get("model_call_performed") if latest else None,
        "latest_repo_mutation_performed": latest.get("repo_mutation_performed") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_record_hash": latest.get("record_hash") if latest else None,
    }


def _request_payload(profile: Path, *, task_text: str, selected_skill_key: str | None) -> dict[str, object]:
    bounded_task = task_text[: _OPTIMIZATION_PROFILE["max_context_chars"]]
    return {
        "request_id": f"cortex_local_model_advice_request_{uuid4().hex}",
        "profile_path": str(profile),
        "task_text": bounded_task,
        "selected_skill_key": selected_skill_key,
        "backend_kind": "mock",
        "safety_mode": "advisory_only",
        "optimization_profile": _OPTIMIZATION_PROFILE,
    }


def _mock_advice(*, task_text: str, selected_skill_key: str | None) -> dict[str, object]:
    return {
        "advice_status": "ready",
        "advice_decision": "optimized_advisory_plan_ready",
        "selected_skill_key": selected_skill_key,
        "summary": "Use the mock advisory path to validate request/response shape before enabling a real local backend.",
        "recommended_steps": [
            "Keep mock backend as default until local config exists.",
            "Add backend config plan with explicit allowed backends and timeouts.",
            "Add a dry-run command for Ollama or llama.cpp only after config validation.",
            "Keep outputs advisory-only and require receipts before repo mutation.",
            "Record request and response hashes for replay and audit.",
        ],
        "risk_flags": [],
        "confidence": 0.78,
        "next_action": "prepare_local_model_backend_config_plan",
    }


def _blockers(dry_run: dict[str, object] | None) -> list[str]:
    blockers = []
    if not dry_run:
        blockers.append("missing_first_local_model_dry_run")
        return blockers
    if dry_run.get("dry_run_allowed") is not True:
        blockers.append("first_local_model_dry_run_not_allowed")
    if dry_run.get("next_action") != "prepare_local_model_advice_cli":
        blockers.append("first_local_model_dry_run_not_waiting_advice_cli")
    if dry_run.get("model_call_performed") is not False:
        blockers.append("dry_run_model_call_was_performed")
    if dry_run.get("repo_mutation_performed") is not False:
        blockers.append("dry_run_repo_mutation_was_performed")
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
