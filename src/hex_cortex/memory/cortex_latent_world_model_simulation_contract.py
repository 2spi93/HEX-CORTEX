from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME = "cortex-latent-world-model-simulation-contract.jsonl"
LOCAL_COMPACT_EXPERT_CONTRACT_FILENAME = "cortex-local-compact-expert-runtime-contract.jsonl"

_STATE_SCHEMA = {
    "state_id": "string",
    "profile_path": "string",
    "active_skill_key": "string|null",
    "memory_evidence_refs": "list[string]",
    "current_goal": "string",
    "known_constraints": "list[string]",
    "observed_scores": "dict[string,float]",
}

_ACTION_SCHEMA = {
    "action_id": "string",
    "action_kind": "plan|patch|review|doc|audit|simulate",
    "action_summary": "string",
    "expected_receipts": "list[string]",
    "mutation_intent": "none|local_artifact|repo_file|runtime_state",
}

_PREDICTED_STATE_SCHEMA = {
    "predicted_state_id": "string",
    "prediction_summary": "string",
    "expected_benefits": "list[string]",
    "expected_risks": "list[string]",
    "surprise_score": "float[0,1]",
    "risk_score": "float[0,1]",
    "confidence_score": "float[0,1]",
    "counterfactual_notes": "list[string]",
    "next_action": "string",
}


def build_cortex_latent_world_model_simulation_contract(profile: Path) -> dict[str, object]:
    local_contract = _latest_jsonl(profile / LOCAL_COMPACT_EXPERT_CONTRACT_FILENAME)
    blockers = _blockers(local_contract)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "latent_world_model_simulation_contract_ready" if allowed else "latent_world_model_simulation_contract_blocked"
    next_action = "prepare_frontier_oracle_fallback_contract" if allowed else "repair_latent_world_model_simulation_contract"
    reasons = ["local_compact_expert_contract_ready", "latent_state_schema_defined", "simulation_contract_defined"] if allowed else blockers
    contract_hash = _hash(
        str(profile),
        str(local_contract.get("contract_hash") if local_contract else "missing_local_contract"),
        decision,
        next_action,
        json.dumps(_STATE_SCHEMA, sort_keys=True),
        json.dumps(_ACTION_SCHEMA, sort_keys=True),
        json.dumps(_PREDICTED_STATE_SCHEMA, sort_keys=True),
        *reasons,
    )
    record = {
        "contract_id": f"cortex_latent_world_model_simulation_contract_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_local_compact_expert_contract_hash": local_contract.get("contract_hash") if local_contract else None,
        "module_key": "latent_world_model_simulation_contract",
        "simulation_kind": "latent_state_transition_simulator",
        "contract_status": status,
        "contract_decision": decision,
        "contract_allowed": allowed,
        "runtime_binding": "none_contract_only",
        "world_model_policy": "latent_prediction_only_no_observation_generation",
        "state_schema": _STATE_SCHEMA if allowed else {},
        "action_schema": _ACTION_SCHEMA if allowed else {},
        "predicted_state_schema": _PREDICTED_STATE_SCHEMA if allowed else {},
        "simulation_safety_mode": "simulation_only_no_state_mutation_no_direct_execution",
        "surprise_policy": "surprise_score_required_for_unexpected_or_implausible_transition",
        "risk_policy": "risk_score_required_and_bounded_0_1",
        "confidence_policy": "confidence_score_required_and_bounded_0_1",
        "counterfactual_policy": "counterfactual_notes_allowed_but_advisory_only",
        "memory_policy": "read_evidence_only_write_simulation_receipts_after_gate",
        "verification_commands": ["python -m pytest", "python -m hex_cortex.memory.cortex_latent_world_model_simulation_contract_cli .hex-cortex --summary --pretty"],
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "contract_hash": contract_hash,
    }
    path = profile / CORTEX_LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("contract_hash") == contract_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "contract_type": "cortex_latent_world_model_simulation_contract",
        "profile_path": str(profile),
        "contract_path": str(path),
        "contract_count": len(records),
        "contract_records": [record],
    }


def summarize_cortex_latent_world_model_simulation_contracts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_latent_world_model_simulation_contract",
        "path": str(path),
        "exists": path.exists(),
        "total_contract_count": len(records),
        "allowed_contract_count": sum(1 for item in records if item.get("contract_allowed") is True),
        "latest_contract_status": latest.get("contract_status") if latest else None,
        "latest_contract_decision": latest.get("contract_decision") if latest else None,
        "latest_contract_allowed": latest.get("contract_allowed") if latest else None,
        "latest_world_model_policy": latest.get("world_model_policy") if latest else None,
        "latest_simulation_safety_mode": latest.get("simulation_safety_mode") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_contract_hash": latest.get("contract_hash") if latest else None,
    }


def _blockers(local_contract: dict[str, object] | None) -> list[str]:
    blockers = []
    if not local_contract:
        blockers.append("missing_local_compact_expert_runtime_contract")
        return blockers
    if local_contract.get("contract_allowed") is not True:
        blockers.append("local_compact_expert_contract_not_allowed")
    if local_contract.get("next_action") != "prepare_latent_world_model_simulation_contract":
        blockers.append("local_compact_expert_contract_not_waiting_world_model_contract")
    if local_contract.get("safety_mode") != "advisory_only_no_direct_execution_no_state_mutation":
        blockers.append("local_compact_expert_safety_mode_unexpected")
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
