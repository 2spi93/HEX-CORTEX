from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_GENOME_TYPE = "hex_cortex_cognitive_genome_v1"
_RESIDUAL_TYPE = "cognitive_residual_record_v1"
_SKILL_TYPE = "cognitive_skill_candidate_v1"
_MUTATION_PLAN_TYPE = "cognitive_mutation_plan_v1"
_MUTATION_EVALUATION_TYPE = "cognitive_mutation_evaluation_v1"
_ALLOWED_FAILURE_CLASSES = {
    "knowledge_gap",
    "logic_error",
    "planning_error",
    "context_loss",
    "tool_misuse",
    "hallucination",
    "ambiguity_failure",
    "capability_limit",
    "uncertainty_failure",
    "causal_misattribution",
}
_ALLOWED_MUTATION_LEVELS = {
    "external_memory",
    "skill_procedure",
    "router_update",
    "isolated_adapter_candidate",
    "full_weight_update",
}
_PROFILE_ORDER = (
    "archivist",
    "researcher",
    "scientist",
    "causalist",
    "engineer",
    "statistician",
    "adversary",
    "explorer",
    "constitutional_judge",
)


def load_cognitive_genome(path: Path) -> dict[str, object]:
    target = path.resolve()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def audit_cognitive_genome(path: Path) -> dict[str, object]:
    payload = load_cognitive_genome(path)
    blockers: list[str] = []
    if payload.get("genome_type") != _GENOME_TYPE:
        blockers.append("cognitive_genome_type_invalid")
    if payload.get("schema_version") != 1:
        blockers.append("cognitive_genome_schema_version_invalid")

    identity = payload.get("identity")
    if not isinstance(identity, dict):
        blockers.append("cognitive_genome_identity_missing")
        identity = {}
    for key, expected in {
        "base_model_interchangeable": True,
        "base_model_immutable_by_default": True,
        "raw_chain_of_thought_persistence_allowed": False,
        "autonomous_weight_mutation_allowed": False,
        "operator_approval_required_for_promotion": True,
    }.items():
        if identity.get(key) is not expected:
            blockers.append(f"cognitive_genome_identity_{key}_invalid")

    ontology = payload.get("error_ontology")
    if not isinstance(ontology, list) or not _ALLOWED_FAILURE_CLASSES.issubset(set(ontology)):
        blockers.append("cognitive_error_ontology_incomplete")

    profiles = payload.get("profile_council")
    if not isinstance(profiles, list) or not set(_PROFILE_ORDER).issubset(set(profiles)):
        blockers.append("cognitive_profile_council_incomplete")

    mutation_policy = payload.get("mutation_policy")
    if not isinstance(mutation_policy, dict):
        blockers.append("cognitive_mutation_policy_missing")
        mutation_policy = {}
    for key, expected in {
        "full_weight_update_enabled": False,
        "worktree_required": True,
        "heldout_required": True,
        "reversibility_required": True,
        "evaluator_mutation_allowed": False,
        "threshold_reduction_allowed": False,
        "automatic_merge_allowed": False,
    }.items():
        if mutation_policy.get(key) is not expected:
            blockers.append(f"cognitive_mutation_policy_{key}_invalid")

    cr_jepa = payload.get("cr_jepa_v0")
    if not isinstance(cr_jepa, dict):
        blockers.append("cr_jepa_descriptor_missing")
        cr_jepa = {}
    if cr_jepa.get("descriptor_type") != "cognitive_residual_jepa_v0":
        blockers.append("cr_jepa_descriptor_type_invalid")
    if cr_jepa.get("training_enabled") is not False:
        blockers.append("cr_jepa_training_must_start_disabled")
    if cr_jepa.get("raw_reasoning_required") is not False:
        blockers.append("cr_jepa_raw_reasoning_policy_invalid")

    ready = not blockers
    result = {
        "audit_type": "cognitive_genome_audit_v1",
        "genome_path": str(path.resolve()),
        "genome_ready": ready,
        "schema_version": payload.get("schema_version"),
        "error_class_count": len(ontology) if isinstance(ontology, list) else 0,
        "profile_count": len(profiles) if isinstance(profiles, list) else 0,
        "base_model_immutable": identity.get("base_model_immutable_by_default") is True,
        "full_weight_update_enabled": mutation_policy.get("full_weight_update_enabled") is True,
        "cr_jepa_v0_present": cr_jepa.get("descriptor_type") == "cognitive_residual_jepa_v0",
        "blockers": sorted(set(blockers)),
        "next_action": "operate_cognitive_genome" if ready else "repair_cognitive_genome",
    }
    result["audit_hash"] = _stable_hash(result)
    return result


