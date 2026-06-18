from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_V14_SAFETY_GATE_FILENAME = "cortex-v14-safety-gate.jsonl"
V14_RUNTIME_ORCHESTRATOR_FILENAME = "cortex-v14-runtime-orchestrator.jsonl"

_REQUIRED_POLICIES = {
    "runtime_binding": "none_contract_orchestrator_only",
    "model_call_policy": "no_model_calls_yet",
    "execution_policy": "no_direct_execution_no_state_mutation",
    "oracle_policy": "gated_fallback_only_after_explicit_operator_gate",
    "receipt_policy": "receipts_required_before_future_mutation",
}


def build_cortex_v14_safety_gate(profile: Path) -> dict[str, object]:
    orchestrator = _latest_jsonl(profile / V14_RUNTIME_ORCHESTRATOR_FILENAME)
    blockers = _blockers(orchestrator)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "v1_4_safety_gate_ready" if allowed else "v1_4_safety_gate_blocked"
    next_action = "prepare_v14_evaluation_harness" if allowed else "repair_v14_safety_gate"
    reasons = ["orchestrator_ready", "policies_verified", "model_runtime_still_unbound"] if allowed else blockers
    gate_hash = _hash(str(profile), str(orchestrator.get("orchestrator_hash") if orchestrator else "missing_orchestrator"), decision, next_action, *[f"{k}={v}" for k, v in _REQUIRED_POLICIES.items()], *reasons)
    record = {
        "gate_id": f"cortex_v14_safety_gate_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_orchestrator_hash": orchestrator.get("orchestrator_hash") if orchestrator else None,
        "gate_status": status,
        "gate_decision": decision,
        "gate_allowed": allowed,
        "verified_policies": _REQUIRED_POLICIES if allowed else {},
        "safety_level": "v1_4_contract_runtime_safe" if allowed else "blocked",
        "mutation_allowed": False,
        "model_calls_allowed": False,
        "oracle_calls_allowed_without_gate": False,
        "required_next_gate_before_model_binding": "v14_evaluation_harness",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "gate_hash": gate_hash,
    }
    path = profile / CORTEX_V14_SAFETY_GATE_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("gate_hash") == gate_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"gate_type": "cortex_v14_safety_gate", "profile_path": str(profile), "gate_path": str(path), "gate_count": len(records), "gate_records": [record]}


def summarize_cortex_v14_safety_gates(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_v14_safety_gate",
        "path": str(path),
        "exists": path.exists(),
        "total_gate_count": len(records),
        "allowed_gate_count": sum(1 for item in records if item.get("gate_allowed") is True),
        "latest_gate_status": latest.get("gate_status") if latest else None,
        "latest_gate_decision": latest.get("gate_decision") if latest else None,
        "latest_gate_allowed": latest.get("gate_allowed") if latest else None,
        "latest_safety_level": latest.get("safety_level") if latest else None,
        "latest_model_calls_allowed": latest.get("model_calls_allowed") if latest else None,
        "latest_mutation_allowed": latest.get("mutation_allowed") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_gate_hash": latest.get("gate_hash") if latest else None,
    }


def _blockers(orchestrator: dict[str, object] | None) -> list[str]:
    blockers = []
    if not orchestrator:
        blockers.append("missing_v14_runtime_orchestrator")
        return blockers
    if orchestrator.get("orchestrator_allowed") is not True:
        blockers.append("v14_runtime_orchestrator_not_allowed")
    if orchestrator.get("next_action") != "prepare_v14_safety_gate":
        blockers.append("v14_runtime_orchestrator_not_waiting_safety_gate")
    for key, expected in _REQUIRED_POLICIES.items():
        if orchestrator.get(key) != expected:
            blockers.append(f"unexpected_{key}")
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
