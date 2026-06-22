"""Verified-inference planner: the capstone that wires the armor together.

Given a task and the brain registry, this produces a single dry-run *plan*
that a step-4 runtime would execute:

    1. route   pick the primary brain with the risk-aware selector
    2. sample  draw N samples from it (self-consistency)
    3. consensus  majority-vote with a fail-closed threshold
    4. police  accept / resample / escalate / refuse via the policy
    5. escalate  to the most capable distinct eligible brain when needed

It performs no model call, no network, no shell — it only composes the
selector with the verification parameters and emits an advisory contract.
The runtime that later executes it is responsible for the actual sampling
(autonomy ladder step 4+).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry
from hex_cortex.memory.cortex_cognitive_brain_registry import select_cognitive_brain

_PLAN_TYPE = "cortex_verified_inference_plan_v1"


def build_verified_inference_plan(
    ledger: Path,
    *,
    task_domain: str,
    context_sensitivity: str,
    maximum_latency_ms: float,
    cost_pressure: float,
    remote_allowed: bool,
    minimum_acceptable_score: float = 0.55,
    initial_samples: int = 5,
    max_samples: int = 16,
    agreement_threshold: float = 0.5,
    target_confidence: float = 0.7,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Compose router selection with a self-consistency + escalation plan."""
    if initial_samples < 1:
        raise ValueError("initial_samples must be >= 1")
    if max_samples < initial_samples:
        raise ValueError("max_samples must be >= initial_samples")
    if not 0.0 <= target_confidence <= 1.0:
        raise ValueError("target_confidence out of range")

    selection = select_cognitive_brain(
        ledger,
        task_domain=task_domain,
        context_sensitivity=context_sensitivity,
        maximum_latency_ms=maximum_latency_ms,
        cost_pressure=cost_pressure,
        remote_allowed=remote_allowed,
        minimum_acceptable_score=minimum_acceptable_score,
    )

    candidates = selection.get("candidates")
    candidate_list = candidates if isinstance(candidates, list) else []
    primary_id = selection.get("selected_brain_id")

    if selection.get("status") != "ready" or not primary_id:
        plan = _plan_record(
            status="blocked",
            task_domain=task_domain,
            context_sensitivity=context_sensitivity,
            primary_brain_id=None,
            escalation_brain_id=None,
            escalation_diversity="not_applicable",
            initial_samples=initial_samples,
            max_samples=max_samples,
            agreement_threshold=agreement_threshold,
            target_confidence=target_confidence,
            selection_hash=str(selection.get("selection_hash", "")),
            blockers=[str(b) for b in selection.get("blockers", [])] or ["no_primary_brain"],
            next_action="escalate_or_refuse_task",
        )
    else:
        registry = project_brain_registry(ledger)
        brains_value = registry.get("brains")
        brain_table = brains_value if isinstance(brains_value, dict) else {}
        escalation_id = _pick_escalation_brain(
            candidate_list,
            primary_id=str(primary_id),
            brain_table=brain_table,
        )
        plan = _plan_record(
            status="ready",
            task_domain=task_domain,
            context_sensitivity=context_sensitivity,
            primary_brain_id=str(primary_id),
            escalation_brain_id=escalation_id,
            escalation_diversity=(
                "distinct_model_hash" if escalation_id is not None else "no_independent_model_available"
            ),
            initial_samples=initial_samples,
            max_samples=max_samples,
            agreement_threshold=agreement_threshold,
            target_confidence=target_confidence,
            selection_hash=str(selection.get("selection_hash", "")),
            blockers=[],
            next_action="execute_verified_inference_plan",
        )

    if receipt_path is not None:
        _append_jsonl(receipt_path, plan)
    return plan


def _pick_escalation_brain(
    candidates: list[dict[str, object]],
    *,
    primary_id: str,
    brain_table: dict[str, object],
) -> str | None:
    """Pick a capable brain backed by a different underlying model identity.

    A distinct ``brain_id`` is not enough: multiple benchmark phenotypes may
    point to the same Ollama model. Such aliases are useful for measurement
    history but do not provide independent reasoning or criticism. Escalation
    therefore excludes candidates with the primary model's persisted hash.
    """
    primary_record = brain_table.get(primary_id)
    primary = primary_record if isinstance(primary_record, dict) else {}
    primary_model_hash = primary.get("model_id_hash")
    others: list[dict[str, object]] = []
    for candidate in candidates:
        brain_id = str(candidate.get("brain_id"))
        if brain_id == primary_id:
            continue
        record_value = brain_table.get(brain_id)
        record = record_value if isinstance(record_value, dict) else {}
        model_hash = record.get("model_id_hash")
        if primary_model_hash and model_hash == primary_model_hash:
            continue
        others.append(candidate)
    if not others:
        return None
    best = max(
        others,
        key=lambda candidate: (
            float(candidate.get("robust_competence", candidate.get("domain_competence", 0.0))),
            float(candidate.get("reliability", 0.0)),
            str(candidate.get("brain_id")),
        ),
    )
    return str(best.get("brain_id"))


def _plan_record(
    *,
    status: str,
    task_domain: str,
    context_sensitivity: str,
    primary_brain_id: str | None,
    escalation_brain_id: str | None,
    escalation_diversity: str,
    initial_samples: int,
    max_samples: int,
    agreement_threshold: float,
    target_confidence: float,
    selection_hash: str,
    blockers: list[str],
    next_action: str,
) -> dict[str, object]:
    record = {
        "record_type": _PLAN_TYPE,
        "event_id": f"verifplan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "task_domain": task_domain,
        "context_sensitivity": context_sensitivity,
        "primary_brain_id": primary_brain_id,
        "escalation_brain_id": escalation_brain_id,
        "escalation_diversity": escalation_diversity,
        "sampling_plan": {
            "initial_samples": initial_samples,
            "max_samples": max_samples,
            "agreement_threshold": agreement_threshold,
            "target_confidence": target_confidence,
        },
        "stages": [
            "route_primary_brain",
            "sample_self_consistency",
            "aggregate_consensus",
            "apply_escalation_policy",
        ],
        "source_selection_hash": selection_hash,
        "safety_mode": "advisory_only_no_direct_execution_no_state_mutation",
        "model_call_performed": False,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "blockers": blockers,
        "next_action": next_action,
    }
    record["plan_hash"] = _stable_hash(record)
    return record


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
