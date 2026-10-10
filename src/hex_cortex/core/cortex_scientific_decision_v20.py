"""V20: conservative scientific interval decisions, never actuator authority.

This uses the *envelope* (hull) of all independently host-checked source
intervals, NOT their narrower intersection. Only bounded exact rationals
are compared; no synthetic confidence percentages, probabilities or model.
Source agreement and a governance pin do not authenticate publishers.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from enum import StrEnum
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceQuery,
    EvidenceRecord,
    _exact_rational,
    _finite_bound,
    _UNIT_MAP,
    review_scientific_knowledge,
)


class DecisionRelation(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"


class ScientificDecisionSpec(BaseModel):
    """Read-only threshold policy in the query's requested physical unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    query: EvidenceQuery
    relation: DecisionRelation
    threshold: str = Field(min_length=1, max_length=128)
    guard_band: str = Field(default="0", min_length=1, max_length=128)
    maximum_evidence_span: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def check_rational_policy(self) -> ScientificDecisionSpec:
        _finite_bound(_exact_rational(self.threshold))
        if _exact_rational(self.guard_band) < 0:
            raise ValueError("scientific_decision_negative_guard_band")
        _finite_bound(_exact_rational(self.guard_band))
        if self.maximum_evidence_span is not None:
            if _exact_rational(self.maximum_evidence_span) < 0:
                raise ValueError("scientific_decision_negative_maximum_span")
            _finite_bound(_exact_rational(self.maximum_evidence_span))
        return self


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def evaluate_scientific_decision(
    spec: ScientificDecisionSpec,
    records: list[EvidenceRecord],
    *,
    operator_approved: bool = False,
    verify_source: Callable[[EvidenceRecord], bool] | None = None,
) -> dict[str, object]:
    """Return one provisional interpretation after all provenance gates.

    The decision is *not* a permission to use a real actuator or to act
    autonomously. For credible evidence, review all original uncertainty
    intervals. Their hull bounds are conservative, while the V16 overlap
    intersection is used only to check if sources are compatible.
    """
    def result(state: str, reason: str, *, lower: Fraction | None = None,
               upper: Fraction | None = None, evidence_hash: str | None = None,
               evidence_status: str = "not_checked") -> dict[str, object]:
        value = {
            "report_type": "hex_cortex_scientific_interval_decision_v20",
            "status": state,
            "reason": reason,
            "claim_sha256": _digest({
                "domain": spec.query.domain.value, "claim": spec.query.claim_id,
            }),
            "unit": spec.query.result_unit,
            "relation": spec.relation.value,
            "policy_sha256": _digest(spec.model_dump(mode="json")),
            "evidence_receipt_sha256": evidence_hash,
            "evidence_status": evidence_status,
            "conservative_lower": str(lower) if lower is not None else None,
            "conservative_upper": str(upper) if upper is not None else None,
            "guard_band_in_unit": spec.guard_band,
            "maximum_span_policy_applied": spec.maximum_evidence_span is not None,
            "scientific_truth_certified": False,
            "source_independence_certified": False,
            "calibrated_confidence_available": False,
            "confidence_probability": None,
            "external_execution_authorized": False,
            "physical_action_authorized": False,
            "model_used": False,
            "checkout_modified": False,
        }
        value["receipt_sha256"] = _digest(value)
        return value

    if not operator_approved:
        return result("blocked", "decision_operator_approval_required")
    if not isinstance(records, list):
        return result("blocked", "decision_records_invalid")
    reviewed = review_scientific_knowledge(
        spec.query, records, operator_approved=True, verify_source=verify_source,
    )
    evidence_status = str(reviewed["status"])
    if evidence_status != "consistent_evidence_not_certified":
        return result(
            "blocked", "decision_scientific_evidence_" + evidence_status,
            evidence_hash=str(reviewed["receipt_sha256"]),
            evidence_status=evidence_status,
        )
    matching = [
        row for row in records
        if row.claim_id == spec.query.claim_id and row.domain == spec.query.domain
    ]
    requested_unit = _UNIT_MAP[spec.query.result_unit]
    lower_bounds: list[Fraction] = []
    upper_bounds: list[Fraction] = []
    for row in matching:
        factor = _UNIT_MAP[row.unit][1] / requested_unit[1]
        center = _finite_bound(_exact_rational(row.value) * factor)
        uncertainty = _finite_bound(_exact_rational(row.absolute_uncertainty) * factor)
        lower_bounds.append(_finite_bound(center - uncertainty))
        upper_bounds.append(_finite_bound(center + uncertainty))
    lower = min(lower_bounds)
    upper = max(upper_bounds)
    threshold = _finite_bound(_exact_rational(spec.threshold))
    guard = _finite_bound(_exact_rational(spec.guard_band))
    if spec.maximum_evidence_span is not None:
        maximum_span = _finite_bound(_exact_rational(spec.maximum_evidence_span))
        if _finite_bound(upper - lower) > maximum_span:
            return result(
                "indeterminate", "decision_evidence_span_exceeds_policy",
                lower=lower, upper=upper, evidence_hash=str(reviewed["receipt_sha256"]),
                evidence_status=evidence_status,
            )

    if spec.relation == DecisionRelation.AT_LEAST:
        if lower >= _finite_bound(threshold + guard):
            state, reason = "provisionally_supported", "entire_interval_above_required_minimum"
        elif upper < _finite_bound(threshold - guard):
            state, reason = "provisionally_refuted", "entire_interval_below_required_minimum"
        else:
            state, reason = "indeterminate", "decision_threshold_overlaps_uncertainty"
    else:
        if upper <= _finite_bound(threshold - guard):
            state, reason = "provisionally_supported", "entire_interval_below_allowed_maximum"
        elif lower > _finite_bound(threshold + guard):
            state, reason = "provisionally_refuted", "entire_interval_above_allowed_maximum"
        else:
            state, reason = "indeterminate", "decision_threshold_overlaps_uncertainty"
    return result(
        state, reason,
        lower=lower, upper=upper, evidence_hash=str(reviewed["receipt_sha256"]),
        evidence_status=evidence_status,
    )
