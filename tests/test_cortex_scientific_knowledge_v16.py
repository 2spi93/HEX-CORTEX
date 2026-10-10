"""Scientific Knowledge Router V16: provenance, SI reconciliation and contradictions."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from fractions import Fraction

import pytest
from pydantic import ValidationError

from hex_cortex.core.cortex_chemistry_cell_v15 import run_chemistry
from hex_cortex.core.cortex_exact_math_v13 import calculate_exact
from hex_cortex.core.cortex_physics_cell_v14 import calculate_physics
from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceKind,
    EvidenceQuery,
    EvidenceRecord,
    review_scientific_knowledge,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain


def _record(
    source_id: str = "nist.001",
    *,
    value: str = "100",
    unit: str = "m/s",
    absolute_uncertainty: str = "1",
    claim_id: str = "reference_speed",
    domain: KnowledgeDomain = KnowledgeDomain.PHYSICS,
    kind: EvidenceKind = EvidenceKind.MEASUREMENT,
) -> EvidenceRecord:
    return EvidenceRecord(
        claim_id=claim_id,
        domain=domain,
        value=value,
        unit=unit,
        absolute_uncertainty=absolute_uncertainty,
        kind=kind,
        source_id=source_id,
        source_uri="https://example.org/synthetic-fixture/" + source_id,
        source_version="fixture.v1",
        source_digest_sha256=hashlib.sha256(source_id.encode()).hexdigest(),
        source_license="synthetic-test-only",
        published_on=date(2026, 10, 10),
    )


def _query(
    claim_id: str = "reference_speed",
    domain: KnowledgeDomain = KnowledgeDomain.PHYSICS,
    result_unit: str = "m/s",
) -> EvidenceQuery:
    return EvidenceQuery(
        claim_id=claim_id, domain=domain, result_unit=result_unit,
    )


def _review(
    records: list[EvidenceRecord],
    *,
    query: EvidenceQuery | None = None,
    verified=True,
    approval=True,
):
    return review_scientific_knowledge(
        query or _query(), records, operator_approved=approval,
        verify_source=(lambda _: verified),
    )


def test_consistent_two_sources_canonicalize_units_and_uncertainty():
    a = _record("source.alpha", value="100", unit="m/s", absolute_uncertainty="2")
    b = _record("source.beta", value="1/10", unit="km/s", absolute_uncertainty="1/1000")
    output = _review([a, b])
    assert output["status"] == "consistent_evidence_not_certified"
    assert output["unit"] == "m/s"
    assert output["interval_lower"] == "99"
    assert output["interval_upper"] == "101"
    assert output["host_checked_source_count"] == 2
    assert output["truth_certified"] is False
    assert output["source_independence_certified"] is False
    assert output["untrusted_web_fetched"] is False
    assert output["physical_action_authorized"] is False


def test_conflicting_scientific_references_are_not_averaged_or_voted_on():
    a = _record("source.alpha", value="100", absolute_uncertainty="1")
    b = _record("source.beta", value="110", absolute_uncertainty="1")
    output = _review([a, b])
    assert output["status"] == "conflict"
    assert output["interval_lower"] is None
    assert output["reason"] == "knowledge_source_intervals_disagree"
    assert output["truth_certified"] is False


def test_insufficient_single_reference_cannot_establish_consensus():
    out = _review([_record()])
    assert out["status"] == "insufficient"
    assert out["interval_lower"] == "99"
    assert out["interval_upper"] == "101"
    assert out["reason"] == "knowledge_multiple_sources_required"


def test_duplicates_do_not_inflate_independent_sources():
    a = _record("source.alpha")
    out = _review([a, a])
    assert out["status"] == "blocked"
    assert out["reason"] == "knowledge_duplicate_source_id"


def test_declared_source_digest_without_trusted_verifier_is_not_evidence():
    evidence = [_record("source.alpha"), _record("source.beta")]
    result = review_scientific_knowledge(
        _query(), evidence, operator_approved=True,
    )
    assert result["reason"] == "trusted_source_verifier_required"
    assert result["host_checked_source_count"] == 0


def test_operator_denial_prevents_any_verifier_callback():
    hits = []
    def verifier(record):
        hits.append(record)
        return True
    report = review_scientific_knowledge(
        _query(), [_record()], operator_approved=False, verify_source=verifier,
    )
    assert report["status"] == "blocked"
    assert report["reason"] == "knowledge_operator_approval_required"
    assert hits == []


def test_source_verifier_failure_suppresses_secret_exception_and_result():
    def malicious(record):
        raise RuntimeError("sensitive credential example")
    out = review_scientific_knowledge(
        _query(), [_record()], operator_approved=True, verify_source=malicious,
    )
    assert out["status"] == "blocked"
    assert out["reason"] == "knowledge_source_not_verified_by_host"
    assert "sensitive credential" not in json.dumps(out)


def test_measurement_cannot_claim_zero_uncertainty():
    with pytest.raises(ValidationError, match="knowledge_measurement_uncertainty_required"):
        _record(kind=EvidenceKind.MEASUREMENT, absolute_uncertainty="0")


@pytest.mark.parametrize(("changed", "match"), [
    ({"source_uri": "file:///tmp/private.txt"}, "knowledge_source_https_required"),
    ({"source_uri": "http://example.org/data"}, "knowledge_source_https_required"),
    ({"source_digest_sha256": "not-a-hash"}, "knowledge_source_digest_invalid"),
    ({"source_license": ""}, "String should have at least"),
    ({"unit": "kelvin_magic"}, "knowledge_unit_not_supported"),
    ({"value": "import('os')"}, "knowledge_rational_expression_invalid"),
    ({"absolute_uncertainty": "-1"}, "knowledge_negative_uncertainty"),
    ({"source_id": "../secret"}, "knowledge_identifier_invalid"),
])
def test_malformed_unlicensed_or_untrusted_metadata_is_rejected(changed, match):
    original = _record().model_dump()
    original.update(changed)
    with pytest.raises(ValidationError, match=match):
        EvidenceRecord.model_validate(original)


def test_hypothesis_is_not_counted_as_observed_evidence():
    guess = _record("source.a", kind=EvidenceKind.HYPOTHESIS)
    result = _review([guess, _record("source.b")])
    assert result["status"] == "blocked"
    assert result["reason"] == "knowledge_hypothesis_not_evidence"


def test_incompatible_units_fail_closed_instead_of_comparing_numbers():
    a = _record("source.a", value="100", unit="m/s")
    b = _record("source.b", value="100", unit="kg",
                absolute_uncertainty="1")
    report = _review([a, b])
    assert report["status"] == "blocked"
    assert report["reason"] == "knowledge_dimension_mismatch"


def test_unmatched_subject_is_not_filled_by_other_scientific_claims():
    report = _review([_record(claim_id="other_fact")])
    assert report["reason"] == "knowledge_no_matching_records"


def test_source_check_cannot_be_replaced_with_str_truthy_response():
    out = review_scientific_knowledge(
        _query(), [_record()], operator_approved=True,
        verify_source=lambda _: "true",
    )
    assert out["reason"] == "knowledge_source_not_verified_by_host"


def test_exact_definition_can_have_zero_uncertainty_but_is_not_truth_certificate():
    a = _record("source.a", kind=EvidenceKind.EXACT_DEFINITION,
                absolute_uncertainty="0")
    b = _record("source.b", kind=EvidenceKind.EXACT_DEFINITION,
                absolute_uncertainty="0")
    report = _review([a, b])
    assert report["status"] == "consistent_evidence_not_certified"
    assert report["interval_lower"] == "100"
    assert report["interval_upper"] == "100"
    assert report["truth_certified"] is False


def test_reference_provenance_metadata_not_exposed_in_receipt():
    src = _record(
        "private-secret-source", value="100",
    ).model_copy(update={
        "source_uri": "https://example.org/sensitive/token-A1B2C3",
        "source_license": "secret-license-ABCD"
    })
    report = _review([src])
    serial = json.dumps(report)
    assert "token-A1B2C3" not in serial
    assert "private-secret" not in serial
    assert "secret-license" not in serial
    assert len(report["source_manifest_sha256"]) == 64


def test_order_invariant_provenance_manifest_for_same_records():
    a, b = _record("source.a"), _record("source.b")
    first = _review([a, b])
    second = _review([b, a])
    assert first["source_manifest_sha256"] == second["source_manifest_sha256"]
    assert first["receipt_sha256"] == second["receipt_sha256"]


def test_source_conflict_regression_grid_289_pairs():
    # Two exact positive/negative error intervals. Test all 17^2 pairs
    # to catch conflict regressions and improper averages.
    for offset_a in range(-8, 9):
        for offset_b in range(-8, 9):
            left = _record("source.a", value=str(100 + offset_a),
                           absolute_uncertainty="1")
            right = _record("source.b", value=str(100 + offset_b),
                            absolute_uncertainty="1")
            report = _review([left, right])
            if abs(offset_a - offset_b) <= 2:
                assert report["status"] == "consistent_evidence_not_certified"
            else:
                assert report["status"] == "conflict"
    assert 17 * 17 == 289


def test_router_reconciles_real_exact_math_output():
    result = calculate_exact("1 / 3 + 1 / 6", approved=True)
    assert result["status"] == "verified_exact_arithmetic"
    a = _record("math.a", value=str(Fraction(result["numerator"], result["denominator"])),
                unit="1", absolute_uncertainty="0", claim_id="rational_half",
                domain=KnowledgeDomain.MATHEMATICS, kind=EvidenceKind.COMPUTED)
    b = _record("math.b", value="2/4", unit="1", absolute_uncertainty="0",
                claim_id="rational_half", domain=KnowledgeDomain.MATHEMATICS,
                kind=EvidenceKind.COMPUTED)
    report = _review([a, b], query=_query("rational_half", KnowledgeDomain.MATHEMATICS, "1"))
    assert report["status"] == "consistent_evidence_not_certified"
    assert report["interval_lower"] == report["interval_upper"] == "1/2"


def test_router_reconciles_real_physics_output():
    result = calculate_physics("speed", {
        "distance": {"value": "100", "unit": "m"},
        "duration": {"value": "1", "unit": "s"},
    }, approved=True)
    assert result["status"] == "verified_classical_formula"
    a = _record("physics.a", value=str(result["numerator"]), unit="m/s",
                absolute_uncertainty="0", kind=EvidenceKind.COMPUTED)
    b = _record("physics.b", value="1/10", unit="km/s",
                absolute_uncertainty="0", kind=EvidenceKind.COMPUTED)
    report = _review([a, b])
    assert report["status"] == "consistent_evidence_not_certified"


def test_router_reconciles_chemistry_molar_mass_units():
    chemistry = run_chemistry(["H2", "O2"], ["H2O"], approved=True)
    assert chemistry["status"] == "verified_idealized_stoichiometry"
    mass = chemistry["molar_mass_g_per_mol_rounded_iupac"]["H2O"]
    a = _record("chem.a", value=mass, unit="g/mol", absolute_uncertainty="0",
                kind=EvidenceKind.COMPUTED, claim_id="water_molar_mass",
                domain=KnowledgeDomain.CHEMISTRY)
    b = _record("chem.b", value="18015/1000000", unit="kg/mol",
                absolute_uncertainty="0", kind=EvidenceKind.COMPUTED,
                claim_id="water_molar_mass", domain=KnowledgeDomain.CHEMISTRY)
    report = _review(
        [a, b],
        query=_query("water_molar_mass", KnowledgeDomain.CHEMISTRY, "g/mol"),
    )
    assert report["status"] == "consistent_evidence_not_certified"
    assert report["interval_lower"] == report["interval_upper"] == "3603/200"


def test_bounded_number_of_sources_not_arbitrary_vector():
    many = [_record(f"source.{n}") for n in range(33)]
    report = _review(many)
    assert report["reason"] == "knowledge_record_budget_invalid"
    assert report["host_checked_source_count"] == 0
