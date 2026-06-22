"""Structured code-plan schema and field-level consensus.

Long-form plans should not be clustered by byte-identical prose. This module
forces a reusable JSON contract, validates repository paths against the bounded
AST context, and selects a weighted medoid from semantically comparable fields.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

FocusArea = Literal[
    "model_call_reduction",
    "consensus_quality",
    "repository_context",
    "phase_separation",
    "patch_safety",
    "testing",
    "security",
    "performance",
    "other",
]


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: FocusArea
    file: str | None = None
    objective: str = Field(min_length=1, max_length=500)
    change: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)


class StructuredCodePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2_000)
    focus_areas: list[FocusArea] = Field(min_length=1, max_length=12)
    candidate_files: list[str] = Field(default_factory=list, max_length=20)
    proposed_changes: list[ProposedChange] = Field(default_factory=list, max_length=20)
    tests: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


def code_plan_json_schema() -> dict[str, object]:
    return StructuredCodePlan.model_json_schema()


def parse_structured_code_plan(
    text: str,
    *,
    allowed_paths: set[str],
) -> dict[str, object]:
    """Validate JSON and remove file references not grounded in repo context."""
    try:
        model = StructuredCodePlan.model_validate_json(text)
    except ValidationError as exc:
        return {
            "status": "invalid",
            "error_type": "structured_code_plan_validation_failed",
            "error_hash": hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
            "plan": None,
            "invalid_paths": [],
            "raw_response_persisted": False,
        }

    payload = model.model_dump(mode="json")
    invalid_paths: set[str] = set()
    valid_files: list[str] = []
    for path in payload["candidate_files"]:
        normalized = _normalize_path(path)
        if normalized in allowed_paths:
            valid_files.append(normalized)
        else:
            invalid_paths.add(normalized)
    payload["candidate_files"] = sorted(set(valid_files))

    grounded_changes: list[dict[str, object]] = []
    referenced = 0
    grounded = 0
    for change in payload["proposed_changes"]:
        row = dict(change)
        path = row.get("file")
        if isinstance(path, str) and path.strip():
            referenced += 1
            normalized = _normalize_path(path)
            if normalized in allowed_paths:
                row["file"] = normalized
                grounded += 1
            else:
                invalid_paths.add(normalized)
                row["file"] = None
        grounded_changes.append(row)
    payload["proposed_changes"] = grounded_changes
    payload["focus_areas"] = sorted(set(str(item) for item in payload["focus_areas"]))
    payload["tests"] = _dedupe_strings(payload["tests"])
    payload["risks"] = _dedupe_strings(payload["risks"])
    payload["unknowns"] = _dedupe_strings(payload["unknowns"])

    total_references = referenced + len(model.candidate_files)
    valid_references = grounded + len(valid_files)
    grounding_ratio = 1.0 if total_references == 0 else valid_references / total_references
    return {
        "status": "valid",
        "plan": payload,
        "invalid_paths": sorted(invalid_paths),
        "grounding_ratio": round(grounding_ratio, 6),
        "raw_response_persisted": False,
    }


def aggregate_structured_code_plans(
    samples: list[str],
    *,
    allowed_paths: set[str],
    sample_weights: list[float] | None = None,
    agreement_threshold: float = 0.55,
) -> dict[str, object]:
    """Select a grounded weighted medoid instead of exact-text voting."""
    if not samples:
        raise ValueError("samples must not be empty")
    if not 0.0 < agreement_threshold <= 1.0:
        raise ValueError("agreement_threshold out of range")
    weights = _weights(sample_weights, len(samples))
    parsed = [parse_structured_code_plan(item, allowed_paths=allowed_paths) for item in samples]
    valid_indices = [index for index, item in enumerate(parsed) if item["status"] == "valid"]
    if not valid_indices:
        return _empty_consensus(len(samples), parsed)

    similarities: dict[tuple[int, int], float] = {}
    for left in valid_indices:
        for right in valid_indices:
            if left == right:
                similarities[(left, right)] = 1.0
            elif (right, left) in similarities:
                similarities[(left, right)] = similarities[(right, left)]
            else:
                similarities[(left, right)] = _plan_similarity(parsed[left], parsed[right])

    medoid = max(
        valid_indices,
        key=lambda index: (
            _weighted_average(
                [similarities[(index, other)] for other in valid_indices],
                [weights[other] for other in valid_indices],
            ),
            float(parsed[index].get("grounding_ratio", 0.0)),
            -index,
        ),
    )
    support_indices = [
        index
        for index in valid_indices
        if similarities[(medoid, index)] >= agreement_threshold
    ]
    total_valid_weight = sum(weights[index] for index in valid_indices)
    support_weight = sum(weights[index] for index in support_indices)
    agreement_ratio = support_weight / total_valid_weight if total_valid_weight else 0.0
    effective_n = _effective_sample_size([weights[index] for index in valid_indices])
    confidence = _wilson_lower(agreement_ratio, effective_n)
    enough_support = len(support_indices) >= 2 and agreement_ratio > 0.5
    winner = parsed[medoid]["plan"]
    invalid_paths = sorted(
        {
            str(path)
            for item in parsed
            for path in item.get("invalid_paths", [])
        }
    )
    status = "consensus" if enough_support else "no_consensus"
    decision = "structured_consensus_reached" if enough_support else "structured_consensus_weak"
    signature = _plan_signature(parsed[medoid])
    event = {
        "record_type": "cortex_structured_code_plan_consensus_v1",
        "event_id": f"structplan_{uuid4().hex}",
        "status": status,
        "decision": decision,
        "mode": "structured_code_plan",
        "sample_count": len(samples),
        "valid_sample_count": len(valid_indices),
        "support_count": len(support_indices),
        "agreement_ratio": round(agreement_ratio, 6),
        "agreement_threshold": agreement_threshold,
        "effective_sample_count": round(effective_n, 6),
        "confidence_wilson_lower": round(confidence, 6),
        "winner_count": len(support_indices),
        "winner_cluster_hash": _stable_hash(_serializable_signature(signature)),
        "consensus_answer": json.dumps(winner, sort_keys=True, separators=(",", ":")),
        "consensus_plan": winner,
        "grounding_ratio": parsed[medoid].get("grounding_ratio", 0.0),
        "invalid_paths": invalid_paths,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "next_action": "review_grounded_plan" if enough_support else "resample_or_review",
    }
    event["event_hash"] = _stable_hash(
        {key: value for key, value in event.items() if key not in {"consensus_answer", "consensus_plan"}}
    )
    return event


def _plan_similarity(left: dict[str, object], right: dict[str, object]) -> float:
    left_signature = _plan_signature(left)
    right_signature = _plan_signature(right)
    areas = _jaccard(left_signature["areas"], right_signature["areas"])
    files = _jaccard(left_signature["files"], right_signature["files"])
    changes = _jaccard(left_signature["changes"], right_signature["changes"])
    grounding = min(
        float(left.get("grounding_ratio", 0.0)),
        float(right.get("grounding_ratio", 0.0)),
    )
    return (0.45 * areas + 0.35 * files + 0.20 * changes) * (0.5 + 0.5 * grounding)


def _plan_signature(parsed: dict[str, object]) -> dict[str, set[str]]:
    plan_value = parsed.get("plan")
    plan = plan_value if isinstance(plan_value, dict) else {}
    areas = {str(item) for item in plan.get("focus_areas", [])}
    files = {str(item) for item in plan.get("candidate_files", [])}
    changes = {
        f"{item.get('area')}:{item.get('file') or 'unknown'}"
        for item in plan.get("proposed_changes", [])
        if isinstance(item, dict)
    }
    return {"areas": areas, "files": files, "changes": changes}


def _serializable_signature(signature: dict[str, set[str]]) -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in signature.items()}


def _empty_consensus(sample_count: int, parsed: list[dict[str, object]]) -> dict[str, object]:
    event = {
        "record_type": "cortex_structured_code_plan_consensus_v1",
        "event_id": f"structplan_{uuid4().hex}",
        "status": "no_consensus",
        "decision": "no_valid_structured_sample",
        "mode": "structured_code_plan",
        "sample_count": sample_count,
        "valid_sample_count": 0,
        "support_count": 0,
        "agreement_ratio": 0.0,
        "agreement_threshold": 0.55,
        "effective_sample_count": 0.0,
        "confidence_wilson_lower": 0.0,
        "winner_count": 0,
        "winner_cluster_hash": None,
        "consensus_answer": "",
        "consensus_plan": None,
        "grounding_ratio": 0.0,
        "invalid_paths": sorted(
            {str(path) for item in parsed for path in item.get("invalid_paths", [])}
        ),
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "next_action": "repair_structured_output_contract",
    }
    event["event_hash"] = _stable_hash(event)
    return event


def _normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("./")


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left.union(right)
    return len(left.intersection(right)) / len(union) if union else 0.0


def _weights(values: list[float] | None, count: int) -> list[float]:
    if values is None:
        return [1.0] * count
    if len(values) != count:
        raise ValueError("sample_weights length mismatch")
    weights = [float(value) for value in values]
    if any(not math.isfinite(value) or value <= 0 for value in weights):
        raise ValueError("sample_weights must be finite and positive")
    return weights


def _weighted_average(values: list[float], weights: list[float]) -> float:
    total = sum(weights)
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / total


def _effective_sample_size(weights: list[float]) -> float:
    total = sum(weights)
    squares = sum(weight * weight for weight in weights)
    return (total * total / squares) if squares else 0.0


def _wilson_lower(proportion: float, sample_size: float, z: float = 1.96) -> float:
    if sample_size <= 0:
        return 0.0
    denominator = 1.0 + z * z / sample_size
    centre = proportion + z * z / (2.0 * sample_size)
    spread = z * math.sqrt(
        (proportion * (1.0 - proportion) + z * z / (4.0 * sample_size)) / sample_size
    )
    return max(0.0, (centre - spread) / denominator)


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "StructuredCodePlan",
    "aggregate_structured_code_plans",
    "code_plan_json_schema",
    "parse_structured_code_plan",
]
