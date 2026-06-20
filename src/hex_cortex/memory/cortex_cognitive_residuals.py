from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_RESIDUAL_TYPE = "cognitive_residual_record_v1"
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


def build_residual_signature(
    *,
    failure_class: str,
    domain: str,
    best_corrective_intervention: str | None,
) -> str:
    if failure_class not in _ALLOWED_FAILURE_CLASSES:
        raise ValueError("failure_class invalid")
    if not domain.strip():
        raise ValueError("domain must be non-empty")
    return _stable_hash(
        {
            "failure_class": failure_class,
            "domain": domain,
            "best_corrective_intervention": best_corrective_intervention,
        }
    )


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
    residual_signature = build_residual_signature(
        failure_class=failure_class,
        domain=domain,
        best_corrective_intervention=best_corrective_intervention,
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
        "residual_signature_scope": "failure_domain_intervention_v1",
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
    if minimum_distinct_contexts < 1 or minimum_distinct_contexts > 1000:
        raise ValueError("minimum_distinct_contexts out of range")
    if minimum_distinct_models < 1 or minimum_distinct_models > 1000:
        raise ValueError("minimum_distinct_models out of range")

    residuals = [
        row
        for row in read_cognitive_records(path)
        if row.get("record_type") == _RESIDUAL_TYPE
    ]
    groups: dict[str, list[dict[str, object]]] = {}
    for row in residuals:
        failure_class = str(row.get("failure_class", ""))
        domain = str(row.get("domain", ""))
        intervention_value = row.get("best_corrective_intervention")
        intervention = str(intervention_value) if intervention_value is not None else None
        try:
            signature = build_residual_signature(
                failure_class=failure_class,
                domain=domain,
                best_corrective_intervention=intervention,
            )
        except ValueError:
            continue
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
                "signature_scope": "failure_domain_intervention_v1",
                "failure_class": rows[0].get("failure_class"),
                "domain": rows[0].get("domain"),
                "occurrence_count": len(rows),
                "distinct_context_count": len(contexts),
                "distinct_model_count": len(models),
                "verified_correction_count": verified,
                "causal_intervention_count": causal,
                "mean_residual_magnitude": (
                    sum(float(row.get("residual_magnitude", 0.0)) for row in rows)
                    / len(rows)
                ),
                "dominant_corrective_intervention": (
                    intervention_counts.most_common(1)[0][0]
                    if intervention_counts
                    else None
                ),
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
        "selected_residual_signature": (
            ready_clusters[0]["residual_signature"] if ready_clusters else None
        ),
        "raw_reasoning_persisted": False,
        "next_action": (
            "build_skill_candidate" if ready_clusters else "collect_verified_residuals"
        ),
    }
    payload["projection_hash"] = _stable_hash(payload)
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