def append_cognitive_residual(
    path: Path,
    *,
    model_id: str,
    model_family: str,
    domain: str,
    context_signature: str,
    state_embedding_ref: str,
    predicted_outcome_ref: str,
    observed_outcome_ref: str,
    failure_class: str,
    residual_magnitude: float,
    profile_set: Iterable[str],
    tool_set: Iterable[str],
    correction_ref: str | None = None,
    correction_verified: bool = False,
    causal_intervention_verified: bool = False,
    best_corrective_intervention: str | None = None,
) -> dict[str, object]:
    for label, value in {
        "model_id": model_id,
        "model_family": model_family,
        "domain": domain,
        "context_signature": context_signature,
        "state_embedding_ref": state_embedding_ref,
        "predicted_outcome_ref": predicted_outcome_ref,
        "observed_outcome_ref": observed_outcome_ref,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if failure_class not in _ALLOWED_FAILURE_CLASSES:
        raise ValueError("failure_class invalid")
    if residual_magnitude < 0.0 or residual_magnitude > 1_000_000.0:
        raise ValueError("residual_magnitude out of range")
    if correction_verified and not correction_ref:
        raise ValueError("correction_ref required when correction is verified")
    if causal_intervention_verified and not best_corrective_intervention:
        raise ValueError("best_corrective_intervention required for causal verification")

    profiles = sorted(set(_clean_values(profile_set)))
    tools = sorted(set(_clean_values(tool_set)))
    residual_signature = _stable_hash(
        {
            "failure_class": failure_class,
            "domain": domain,
            "context_signature": context_signature,
            "best_corrective_intervention": best_corrective_intervention,
        }
    )
    record = {
        "record_type": _RESIDUAL_TYPE,
        "residual_id": f"cres_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "model_id_hash": _hash_text(model_id),
        "model_family": model_family,
        "domain": domain,
        "context_signature_hash": _hash_text(context_signature),
        "state_embedding_ref_hash": _hash_text(state_embedding_ref),
        "predicted_outcome_ref_hash": _hash_text(predicted_outcome_ref),
        "observed_outcome_ref_hash": _hash_text(observed_outcome_ref),
        "failure_class": failure_class,
        "residual_magnitude": float(residual_magnitude),
        "profile_set": profiles,
        "tool_set": tools,
        "correction_ref_hash": _hash_text(correction_ref) if correction_ref else None,
        "correction_verified": correction_verified,
        "causal_intervention_verified": causal_intervention_verified,
        "best_corrective_intervention": best_corrective_intervention,
        "residual_signature": residual_signature,
        "raw_state_persisted": False,
        "raw_reasoning_persisted": False,
        "raw_outcome_persisted": False,
        "raw_secret_persisted": False,
    }
    record["record_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def read_cognitive_records(path: Path) -> list[dict[str, object]]:
    target = path.resolve()
    if not target.exists():
        return []
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid cognitive JSONL at line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"cognitive record at line {line_number} must be an object")
        rows.append(payload)
    return rows


def project_residual_topology(
    path: Path,
    *,
    minimum_recurrences: int = 3,
    minimum_distinct_contexts: int = 2,
    minimum_distinct_models: int = 2,
) -> dict[str, object]:
    if minimum_recurrences < 2 or minimum_recurrences > 1000:
        raise ValueError("minimum_recurrences out of range")
    residuals = [
        row
        for row in read_cognitive_records(path)
        if row.get("record_type") == _RESIDUAL_TYPE
    ]
    groups: dict[str, list[dict[str, object]]] = {}
    for row in residuals:
        signature = str(row.get("residual_signature", ""))
        if signature:
            groups.setdefault(signature, []).append(row)

    clusters = []
    for signature, rows in sorted(groups.items()):
        contexts = {str(row.get("context_signature_hash")) for row in rows}
        models = {str(row.get("model_id_hash")) for row in rows}
        verified = sum(row.get("correction_verified") is True for row in rows)
        causal = sum(row.get("causal_intervention_verified") is True for row in rows)
        intervention_counts = Counter(
            str(row.get("best_corrective_intervention"))
            for row in rows
            if row.get("best_corrective_intervention")
        )
        consolidation_ready = (
            len(rows) >= minimum_recurrences
            and len(contexts) >= minimum_distinct_contexts
            and len(models) >= minimum_distinct_models
            and verified == len(rows)
            and causal > 0
        )
        clusters.append(
            {
                "residual_signature": signature,
                "occurrence_count": len(rows),
                "distinct_context_count": len(contexts),
                "distinct_model_count": len(models),
                "verified_correction_count": verified,
                "causal_intervention_count": causal,
                "mean_residual_magnitude": sum(float(row.get("residual_magnitude", 0.0)) for row in rows) / len(rows),
                "dominant_corrective_intervention": intervention_counts.most_common(1)[0][0] if intervention_counts else None,
                "skill_consolidation_ready": consolidation_ready,
            }
        )

    ready_clusters = [row for row in clusters if row["skill_consolidation_ready"] is True]
    payload = {
        "projection_type": "cognitive_residual_topology_v1",
        "residual_count": len(residuals),
        "cluster_count": len(clusters),
        "consolidation_ready_count": len(ready_clusters),
        "clusters": clusters,
        "selected_residual_signature": ready_clusters[0]["residual_signature"] if ready_clusters else None,
        "raw_reasoning_persisted": False,
        "next_action": "build_skill_candidate" if ready_clusters else "collect_verified_residuals",
    }
    payload["projection_hash"] = _stable_hash(payload)
    return payload


def build_skill_candidate(
    topology: dict[str, object],
    *,
    residual_signature: str,
    skill_id: str,
    domain: str,
) -> dict[str, object]:
    clusters = topology.get("clusters")
    rows = clusters if isinstance(clusters, list) else []
    selected = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and row.get("residual_signature") == residual_signature
        ),
        None,
    )
    blockers = []
    if selected is None:
        blockers.append("residual_cluster_not_found")
    elif selected.get("skill_consolidation_ready") is not True:
        blockers.append("residual_cluster_not_consolidation_ready")
    if not skill_id.strip():
        blockers.append("skill_id_missing")
    if not domain.strip():
        blockers.append("skill_domain_missing")
    ready = not blockers
    payload = {
        "record_type": _SKILL_TYPE,
        "status": "candidate" if ready else "blocked",
        "skill_id": skill_id,
        "domain": domain,
        "source_residual_signature": residual_signature,
        "corrective_intervention": selected.get("dominant_corrective_intervention") if selected else None,
        "occurrence_count": selected.get("occurrence_count") if selected else 0,
        "distinct_context_count": selected.get("distinct_context_count") if selected else 0,
        "distinct_model_count": selected.get("distinct_model_count") if selected else 0,
        "promotion_allowed": False,
        "adapter_training_allowed": ready,
        "operator_approval_required": True,
        "blockers": blockers,
        "next_action": "build_mutation_plan" if ready else "collect_more_residual_evidence",
    }
    payload["candidate_hash"] = _stable_hash(payload)
    return payload


