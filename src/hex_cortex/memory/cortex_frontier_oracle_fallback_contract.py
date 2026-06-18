from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME = "cortex-frontier-oracle-fallback-contract.jsonl"
LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME = "cortex-latent-world-model-simulation-contract.jsonl"

_ALLOWED_TRIGGERS = [
    "high_uncertainty",
    "high_surprise",
    "conflicting_evidence",
    "operator_requests_audit",
    "compact_expert_insufficient_context",
]

_REQUEST_SCHEMA = {
    "request_id": "string",
    "trigger": "high_uncertainty|high_surprise|conflicting_evidence|operator_requests_audit|compact_expert_insufficient_context",
    "question": "string",
    "evidence_refs": "list[string]",
    "redaction_policy": "redacted_secrets_required",
    "operator_gate": "explicit_required",
}

_ANSWER_SCHEMA = {
    "oracle_status": "ready|blocked|insufficient_context",
    "oracle_decision": "advice_ready|advice_blocked|audit_only",
    "answer": "string",
    "rationale": "list[string]",
    "confidence": "float[0,1]",
    "risk_flags": "list[string]",
    "required_receipts": "list[string]",
    "next_action": "string",
}


def build_cortex_frontier_oracle_fallback_contract(profile: Path) -> dict[str, object]:
    world_contract = _latest_jsonl(profile / LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME)
    blockers = _blockers(world_contract)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "frontier_oracle_fallback_contract_ready" if allowed else "frontier_oracle_fallback_contract_blocked"
    next_action = "prepare_v14_runtime_orchestrator" if allowed else "repair_frontier_oracle_fallback_contract"
    reasons = ["latent_world_model_contract_ready", "oracle_gate_defined", "local_path_remains_primary"] if allowed else blockers
    contract_hash = _hash(
        str(profile),
        str(world_contract.get("contract_hash") if world_contract else "missing_world_contract"),
        decision,
        next_action,
        json.dumps(_REQUEST_SCHEMA, sort_keys=True),
        json.dumps(_ANSWER_SCHEMA, sort_keys=True),
        *_ALLOWED_TRIGGERS,
        *reasons,
    )
    record = {
        "contract_id": f"cortex_frontier_oracle_fallback_contract_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_latent_world_model_contract_hash": world_contract.get("contract_hash") if world_contract else None,
        "module_key": "frontier_oracle_fallback_contract",
        "oracle_kind": "guarded_frontier_audit_fallback",
        "contract_status": status,
        "contract_decision": decision,
        "contract_allowed": allowed,
        "local_path_primary": True if allowed else False,
        "oracle_required_by_default": False,
        "oracle_mode": "gated_audit_fallback" if allowed else "blocked",
        "runtime_binding": "none_contract_only",
        "allowed_triggers": _ALLOWED_TRIGGERS if allowed else [],
        "request_schema": _REQUEST_SCHEMA if allowed else {},
        "answer_schema": _ANSWER_SCHEMA if allowed else {},
        "context_policy": "minimum_necessary_evidence_redacted_secrets_only",
        "gate_policy": "explicit_operator_gate_required_for_every_oracle_call",
        "write_policy": "no_autonomous_write_no_runtime_state_mutation",
        "logging_policy": "persist_request_response_hashes_and_receipts_before_use",
        "fallback_scope": "audit_synthesis_ambiguity_resolution_only",
        "verification_commands": ["python -m pytest", "python -m hex_cortex.memory.cortex_frontier_oracle_fallback_contract_cli .hex-cortex --summary --pretty"],
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "contract_hash": contract_hash,
    }
    path = profile / CORTEX_FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("contract_hash") == contract_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "contract_type": "cortex_frontier_oracle_fallback_contract",
        "profile_path": str(profile),
        "contract_path": str(path),
        "contract_count": len(records),
        "contract_records": [record],
    }


def summarize_cortex_frontier_oracle_fallback_contracts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_frontier_oracle_fallback_contract",
        "path": str(path),
        "exists": path.exists(),
        "total_contract_count": len(records),
        "allowed_contract_count": sum(1 for item in records if item.get("contract_allowed") is True),
        "latest_contract_status": latest.get("contract_status") if latest else None,
        "latest_contract_decision": latest.get("contract_decision") if latest else None,
        "latest_contract_allowed": latest.get("contract_allowed") if latest else None,
        "latest_local_path_primary": latest.get("local_path_primary") if latest else None,
        "latest_oracle_mode": latest.get("oracle_mode") if latest else None,
        "latest_write_policy": latest.get("write_policy") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_contract_hash": latest.get("contract_hash") if latest else None,
    }


def _blockers(world_contract: dict[str, object] | None) -> list[str]:
    blockers = []
    if not world_contract:
        blockers.append("missing_latent_world_model_simulation_contract")
        return blockers
    if world_contract.get("contract_allowed") is not True:
        blockers.append("latent_world_model_contract_not_allowed")
    if world_contract.get("next_action") != "prepare_frontier_oracle_fallback_contract":
        blockers.append("latent_world_model_contract_not_waiting_oracle_contract")
    if world_contract.get("simulation_safety_mode") != "simulation_only_no_state_mutation_no_direct_execution":
        blockers.append("latent_world_model_safety_mode_unexpected")
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
