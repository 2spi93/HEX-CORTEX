"""Scientific Knowledge Router V16: bounded, offline, evidence-gated cross-domain facts.

Inspired by W3C PROV provenance and FAIR reuse principles; not a PROV-O
serializer, FAIR certification, scientific search engine or truth oracle.
No external I/O or execution. The caller's source verifier is a TRUSTED
HOST callback; its True result alone is not independent scientific proof.
Never grant physical/device authority based on this advisory.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import date
from enum import StrEnum
from fractions import Fraction

from pydantic import BaseModel, Field, field_validator, model_validator

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain

# Canonical unit, exact multiplicative factor TO canonical unit.
# No affine offsets, temperatures in Celsius, logarithmic scales or dimensional
# analysis of arbitrary unit expressions.
_UNIT_MAP: dict[str, tuple[str, Fraction]] = {
    "1": ("1", Fraction(1)),
    "m": ("m", Fraction(1)),
    "cm": ("m", Fraction(1, 100)),
    "km": ("m", Fraction(1000)),
    "s": ("s", Fraction(1)),
    "ms": ("s", Fraction(1, 1000)),
    "kg": ("kg", Fraction(1)),
    "g": ("kg", Fraction(1, 1000)),
    "mol": ("mol", Fraction(1)),
    "m/s": ("m/s", Fraction(1)),
    "km/s": ("m/s", Fraction(1000)),
    "N": ("N", Fraction(1)),
    "J": ("J", Fraction(1)),
    "W": ("W", Fraction(1)),
    "g/mol": ("kg/mol", Fraction(1, 1000)),
    "kg/mol": ("kg/mol", Fraction(1)),
}
_MAX_RECORDS = 32
_MAX_RESULT_BITS = 256
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-z][a-z0-9_.:-]{1,95}\Z")


class EvidenceKind(StrEnum):
    EXACT_DEFINITION = "exact_definition"
    MEASUREMENT = "measurement"
    COMPUTED = "computed"
    HYPOTHESIS = "hypothesis"


class EvidenceRecord(BaseModel):
    """A *supplied* source record; metadata is not authenticated by typing."""

    claim_id: str = Field(min_length=2, max_length=96)
    domain: KnowledgeDomain
    value: str = Field(min_length=1, max_length=128)
    unit: str
    absolute_uncertainty: str = Field(min_length=1, max_length=128)
    kind: EvidenceKind
    source_id: str = Field(min_length=2, max_length=96)
    source_uri: str = Field(min_length=12, max_length=512)
    source_version: str = Field(min_length=1, max_length=96)
    source_digest_sha256: str
    source_license: str = Field(min_length=2, max_length=100)
    published_on: date

    @field_validator("claim_id", "source_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("knowledge_identifier_invalid")
        return value

    @field_validator("unit")
    @classmethod
    def validate_known_unit(cls, value: str) -> str:
        if value not in _UNIT_MAP:
            raise ValueError("knowledge_unit_not_supported")
        return value

    @field_validator("source_uri")
    @classmethod
    def validate_provenance_uri(cls, value: str) -> str:
        if not value.startswith("https://") or any(c.isspace() for c in value):
            raise ValueError("knowledge_source_https_required")
        return value

    @field_validator("source_digest_sha256")
    @classmethod
    def validate_hex_sha(cls, value: str) -> str:
        if not _HEX64.fullmatch(value):
            raise ValueError("knowledge_source_digest_invalid")
        return value

    @model_validator(mode="after")
    def check_numeric_envelope(self) -> EvidenceRecord:
        point = _exact_rational(self.value)
        uncertainty = _exact_rational(self.absolute_uncertainty)
        if uncertainty < 0:
            raise ValueError("knowledge_negative_uncertainty")
        if self.kind == EvidenceKind.MEASUREMENT and uncertainty <= 0:
            raise ValueError("knowledge_measurement_uncertainty_required")
        _finite_bound(point * _UNIT_MAP[self.unit][1])
        _finite_bound(uncertainty * _UNIT_MAP[self.unit][1])
        return self


class EvidenceQuery(BaseModel):
    claim_id: str = Field(min_length=2, max_length=96)
    domain: KnowledgeDomain
    result_unit: str

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("knowledge_identifier_invalid")
        return value

    @field_validator("result_unit")
    @classmethod
    def validate_result_unit(cls, value: str) -> str:
        if value not in _UNIT_MAP:
            raise ValueError("knowledge_unit_not_supported")
        return value


def _exact_rational(expression: str) -> Fraction:
    proof = calculate_exact(expression, approved=True)
    if proof.get("status") != "verified_exact_arithmetic":
        raise ValueError("knowledge_rational_expression_invalid")
    return Fraction(int(proof["numerator"]), int(proof["denominator"]))


def _finite_bound(number: Fraction) -> Fraction:
    if (number.numerator.bit_length() > _MAX_RESULT_BITS
            or number.denominator.bit_length() > _MAX_RESULT_BITS):
        raise ValueError("knowledge_numeric_budget_exceeded")
    return number


def _serial_fraction(value: Fraction) -> str:
    return str(value)


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def review_scientific_knowledge(
    query: EvidenceQuery,
    records: list[EvidenceRecord],
    *,
    operator_approved: bool = False,
    verify_source: Callable[[EvidenceRecord], bool] | None = None,
) -> dict[str, object]:
    """Compare approved host-reviewed sources in one normalized unit.

    A source callback must independently check the SOURCE BYTES and its
    digest; a bool from an arbitrary host callback is not external proof.
    Multiple SOURCE IDs are not necessarily independent institutions.
    """
    def receipt(status: str, reason: str, *, matched: int = 0,
                selected: int = 0, interval: tuple[Fraction, Fraction] | None = None,
                sources: list[EvidenceRecord] | None = None) -> dict[str, object]:
        report: dict[str, object] = {
            "receipt_type": "hex_cortex_scientific_knowledge_router_v16",
            "status": status,
            "reason": reason,
            "claim_sha256": _digest({"claim": query.claim_id, "domain": query.domain.value}),
            "domain": query.domain.value,
            "unit": query.result_unit,
            "candidate_record_count": matched,
            "host_checked_source_count": selected,
            "source_manifest_sha256": _digest([
                {"source_id": s.source_id, "revision": s.source_version,
                 "digest": s.source_digest_sha256, "license": s.source_license}
                for s in sorted(sources or [], key=lambda x: x.source_id)
            ]),
            "interval_lower": _serial_fraction(interval[0]) if interval else None,
            "interval_upper": _serial_fraction(interval[1]) if interval else None,
            "truth_certified": False,
            "source_independence_certified": False,
            "untrusted_web_fetched": False,
            "model_used": False,
            "knowledge_persisted": False,
            "tools_executed": False,
            "physical_action_authorized": False,
            "checkout_modified": False,
        }
        report["receipt_sha256"] = _digest(report)
        return report

    if not operator_approved:
        return receipt("blocked", "knowledge_operator_approval_required")
    if not isinstance(records, list) or len(records) > _MAX_RECORDS:
        return receipt("blocked", "knowledge_record_budget_invalid")
    if verify_source is None or not callable(verify_source):
        return receipt("blocked", "trusted_source_verifier_required")
    if any(not isinstance(r, EvidenceRecord) for r in records):
        return receipt("blocked", "knowledge_record_type_invalid")
    matches = [r for r in records if r.claim_id == query.claim_id and r.domain == query.domain]
    if not matches:
        return receipt("blocked", "knowledge_no_matching_records")
    n = len(matches)
    # Reject conflicting declarations from one identifier: never treat
    # duplicated rows, aliases or revisions as independent corroboration.
    if len({r.source_id for r in matches}) != n:
        return receipt("blocked", "knowledge_duplicate_source_id", matched=n)
    wanted_unit = _UNIT_MAP[query.result_unit]
    if any(_UNIT_MAP[r.unit][0] != wanted_unit[0] for r in matches):
        return receipt("blocked", "knowledge_dimension_mismatch", matched=n)
    if any(r.kind == EvidenceKind.HYPOTHESIS for r in matches):
        return receipt("blocked", "knowledge_hypothesis_not_evidence", matched=n)
    for record in matches:
        try:
            checked = verify_source(record) is True
        except Exception:  # noqa: BLE001 - do not expose arbitrary untrusted errors
            checked = False
        if not checked:
            return receipt("blocked", "knowledge_source_not_verified_by_host", matched=n)
    lows: list[Fraction] = []
    highs: list[Fraction] = []
    for record in matches:
        scale = _UNIT_MAP[record.unit][1] / wanted_unit[1]
        value = _finite_bound(_exact_rational(record.value) * scale)
        error = _finite_bound(_exact_rational(record.absolute_uncertainty) * scale)
        lows.append(_finite_bound(value - error))
        highs.append(_finite_bound(value + error))
    lower, upper = max(lows), min(highs)
    if lower > upper:
        return receipt("conflict", "knowledge_source_intervals_disagree",
                       matched=n, selected=n, sources=matches)
    if n < 2:
        return receipt("insufficient", "knowledge_multiple_sources_required",
                       matched=n, selected=n, interval=(lower, upper), sources=matches)
    return receipt(
        "consistent_evidence_not_certified",
        "knowledge_consistent_but_independence_and_truth_unverified",
        matched=n, selected=n, interval=(lower, upper), sources=matches,
    )
