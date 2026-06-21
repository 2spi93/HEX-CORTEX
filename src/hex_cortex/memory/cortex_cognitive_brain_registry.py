from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_BRAIN_EVENT_TYPE = "cognitive_brain_phenotype_event_v1"
_PROVIDER_SCOPES = {"local", "private_remote", "metered_remote"}
_PRIVACY_LEVELS = {"public", "private", "secret"}


def append_brain_phenotype(
    path: Path,
    *,
    brain_id: str,
    model_id: str,
    model_family: str,
    runtime_id: str,
    node_id: str,
    provider_scope: str,
    domain_scores: dict[str, float],
    reliability_score: float,
    latency_ms: float,
    normalized_cost: float,
    baseline_hash: str,
    parameter_class: str = "unknown",
    quantization: str = "unknown",
    available: bool = True,
    reliability_ci95: float = 0.0,
    error_rate: float = 0.0,
) -> dict[str, object]:
    for label, value in {
        "brain_id": brain_id,
        "model_id": model_id,
        "model_family": model_family,
        "runtime_id": runtime_id,
        "node_id": node_id,
        "parameter_class": parameter_class,
        "quantization": quantization,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if provider_scope not in _PROVIDER_SCOPES:
        raise ValueError("provider_scope invalid")
    if len(baseline_hash) != 64:
        raise ValueError("baseline_hash invalid")
    if not domain_scores or not all(
        isinstance(domain, str)
        and domain.strip()
        and isinstance(score, int | float)
        and 0.0 <= float(score) <= 1.0
        for domain, score in domain_scores.items()
    ):
        raise ValueError("domain_scores invalid")
    for label, value in {
        "reliability_score": reliability_score,
        "normalized_cost": normalized_cost,
        "reliability_ci95": reliability_ci95,
        "error_rate": error_rate,
    }.items():
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{label} out of range")
    if latency_ms < 0.0 or latency_ms > 3_600_000.0:
        raise ValueError("latency_ms out of range")

    record = {
        "record_type": _BRAIN_EVENT_TYPE,
        "event_id": f"cbrain_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "brain_id": brain_id,
        "model_id_hash": _hash_text(model_id),
        "model_family": model_family,
        "runtime_id": runtime_id,
        "node_id_hash": _hash_text(node_id),
        "provider_scope": provider_scope,
        "parameter_class": parameter_class,
        "quantization": quantization,
        "domain_scores": {
            domain: float(score) for domain, score in sorted(domain_scores.items())
        },
        "reliability_score": float(reliability_score),
        "reliability_ci95": float(reliability_ci95),
        "error_rate": float(error_rate),
        "latency_ms": float(latency_ms),
        "normalized_cost": float(normalized_cost),
        "baseline_hash": baseline_hash,
        "available": available,
        "raw_model_identifier_persisted": False,
        "raw_node_identifier_persisted": False,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
    }
    record["event_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def project_brain_registry(path: Path) -> dict[str, object]:
    rows = [
        row
        for row in _read_jsonl(path)
        if row.get("record_type") == _BRAIN_EVENT_TYPE
    ]
    brains: dict[str, dict[str, object]] = {}
    for row in rows:
        brain_id = str(row.get("brain_id", ""))
        if brain_id:
            brains[brain_id] = dict(row)
    available = sorted(
        brain_id
        for brain_id, row in brains.items()
        if row.get("available") is True
    )
    payload = {
        "projection_type": "cognitive_brain_registry_v1",
        "event_count": len(rows),
        "brain_count": len(brains),
        "available_brain_ids": available,
        "brains": brains,
        "base_model_interchangeable": True,
        "raw_model_identifiers_persisted": False,
        "next_action": "select_cognitive_brain" if available else "register_brain_phenotype",
    }
    payload["projection_hash"] = _stable_hash(payload)
    return payload


def select_cognitive_brain(
    path: Path,
    *,
    task_domain: str,
    context_sensitivity: str,
    maximum_latency_ms: float,
    cost_pressure: float,
    remote_allowed: bool,
    minimum_acceptable_score: float = 0.55,
) -> dict[str, object]:
    if not task_domain.strip():
        raise ValueError("task_domain must be non-empty")
    if context_sensitivity not in _PRIVACY_LEVELS:
        raise ValueError("context_sensitivity invalid")
    if maximum_latency_ms <= 0.0 or maximum_latency_ms > 3_600_000.0:
        raise ValueError("maximum_latency_ms out of range")
    for label, value in {
        "cost_pressure": cost_pressure,
        "minimum_acceptable_score": minimum_acceptable_score,
    }.items():
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{label} out of range")

    registry = project_brain_registry(path)
    brains_value = registry.get("brains")
    brains = brains_value if isinstance(brains_value, dict) else {}
    candidates: list[dict[str, object]] = []
    exclusions: list[dict[str, str]] = []
    for brain_id, value in sorted(brains.items()):
        if not isinstance(value, dict):
            continue
        reason = _ineligibility_reason(
            value,
            context_sensitivity=context_sensitivity,
            remote_allowed=remote_allowed,
        )
        if reason:
            exclusions.append({"brain_id": brain_id, "reason": reason})
            continue
        domain_scores = value.get("domain_scores")
        score_map = domain_scores if isinstance(domain_scores, dict) else {}
        competence = float(score_map.get(task_domain, score_map.get("general", 0.0)))
        reliability = float(value.get("reliability_score", 0.0))
        latency_ms = float(value.get("latency_ms", maximum_latency_ms * 10.0))
        normalized_cost = float(value.get("normalized_cost", 1.0))
        # Risk-aware selection: discount a brain's measured competence and
        # reliability by the 95% CI half-width of its benchmark, and penalize a
        # measured call-error rate. A high but unstable (wide-CI) or flaky brain
        # loses to a slightly lower but stable one. Both default to 0.0 when
        # unmeasured, so the score is unchanged for legacy phenotypes.
        reliability_ci95 = float(value.get("reliability_ci95", 0.0))
        error_rate = float(value.get("error_rate", 0.0))
        robust_competence = max(0.0, competence - 0.5 * reliability_ci95)
        robust_reliability = max(0.0, reliability - reliability_ci95)
        latency_utility = max(0.0, min(1.0, 1.0 - latency_ms / maximum_latency_ms))
        cost_utility = 1.0 - normalized_cost
        privacy_utility = 1.0 if value.get("provider_scope") in {"local", "private_remote"} else 0.0
        weighted_cost = 0.05 + 0.15 * cost_pressure
        weighted_competence = 0.65 - 0.10 * cost_pressure
        total = (
            weighted_competence * robust_competence
            + 0.20 * robust_reliability
            + 0.10 * latency_utility
            + weighted_cost * cost_utility
            + 0.05 * privacy_utility
            - 0.10 * error_rate
        )
        candidates.append(
            {
                "brain_id": brain_id,
                "score": round(total, 6),
                "domain_competence": competence,
                "robust_competence": round(robust_competence, 6),
                "reliability": reliability,
                "reliability_ci95": reliability_ci95,
                "error_rate": error_rate,
                "latency_utility": round(latency_utility, 6),
                "cost_utility": round(cost_utility, 6),
                "privacy_utility": privacy_utility,
                "provider_scope": value.get("provider_scope"),
                "runtime_id": value.get("runtime_id"),
                "model_family": value.get("model_family"),
                "baseline_hash": value.get("baseline_hash"),
            }
        )

    candidates.sort(key=lambda row: (-float(row["score"]), str(row["brain_id"])))
    selected = candidates[0] if candidates else None
    acceptable = selected is not None and float(selected["score"]) >= minimum_acceptable_score
    blockers = [] if acceptable else [
        "no_eligible_brain" if selected is None else "best_brain_below_acceptance_threshold"
    ]
    payload = {
        "selection_type": "cognitive_brain_selection_v1",
        "status": "ready" if acceptable else "blocked",
        "task_domain": task_domain,
        "context_sensitivity": context_sensitivity,
        "cost_pressure": cost_pressure,
        "maximum_latency_ms": maximum_latency_ms,
        "minimum_acceptable_score": minimum_acceptable_score,
        "selected_brain_id": selected.get("brain_id") if acceptable and selected else None,
        "selected_score": selected.get("score") if acceptable and selected else None,
        "candidates": candidates,
        "exclusions": exclusions,
        "silent_fallback_allowed": False,
        "model_call_performed": False,
        "raw_context_persisted": False,
        "blockers": blockers,
        "next_action": "dispatch_selected_brain" if acceptable else "escalate_or_refuse_task",
    }
    payload["selection_hash"] = _stable_hash(payload)
    return payload


def _ineligibility_reason(
    brain: dict[str, object],
    *,
    context_sensitivity: str,
    remote_allowed: bool,
) -> str | None:
    if brain.get("available") is not True:
        return "brain_not_available"
    scope = brain.get("provider_scope")
    if scope == "metered_remote" and not remote_allowed:
        return "remote_not_authorized"
    if context_sensitivity == "secret" and scope != "local":
        return "secret_context_requires_local_brain"
    if context_sensitivity == "private" and scope == "metered_remote":
        return "private_context_excludes_metered_remote"
    return None


def _read_jsonl(path: Path) -> list[dict[str, object]]:
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
            raise ValueError(f"invalid brain registry JSONL at line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"brain registry record at line {line_number} must be an object")
        rows.append(payload)
    return rows


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
