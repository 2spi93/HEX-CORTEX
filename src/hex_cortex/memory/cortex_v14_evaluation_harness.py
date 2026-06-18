from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_V14_EVALUATION_HARNESS_FILENAME = "cortex-v14-evaluation-harness.jsonl"
V14_GUARD_FILENAME = "cortex-v14-safety-gate.jsonl"

_EVAL_CHECKS = [
    "contracts_present",
    "no_model_calls_yet",
    "no_state_mutation",
    "oracle_gated",
    "receipt_policy_present",
    "pytest_required",
]


def build_cortex_v14_evaluation_harness(profile: Path) -> dict[str, object]:
    guard = _latest_jsonl(profile / V14_GUARD_FILENAME)
    blockers = _blockers(guard)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "v1_4_evaluation_harness_ready" if allowed else "v1_4_evaluation_harness_blocked"
    next_action = "prepare_local_model_backend_adapter_contract" if allowed else "repair_v14_evaluation_harness"
    reasons = ["runtime_guard_ready", "evaluation_checks_defined", "no_model_runtime_binding_yet"] if allowed else blockers
    harness_hash = _hash(str(profile), str(guard.get("gate_hash") if guard else "missing_guard"), decision, next_action, *_EVAL_CHECKS, *reasons)
    record = {
        "harness_id": f"cortex_v14_evaluation_harness_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_guard_hash": guard.get("gate_hash") if guard else None,
        "harness_status": status,
        "harness_decision": decision,
        "harness_allowed": allowed,
        "evaluation_checks": _EVAL_CHECKS if allowed else [],
        "minimum_pass_score": 1.0,
        "current_pass_score": 1.0 if allowed else 0.0,
        "model_runtime_binding_allowed": False,
        "dry_run_allowed_after_harness": True if allowed else False,
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "harness_hash": harness_hash,
    }
    path = profile / CORTEX_V14_EVALUATION_HARNESS_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("harness_hash") == harness_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"harness_type": "cortex_v14_evaluation_harness", "profile_path": str(profile), "harness_path": str(path), "harness_count": len(records), "harness_records": [record]}


def summarize_cortex_v14_evaluation_harnesses(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_v14_evaluation_harness",
        "path": str(path),
        "exists": path.exists(),
        "total_harness_count": len(records),
        "allowed_harness_count": sum(1 for item in records if item.get("harness_allowed") is True),
        "latest_harness_status": latest.get("harness_status") if latest else None,
        "latest_harness_decision": latest.get("harness_decision") if latest else None,
        "latest_harness_allowed": latest.get("harness_allowed") if latest else None,
        "latest_current_pass_score": latest.get("current_pass_score") if latest else None,
        "latest_dry_run_allowed_after_harness": latest.get("dry_run_allowed_after_harness") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_harness_hash": latest.get("harness_hash") if latest else None,
    }


def _blockers(guard: dict[str, object] | None) -> list[str]:
    blockers = []
    if not guard:
        blockers.append("missing_v14_runtime_guard")
        return blockers
    if guard.get("gate_allowed") is not True:
        blockers.append("v14_runtime_guard_not_allowed")
    if guard.get("next_action") != "prepare_v14_evaluation_harness":
        blockers.append("v14_runtime_guard_not_waiting_evaluation_harness")
    if guard.get("model_calls_allowed") is not False:
        blockers.append("model_calls_policy_not_closed")
    if guard.get("mutation_allowed") is not False:
        blockers.append("mutation_policy_not_closed")
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
