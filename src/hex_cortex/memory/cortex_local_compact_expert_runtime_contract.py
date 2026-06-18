from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_LOCAL_COMPACT_EXPERT_RUNTIME_CONTRACT_FILENAME = "cortex-local-compact-expert-runtime-contract.jsonl"
V14_ADVANCED_MODULES_PLAN_FILENAME = "cortex-v14-advanced-modules-plan.jsonl"

_INPUT_CONTEXT_SCHEMA = {
    "profile_path": "string",
    "task_text": "string",
    "intent": "plan|review|explain|diagnose",
    "domain": "string|null",
    "selected_skill_key": "string|null",
    "memory_evidence_refs": "list[string]",
}

_OUTPUT_SCHEMA = {
    "expert_status": "ready|blocked|insufficient_context",
    "expert_decision": "advice_ready|advice_blocked",
    "recommendation": "string",
    "rationale": "list[string]",
    "confidence": "float[0,1]",
    "risk_flags": "list[string]",
    "required_receipts": "list[string]",
    "next_action": "string",
}


def build_cortex_local_compact_expert_runtime_contract(profile: Path) -> dict[str, object]:
    plan = _latest_jsonl(profile / V14_ADVANCED_MODULES_PLAN_FILENAME)
    blockers = _blockers(plan)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "local_compact_expert_runtime_contract_ready" if allowed else "local_compact_expert_runtime_contract_blocked"
    next_action = "prepare_latent_world_model_simulation_contract" if allowed else "repair_local_compact_expert_runtime_contract"
    reasons = ["v14_plan_ready", "local_compact_expert_module_found", "runtime_contract_defined"] if allowed else blockers
    contract_hash = _hash(
        str(profile),
        str(plan.get("plan_hash") if plan else "missing_plan"),
        decision,
        next_action,
        json.dumps(_INPUT_CONTEXT_SCHEMA, sort_keys=True),
        json.dumps(_OUTPUT_SCHEMA, sort_keys=True),
        *reasons,
    )
    record = {
        "contract_id": f"cortex_local_compact_expert_runtime_contract_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_v14_plan_hash": plan.get("plan_hash") if plan else None,
        "module_key": "local_compact_expert_runtime_contract",
        "expert_kind": "local_compact_architecture_expert",
        "contract_status": status,
        "contract_decision": decision,
        "contract_allowed": allowed,
        "runtime_binding": "none_contract_only",
        "model_slot": "local_small_instruct_model_slot",
        "model_backend_policy": "gguf_or_local_api_later_no_binding_now",
        "adapter_policy": "prompt_adapter_first_optional_lora_candidate_later",
        "input_context_schema": _INPUT_CONTEXT_SCHEMA if allowed else {},
        "output_schema": _OUTPUT_SCHEMA if allowed else {},
        "confidence_policy": "confidence_required_and_bounded_0_1",
        "safety_mode": "advisory_only_no_direct_execution_no_state_mutation",
        "memory_policy": "read_evidence_only_write_receipts_only_after_gate",
        "fallback_policy": "frontier_oracle_only_after_explicit_gate",
        "verification_commands": ["python -m pytest", "python -m hex_cortex.memory.cortex_local_compact_expert_runtime_contract_cli .hex-cortex --summary --pretty"],
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "contract_hash": contract_hash,
    }
    path = profile / CORTEX_LOCAL_COMPACT_EXPERT_RUNTIME_CONTRACT_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("contract_hash") == contract_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"contract_type": "cortex_local_compact_expert_runtime_contract", "profile_path": str(profile), "contract_path": str(path), "contract_count": len(records), "contract_records": [record]}


def summarize_cortex_local_compact_expert_runtime_contracts(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_local_compact_expert_runtime_contract",
        "path": str(path),
        "exists": path.exists(),
        "total_contract_count": len(records),
        "allowed_contract_count": sum(1 for item in records if item.get("contract_allowed") is True),
        "latest_contract_status": latest.get("contract_status") if latest else None,
        "latest_contract_decision": latest.get("contract_decision") if latest else None,
        "latest_contract_allowed": latest.get("contract_allowed") if latest else None,
        "latest_model_slot": latest.get("model_slot") if latest else None,
        "latest_adapter_policy": latest.get("adapter_policy") if latest else None,
        "latest_safety_mode": latest.get("safety_mode") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_contract_hash": latest.get("contract_hash") if latest else None,
    }


def _blockers(plan: dict[str, object] | None) -> list[str]:
    blockers = []
    if not plan:
        blockers.append("missing_v14_advanced_modules_plan")
        return blockers
    if plan.get("v14_allowed") is not True:
        blockers.append("v14_advanced_modules_plan_not_allowed")
    if plan.get("next_action") != "prepare_local_compact_expert_runtime_contract":
        blockers.append("v14_plan_not_waiting_local_compact_expert_contract")
    modules = plan.get("modules", [])
    if not any(isinstance(module, dict) and module.get("module_key") == "local_compact_expert_runtime_contract" for module in modules):
        blockers.append("missing_local_compact_expert_module")
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