def build_profile_council(
    *,
    failure_class: str,
    novelty: float,
    uncertainty: float,
    mutation_requested: bool = False,
) -> dict[str, object]:
    if failure_class not in _ALLOWED_FAILURE_CLASSES:
        raise ValueError("failure_class invalid")
    for label, value in {"novelty": novelty, "uncertainty": uncertainty}.items():
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{label} out of range")

    profiles = {"archivist", "adversary"}
    if failure_class in {"knowledge_gap", "hallucination", "ambiguity_failure"}:
        profiles.update({"researcher", "scientist"})
    if failure_class in {"logic_error", "planning_error", "tool_misuse"}:
        profiles.update({"engineer", "scientist"})
    if failure_class in {"causal_misattribution", "planning_error"}:
        profiles.add("causalist")
    if failure_class in {"uncertainty_failure", "capability_limit"}:
        profiles.add("statistician")
    if novelty >= 0.6:
        profiles.add("explorer")
    if mutation_requested or uncertainty >= 0.8:
        profiles.add("constitutional_judge")

    ordered = [profile for profile in _PROFILE_ORDER if profile in profiles]
    payload = {
        "plan_type": "cognitive_profile_council_v1",
        "failure_class": failure_class,
        "novelty": novelty,
        "uncertainty": uncertainty,
        "mutation_requested": mutation_requested,
        "selected_profiles": ordered,
        "profile_count": len(ordered),
        "majority_vote_allowed": False,
        "evidence_weighted_adjudication_required": True,
        "independent_views_required": len(ordered) >= 3,
        "next_action": "dispatch_profile_council",
    }
    payload["plan_hash"] = _stable_hash(payload)
    return payload


