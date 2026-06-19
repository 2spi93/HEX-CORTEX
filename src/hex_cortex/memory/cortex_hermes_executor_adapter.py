from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_server_federation_audit import verify_signed_task_envelope

_ALLOWED_CAPABILITIES = {
    "repo.inspect",
    "code.plan",
    "code.propose_patch",
    "worktree.evaluate",
    "tests.run_allowlisted",
    "candidate.summarize",
}


def build_hermes_executor_plan(
    *,
    envelope: dict[str, object],
    signing_key: bytes,
    repository_root: Path,
    worktree_root: Path,
    hermes_version: str,
    transport: str = "mcp",
    operator_approved: bool = False,
) -> dict[str, object]:
    verification = verify_signed_task_envelope(envelope, signing_key=signing_key)
    blockers = list(verification.get("blockers", []))
    capability = envelope.get("capability")
    if capability not in _ALLOWED_CAPABILITIES:
        blockers.append("hermes_capability_not_allowed")
    if transport not in {"mcp", "openai_compatible_v1_models", "declared_hermes_api", "bounded_cli_stdio"}:
        blockers.append("hermes_transport_invalid")
    repo = repository_root.resolve()
    worktrees = worktree_root.resolve()
    if not (repo / ".git").exists():
        blockers.append("repository_root_not_git")
    if worktrees == repo or repo.is_relative_to(worktrees):
        blockers.append("worktree_root_must_be_separate")
    write_capability = capability in {
        "code.propose_patch",
        "worktree.evaluate",
        "tests.run_allowlisted",
    }
    if write_capability and not operator_approved:
        blockers.append("operator_approval_required")
    if not hermes_version.strip():
        blockers.append("hermes_version_missing")

    plan = {
        "plan_type": "hermes_executor_adapter_v1",
        "status": "ready" if not blockers else "blocked",
        "envelope_id": envelope.get("envelope_id"),
        "capability": capability,
        "repository_root_hash": hashlib.sha256(str(repo).encode("utf-8")).hexdigest(),
        "worktree_root_hash": hashlib.sha256(str(worktrees).encode("utf-8")).hexdigest(),
        "hermes_version": hermes_version,
        "transport": transport,
        "memory_policy": "separate_no_merge",
        "bounded_context_only": True,
        "raw_memory_exchange_allowed": False,
        "raw_secret_persistence_allowed": False,
        "operator_approved": operator_approved,
        "write_capability": write_capability,
        "execution_performed": False,
        "steps": [
            "verify_signed_envelope",
            "resolve_bounded_context_ref",
            "create_isolated_worktree_if_required",
            "invoke_hermes_transport",
            "run_allowlisted_evaluators",
            "emit_result_and_receipt",
        ],
        "blockers": sorted(set(blockers)),
        "next_action": "execute_hermes_task_in_isolated_worktree" if not blockers else "repair_hermes_executor_plan",
    }
    plan["plan_hash"] = _stable_hash(plan)
    return plan


def verify_hermes_result(
    *,
    plan: dict[str, object],
    result: dict[str, object],
) -> dict[str, object]:
    blockers = []
    if plan.get("status") != "ready":
        blockers.append("hermes_plan_not_ready")
    if result.get("envelope_id") != plan.get("envelope_id"):
        blockers.append("hermes_result_envelope_mismatch")
    if result.get("memory_policy") != "separate_no_merge":
        blockers.append("hermes_memory_policy_violation")
    if result.get("raw_memory_persisted") is not False:
        blockers.append("hermes_raw_memory_persisted")
    if result.get("raw_secret_persisted") is not False:
        blockers.append("hermes_raw_secret_persisted")
    if result.get("status") not in {"completed", "blocked", "failed"}:
        blockers.append("hermes_result_status_invalid")
    verified = not blockers
    receipt = {
        "verification_type": "hermes_executor_result_verification_v1",
        "status": "verified" if verified else "blocked",
        "plan_hash": plan.get("plan_hash"),
        "envelope_id": plan.get("envelope_id"),
        "result_status": result.get("status"),
        "memory_policy": result.get("memory_policy"),
        "raw_memory_persisted": result.get("raw_memory_persisted"),
        "raw_secret_persisted": result.get("raw_secret_persisted"),
        "result_hash": _stable_hash(result),
        "verified": verified,
        "merge_allowed": False,
        "merge_performed": False,
        "blockers": blockers,
        "next_action": "evaluate_candidate_evidence" if verified else "quarantine_hermes_result",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
