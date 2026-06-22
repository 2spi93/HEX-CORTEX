from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry
from hex_cortex.memory.cortex_coding_model_executor import execute_coding_model_task
from hex_cortex.memory.cortex_gpu_governor import decide_gpu_admission
from hex_cortex.memory.cortex_pot_evaluator import grade_arithmetic
from hex_cortex.memory.cortex_repo_context import build_bounded_repo_context
from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_structured_code_plan import aggregate_structured_code_plans
from hex_cortex.memory.cortex_structured_code_plan import code_plan_json_schema
from hex_cortex.memory.cortex_verification_policy import decide_verification_action

JsonTransport = Callable[[str, str, dict[str, str], dict[str, object], float], dict[str, object]]

_EXECUTION_PHRASE = "EXECUTE_VERIFIED_LOCAL_LOOP"
_MAX_PRIMARY_SAMPLES = 5
_MAX_VERIFICATION_SAMPLES = 16


def execute_verified_local_loop(
    plan: dict[str, object],
    *,
    ledger: Path,
    gpu_snapshot: dict[str, object],
    model: str,
    instruction: str,
    task_prompt: str,
    bounded_context: str = "",
    repo_root: Path | None = None,
    auto_repo_context: bool = False,
    structured_code_plan: bool = False,
    repo_context_max_modules: int = 10,
    repo_context_max_chars: int = 12_000,
    local_endpoint: str = "http://127.0.0.1:11434",
    max_output_tokens: int = 2048,
    timeout_seconds: float = 120.0,
    sample_temperature: float = 0.2,
    ollama_keep_alive: str = "2m",
    expected_numeric: float | None = None,
    operator_approved: bool = False,
    confirmation: str = "",
    transport: JsonTransport | None = None,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Execute only the primary local sampling phase of a verified loop plan.

    This runtime deliberately stops before model escalation, shell execution,
    patch application, tests, or repository mutation. Each later stage requires
    a separate operator decision. Raw prompts and model responses are returned
    only transiently and are never written to the receipt.
    """
    blockers = _validate_execution_request(
        plan,
        ledger=ledger,
        model=model,
        gpu_snapshot=gpu_snapshot,
        repo_root=repo_root,
        auto_repo_context=auto_repo_context,
        structured_code_plan=structured_code_plan,
        expected_numeric=expected_numeric,
        operator_approved=operator_approved,
        confirmation=confirmation,
    )
    if blockers:
        return _blocked(blockers, plan_hash=plan.get("plan_hash"))

    context_meta: dict[str, object] = {
        "repo_context_hash": None,
        "repo_context_module_count": 0,
        "repo_context_chars": 0,
        "structured_code_plan": structured_code_plan,
        "structured_schema_hash": None,
    }
    allowed_paths: set[str] = set()
    effective_context = bounded_context
    response_format: dict[str, object] | None = None
    effective_instruction = instruction

    if auto_repo_context and repo_root is not None:
        repo_context = build_bounded_repo_context(
            repo_root,
            task_prompt,
            max_modules=repo_context_max_modules,
            max_chars=repo_context_max_chars,
        )
        context_text = str(repo_context["context_text"])
        effective_context = (
            f"{bounded_context}\n\n{context_text}" if bounded_context else context_text
        )
        allowed_paths = {str(path) for path in repo_context["allowed_paths"]}
        context_meta.update(
            {
                "repo_context_hash": repo_context.get("context_hash"),
                "repo_context_module_count": repo_context.get("module_count", 0),
                "repo_context_chars": repo_context.get("context_chars", 0),
            }
        )

    if structured_code_plan:
        response_format = code_plan_json_schema()
        context_meta["structured_schema_hash"] = _stable_hash(response_format)
        effective_instruction = (
            f"{instruction.strip()}\n\n"
            "Return only one JSON object matching the supplied schema. "
            "Use only repository paths present in bounded_context. "
            "When evidence is insufficient, use unknowns instead of inventing files."
        )

    requested_tier = str(plan.get("granted_tier", "small"))
    fresh_gpu = decide_gpu_admission(
        gpu_snapshot,
        {"tier": requested_tier, "is_benchmark": False},
    )
    if fresh_gpu.get("action") not in {"admit", "downgrade"}:
        return _blocked(
            [f"fresh_gpu_{fresh_gpu.get('action', 'unknown')}"],
            plan_hash=plan.get("plan_hash"),
            fresh_gpu=fresh_gpu,
        )

    sample_count = int(plan["samples"])
    sample_hashes: list[str] = []
    volatile_samples: list[str] = []
    call_receipt_hashes: list[str] = []
    failed_call_index: int | None = None
    failure_call: dict[str, object] | None = None

    for index in range(sample_count):
        keep_alive = "0" if index == sample_count - 1 else ollama_keep_alive
        call = execute_coding_model_task(
            provider_id="local_ollama",
            model=model,
            instruction=effective_instruction,
            task_prompt=task_prompt,
            bounded_context=effective_context,
            context_sensitivity=str(plan["context_sensitivity"]),
            local_endpoint=local_endpoint,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            temperature=0.0 if sample_count == 1 else sample_temperature,
            ollama_keep_alive=keep_alive,
            response_format=response_format,
            operator_approved=True,
            transport=transport,
        )
        call_receipt_hashes.append(str(call.get("receipt_hash", "")))
        text = call.get("volatile_result_text")
        if call.get("status") != "completed" or not isinstance(text, str) or not text.strip():
            failed_call_index = index
            failure_call = call
            break
        volatile_samples.append(text)
        sample_hashes.append(hashlib.sha256(text.encode("utf-8")).hexdigest())

    if failed_call_index is not None:
        return _execution_receipt(
            plan=plan,
            model=model,
            status="failed",
            sample_count_requested=sample_count,
            sample_hashes=sample_hashes,
            call_receipt_hashes=call_receipt_hashes,
            fresh_gpu=fresh_gpu,
            consensus=None,
            verification=None,
            deterministic_grade=None,
            volatile_consensus_answer="",
            blockers=[f"primary_model_call_failed_at_index:{failed_call_index}"],
            next_action="repair_local_model_runtime",
            receipt_path=receipt_path,
            failure_call=failure_call,
            context_meta=context_meta,
        )

    weights = None
    if _weighted_vote_requested(plan):
        weight = _primary_brain_weight(ledger, str(plan["primary_brain_id"]))
        weights = [weight] * sample_count

    if structured_code_plan:
        consensus = aggregate_structured_code_plans(
            volatile_samples,
            allowed_paths=allowed_paths,
            sample_weights=weights,
        )
    else:
        mode = "numeric" if plan.get("exact_arithmetic_domain") is True else "text"
        consensus = aggregate_self_consistency(
            volatile_samples,
            mode=mode,
            agreement_threshold=0.5,
            sample_weights=weights,
        )

    deterministic_grade = None
    if plan.get("use_deterministic_tool") is True:
        deterministic_grade = grade_arithmetic(
            str(consensus["consensus_answer"]),
            float(expected_numeric),
        )
        if deterministic_grade.get("correct") is not True:
            return _execution_receipt(
                plan=plan,
                model=model,
                status="refused",
                sample_count_requested=sample_count,
                sample_hashes=sample_hashes,
                call_receipt_hashes=call_receipt_hashes,
                fresh_gpu=fresh_gpu,
                consensus=consensus,
                verification=None,
                deterministic_grade=deterministic_grade,
                volatile_consensus_answer=str(consensus["consensus_answer"]),
                blockers=["deterministic_verifier_refuted_consensus"],
                next_action="revise_reasoning_before_any_execution",
                receipt_path=receipt_path,
                context_meta=context_meta,
            )

    if plan.get("verification_gap") is True:
        status = "needs_human_review"
        verification = {
            "policy_type": "cortex_verification_policy_v1",
            "action": "human_review",
            "reason": "independent_model_unavailable_for_required_critique",
            "model_call_performed": False,
            "fail_closed": True,
        }
        blockers = ["independent_critic_unavailable"]
        next_action = "operator_review_primary_consensus"
    elif plan.get("use_self_consistency") is not True:
        status = "needs_human_review"
        verification = {
            "policy_type": "cortex_verification_policy_v1",
            "action": "human_review",
            "reason": "single_sample_has_no_independent_verification",
            "model_call_performed": False,
            "fail_closed": True,
        }
        blockers = ["single_sample_unverified"]
        next_action = "operator_review_primary_answer"
    else:
        verification = decide_verification_action(
            consensus,
            target_confidence=float(plan.get("target_confidence", 0.7)),
            max_samples=_MAX_VERIFICATION_SAMPLES,
            stronger_brain_available=bool(plan.get("escalation_brain_id")),
        )
        status, blockers, next_action = _resolve_next_stage(plan, verification)

    return _execution_receipt(
        plan=plan,
        model=model,
        status=status,
        sample_count_requested=sample_count,
        sample_hashes=sample_hashes,
        call_receipt_hashes=call_receipt_hashes,
        fresh_gpu=fresh_gpu,
        consensus=consensus,
        verification=verification,
        deterministic_grade=deterministic_grade,
        volatile_consensus_answer=str(consensus["consensus_answer"]),
        blockers=blockers,
        next_action=next_action,
        receipt_path=receipt_path,
        context_meta=context_meta,
    )


def _validate_execution_request(
    plan: dict[str, object],
    *,
    ledger: Path,
    model: str,
    gpu_snapshot: dict[str, object],
    repo_root: Path | None,
    auto_repo_context: bool,
    structured_code_plan: bool,
    expected_numeric: float | None,
    operator_approved: bool,
    confirmation: str,
) -> list[str]:
    blockers: list[str] = []
    if plan.get("record_type") != "cortex_cognitive_loop_plan_v1":
        blockers.append("plan_type_invalid")
    if plan.get("status") != "ready":
        blockers.append("plan_not_ready")
    if not _plan_hash_valid(plan):
        blockers.append("plan_hash_invalid")
    if not operator_approved:
        blockers.append("operator_approval_required")
    if confirmation != _EXECUTION_PHRASE:
        blockers.append("confirmation_phrase_invalid")
    if not isinstance(gpu_snapshot, dict):
        blockers.append("gpu_snapshot_invalid")
    samples = plan.get("samples")
    if isinstance(samples, bool) or not isinstance(samples, int):
        blockers.append("sample_count_invalid")
    elif not 1 <= samples <= _MAX_PRIMARY_SAMPLES:
        blockers.append("sample_count_exceeds_bounded_runtime")
    if plan.get("primary_brain_id") in {None, ""}:
        blockers.append("primary_brain_missing")
    if not model.strip():
        blockers.append("model_missing")
    if plan.get("use_deterministic_tool") is True and expected_numeric is None:
        blockers.append("expected_numeric_required_for_deterministic_verifier")
    if auto_repo_context and repo_root is None:
        blockers.append("repo_root_required_for_auto_context")
    if repo_root is not None and not repo_root.resolve().is_dir():
        blockers.append("repo_root_invalid")
    if structured_code_plan and not auto_repo_context:
        blockers.append("structured_code_plan_requires_auto_repo_context")
    if structured_code_plan and plan.get("exact_arithmetic_domain") is True:
        blockers.append("structured_code_plan_incompatible_with_arithmetic_mode")
    if not ledger.resolve().is_file():
        blockers.append("brain_ledger_missing")
    elif model.strip() and plan.get("primary_brain_id"):
        try:
            if not _model_matches_primary(ledger, str(plan["primary_brain_id"]), model):
                blockers.append("model_does_not_match_primary_brain")
        except ValueError:
            blockers.append("brain_ledger_invalid")
    return sorted(set(blockers))


def _resolve_next_stage(
    plan: dict[str, object],
    verification: dict[str, object],
) -> tuple[str, list[str], str]:
    action = verification.get("action")
    critic_required = plan.get("use_adversarial_critique") is True
    critic_available = bool(plan.get("escalation_brain_id"))
    human_required = plan.get("require_human_validation") is True

    if action == "accept":
        if critic_required and critic_available:
            return "needs_escalation", [], "execute_separately_approved_critic"
        if critic_required or human_required:
            return (
                "needs_human_review",
                ["independent_critic_unavailable"] if critic_required and not critic_available else [],
                "operator_review_verified_primary_answer",
            )
        return "completed", [], "present_verified_answer"
    if action == "resample":
        return "needs_more_samples", [], "request_separate_resample_approval"
    if action == "escalate":
        if critic_available:
            return "needs_escalation", [], "execute_separately_approved_escalation"
        return (
            "needs_human_review",
            ["no_independent_model_available"],
            "operator_review_unresolved_consensus",
        )
    return "refused", ["verification_policy_refused"], "do_not_use_model_answer"


def _execution_receipt(
    *,
    plan: dict[str, object],
    model: str,
    status: str,
    sample_count_requested: int,
    sample_hashes: list[str],
    call_receipt_hashes: list[str],
    fresh_gpu: dict[str, object],
    consensus: dict[str, object] | None,
    verification: dict[str, object] | None,
    deterministic_grade: dict[str, object] | None,
    volatile_consensus_answer: str,
    blockers: list[str],
    next_action: str,
    receipt_path: Path | None,
    failure_call: dict[str, object] | None = None,
    context_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    failed = failure_call or {}
    metadata = context_meta or {}
    persisted = {
        "receipt_type": "verified_local_loop_execution_v1",
        "status": status,
        "source_plan_hash": plan.get("plan_hash"),
        "primary_brain_id": plan.get("primary_brain_id"),
        "model_id_hash": hashlib.sha256(model.encode("utf-8")).hexdigest(),
        "sample_count_requested": sample_count_requested,
        "sample_count_completed": len(sample_hashes),
        "sample_hashes": sample_hashes,
        "model_call_receipt_hashes": call_receipt_hashes,
        "model_error_type": failed.get("error_type"),
        "model_error_status_code": failed.get("error_status_code"),
        "model_error_message_hash": failed.get("error_message_hash"),
        "ollama_cleanup_attempted": failed.get("cleanup_attempted", False),
        "ollama_cleanup_succeeded": failed.get("cleanup_succeeded", False),
        "ollama_cleanup_error_type": failed.get("cleanup_error_type"),
        "repo_context_hash": metadata.get("repo_context_hash"),
        "repo_context_module_count": metadata.get("repo_context_module_count", 0),
        "repo_context_chars": metadata.get("repo_context_chars", 0),
        "structured_code_plan": metadata.get("structured_code_plan", False),
        "structured_schema_hash": metadata.get("structured_schema_hash"),
        "grounding_ratio": consensus.get("grounding_ratio") if consensus else None,
        "invalid_path_count": len(consensus.get("invalid_paths", [])) if consensus else 0,
        "fresh_gpu_action": fresh_gpu.get("action"),
        "fresh_gpu_granted_tier": fresh_gpu.get("granted_tier"),
        "consensus_event_hash": consensus.get("event_hash") if consensus else None,
        "consensus_status": consensus.get("status") if consensus else None,
        "consensus_confidence": consensus.get("confidence_wilson_lower") if consensus else None,
        "verification_action": verification.get("action") if verification else None,
        "verification_reason": verification.get("reason") if verification else None,
        "deterministic_correct": deterministic_grade.get("correct") if deterministic_grade else None,
        "operator_approved": True,
        "confirmation_phrase_matched": True,
        "model_call_performed": bool(call_receipt_hashes),
        "repository_mutation_performed": False,
        "shell_command_performed": False,
        "patch_applied": False,
        "tests_executed": False,
        "automatic_escalation_performed": False,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_repo_context_persisted": False,
        "raw_consensus_answer_persisted": False,
        "raw_error_message_persisted": False,
        "blockers": blockers,
        "next_action": next_action,
    }
    persisted["receipt_hash"] = _stable_hash(persisted)
    if receipt_path is not None:
        _append_jsonl(receipt_path, persisted)
    result = dict(persisted)
    result["volatile_consensus_answer"] = volatile_consensus_answer
    result["volatile_error_message"] = str(failed.get("volatile_error_message", ""))
    result["consensus"] = consensus
    result["verification"] = verification
    result["deterministic_grade"] = deterministic_grade
    return result


def _blocked(
    blockers: list[str],
    *,
    plan_hash: object,
    fresh_gpu: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "receipt_type": "verified_local_loop_execution_v1",
        "status": "blocked",
        "source_plan_hash": plan_hash,
        "fresh_gpu_action": fresh_gpu.get("action") if fresh_gpu else None,
        "model_call_performed": False,
        "repository_mutation_performed": False,
        "shell_command_performed": False,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_verified_execution_inputs",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _weighted_vote_requested(plan: dict[str, object]) -> bool:
    components = plan.get("components")
    strategy = components.get("strategy") if isinstance(components, dict) else None
    return isinstance(strategy, dict) and strategy.get("weighted_vote") is True


def _primary_brain_weight(ledger: Path, brain_id: str) -> float:
    registry = project_brain_registry(ledger)
    brains = registry.get("brains")
    table = brains if isinstance(brains, dict) else {}
    row = table.get(brain_id)
    brain = row if isinstance(row, dict) else {}
    reliability = float(brain.get("reliability_score", 0.0))
    uncertainty = float(brain.get("reliability_ci95", 0.0))
    errors = float(brain.get("error_rate", 0.0))
    return max(0.01, reliability - uncertainty - errors)


def _model_matches_primary(ledger: Path, brain_id: str, model: str) -> bool:
    registry = project_brain_registry(ledger)
    brains = registry.get("brains")
    table = brains if isinstance(brains, dict) else {}
    row = table.get(brain_id)
    if not isinstance(row, dict):
        return False
    return row.get("model_id_hash") == hashlib.sha256(model.encode("utf-8")).hexdigest()


def _plan_hash_valid(plan: dict[str, object]) -> bool:
    provided = plan.get("plan_hash")
    if not isinstance(provided, str) or len(provided) != 64:
        return False
    body = {key: value for key, value in plan.items() if key != "plan_hash"}
    return _stable_hash(body) == provided


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


__all__ = ["execute_verified_local_loop"]