def build_homeostasis_decision(
    *,
    uncertainty: float,
    recurrence_count: int,
    deterministic_verification_available: bool,
    local_verification_failed: bool,
    cost_pressure: float,
    regression_risk: float,
) -> dict[str, object]:
    for label, value in {
        "uncertainty": uncertainty,
        "cost_pressure": cost_pressure,
        "regression_risk": regression_risk,
    }.items():
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{label} out of range")
    if recurrence_count < 0:
        raise ValueError("recurrence_count out of range")

    actions = ["retrieve_skill_memory"]
    if deterministic_verification_available:
        actions.append("run_deterministic_verifier")
    if uncertainty >= 0.65:
        actions.append("increase_test_time_compute")
    if local_verification_failed and uncertainty >= 0.65 and cost_pressure < 0.9:
        actions.append("consult_remote_teacher")
    if recurrence_count >= 3:
        actions.append("propose_skill_consolidation")
    if recurrence_count >= 3 and regression_risk < 0.35:
        actions.append("consider_isolated_adapter_candidate")
    if uncertainty >= 0.85 and not deterministic_verification_available:
        actions.append("refuse_unverified_action")

    payload = {
        "decision_type": "cognitive_homeostasis_decision_v1",
        "selected_actions": actions,
        "weight_mutation_selected": False,
        "remote_teacher_selected": "consult_remote_teacher" in actions,
        "refusal_selected": "refuse_unverified_action" in actions,
        "reversible_path_only": True,
        "next_action": actions[0] if actions else "hold_state",
    }
    payload["decision_hash"] = _stable_hash(payload)
    return payload


def build_mutation_plan(
    *,
    skill_candidate_hash: str,
    mutation_level: str,
    baseline_ref: str,
    evaluator_ref: str,
    revocation_ref: str,
) -> dict[str, object]:
    blockers = []
    if len(skill_candidate_hash) != 64:
        blockers.append("skill_candidate_hash_invalid")
    if mutation_level not in _ALLOWED_MUTATION_LEVELS:
        blockers.append("mutation_level_invalid")
    if mutation_level == "full_weight_update":
        blockers.append("full_weight_update_disabled")
    for label, value in {
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
        "revocation_ref": revocation_ref,
    }.items():
        if not value.strip():
            blockers.append(f"{label}_missing")
    ready = not blockers
    payload = {
        "plan_type": _MUTATION_PLAN_TYPE,
        "status": "ready" if ready else "blocked",
        "skill_candidate_hash": skill_candidate_hash,
        "mutation_level": mutation_level,
        "base_model_immutable": True,
        "isolated_adapter_required": mutation_level == "isolated_adapter_candidate",
        "worktree_required": True,
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
        "evaluator_mutation_allowed": False,
        "threshold_reduction_allowed": False,
        "revocation_ref": revocation_ref,
        "heldout_required": True,
        "automatic_merge_allowed": False,
        "operator_approval_required": True,
        "blockers": blockers,
        "next_action": "run_mutation_sandbox" if ready else "repair_mutation_plan",
    }
    payload["plan_hash"] = _stable_hash(payload)
    return payload


def evaluate_mutation_candidate(
    *,
    plan_hash: str,
    critical_competency_deltas: dict[str, float],
    noncritical_competency_deltas: dict[str, float],
    target_skill_delta: float,
    heldout_passed: bool,
    reversible: bool,
    evaluator_changed: bool,
    threshold_lowered: bool,
) -> dict[str, object]:
    blockers = []
    if len(plan_hash) != 64:
        blockers.append("mutation_plan_hash_invalid")
    if target_skill_delta <= 0.0:
        blockers.append("target_skill_not_improved")
    if not heldout_passed:
        blockers.append("heldout_gate_failed")
    if not reversible:
        blockers.append("mutation_not_reversible")
    if evaluator_changed:
        blockers.append("evaluator_changed")
    if threshold_lowered:
        blockers.append("threshold_lowered")
    for competency, delta in critical_competency_deltas.items():
        if delta < 0.0:
            blockers.append(f"critical_competency_regressed:{competency}")
    for competency, delta in noncritical_competency_deltas.items():
        if delta < -0.02:
            blockers.append(f"noncritical_competency_regressed:{competency}")

    promotable = not blockers
    payload = {
        "evaluation_type": _MUTATION_EVALUATION_TYPE,
        "status": "promotable" if promotable else "rejected",
        "plan_hash": plan_hash,
        "target_skill_delta": target_skill_delta,
        "critical_competency_deltas": critical_competency_deltas,
        "noncritical_competency_deltas": noncritical_competency_deltas,
        "heldout_passed": heldout_passed,
        "reversible": reversible,
        "evaluator_changed": evaluator_changed,
        "threshold_lowered": threshold_lowered,
        "anti_forgetting_passed": not any("competency_regressed" in item for item in blockers),
        "promotion_allowed": promotable,
        "merge_performed": False,
        "operator_approval_required": True,
        "blockers": blockers,
        "next_action": "request_operator_promotion" if promotable else "retain_rejected_mutation_evidence",
    }
    payload["evaluation_hash"] = _stable_hash(payload)
    return payload


def build_cr_jepa_v0_manifest(path: Path) -> dict[str, object]:
    residuals = [
        row
        for row in read_cognitive_records(path)
        if row.get("record_type") == _RESIDUAL_TYPE
    ]
    verified = [row for row in residuals if row.get("correction_verified") is True]
    causal = [row for row in verified if row.get("causal_intervention_verified") is True]
    failure_counts = Counter(str(row.get("failure_class")) for row in residuals)
    payload = {
        "manifest_type": "cognitive_residual_jepa_dataset_manifest_v0",
        "training_allowed": False,
        "residual_count": len(residuals),
        "verified_residual_count": len(verified),
        "causal_residual_count": len(causal),
        "failure_class_counts": dict(sorted(failure_counts.items())),
        "raw_reasoning_required": False,
        "raw_reasoning_persisted": False,
        "minimum_research_gate": {
            "verified_residuals": 1000,
            "causal_residuals": 200,
            "distinct_failure_classes": 6,
            "heldout_split_required": True,
        },
        "next_action": "collect_residual_dataset" if len(verified) < 1000 else "design_cr_jepa_training_experiment",
    }
    payload["manifest_hash"] = _stable_hash(payload)
    return payload


def _clean_values(values: Iterable[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
