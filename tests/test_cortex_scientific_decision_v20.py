"""V20 confidence honesty:  conservative intervals, abstention and safe gates."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from hex_cortex.core.cortex_scientific_corpus_v19 import (
    evaluate_corpus_record,
)
from hex_cortex.core.cortex_scientific_decision_v20 import (
    ScientificDecisionSpec,
    evaluate_scientific_decision,
)
from hex_cortex.core.cortex_scientific_decision_circuit_v20 import (
    decision_task,
    run_scientific_decision_circuit,
)
from hex_cortex.core.cortex_scientific_decision_cli_v20 import main
from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceKind, EvidenceQuery, EvidenceRecord,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain

_PIN = "8eadc291e08d7292c07519c955fa4e52611577dc57f25a16f962c2c42c6a44c5"


def _root() -> Path:
    return Path(__file__).resolve().parents[1] / "examples"


def _records() -> list[EvidenceRecord]:
    return load_local_scientific_manifest(
        _root() / "scientific_v17" / "manifest.json", approved=True,
    )


def _spec(
    threshold: str = "100",
    *,
    relation: str = "at_least",
    unit: str = "m/s",
    guard: str = "0",
    max_span: str | None = None,
) -> ScientificDecisionSpec:
    return ScientificDecisionSpec(
        query=EvidenceQuery(
            claim_id="demo_velocity", domain=KnowledgeDomain.PHYSICS,
            result_unit=unit,
        ),
        relation=relation,
        threshold=threshold,
        guard_band=guard,
        maximum_evidence_span=max_span,
    )


def _verified(record: EvidenceRecord) -> bool:
    return LocalScientificEvidenceVerifier(
        _root() / "scientific_v17", operator_approved=True,
    ).verify_source(record)


@pytest.mark.parametrize(("threshold", "relation", "expected"), [
    ("95", "at_least", "provisionally_supported"),
    ("105", "at_least", "provisionally_refuted"),
    ("100", "at_least", "indeterminate"),
    ("105", "at_most", "provisionally_supported"),
    ("95", "at_most", "provisionally_refuted"),
    ("100", "at_most", "indeterminate"),
    ("98", "at_least", "provisionally_supported"),
    ("102", "at_most", "provisionally_supported"),
])
def test_conservative_hull_threshold_policy(threshold, relation, expected):
    result = evaluate_scientific_decision(
        _spec(threshold, relation=relation), _records(),
        operator_approved=True, verify_source=_verified,
    )
    assert result["status"] == expected
    assert result["conservative_lower"] == "98"
    assert result["conservative_upper"] == "102"
    assert result["confidence_probability"] is None
    assert result["calibrated_confidence_available"] is False
    assert result["scientific_truth_certified"] is False
    assert result["physical_action_authorized"] is False


def test_safety_hull_not_overoptimistic_intersection():
    # V16 consensus intersection is 99..101; V20 decision must use
    # 98..102 instead, so requiring >= 99 remains INDETERMINATE.
    out = evaluate_scientific_decision(
        _spec("99"), _records(), operator_approved=True,
        verify_source=_verified,
    )
    assert out["status"] == "indeterminate"
    assert out["reason"] == "decision_threshold_overlaps_uncertainty"


def test_exact_unit_conversion_at_threshold_in_kilometers_per_second():
    result = evaluate_scientific_decision(
        _spec("1/10", unit="km/s"), _records(), operator_approved=True,
        verify_source=_verified,
    )
    assert result["status"] == "indeterminate"
    assert result["conservative_lower"] == "49/500"
    assert result["conservative_upper"] == "51/500"


def test_guard_band_and_maximum_interval_span_abstain():
    guarded = evaluate_scientific_decision(
        _spec("97", guard="2"), _records(), operator_approved=True,
        verify_source=_verified,
    )
    assert guarded["status"] == "indeterminate"
    assert guarded["reason"] == "decision_threshold_overlaps_uncertainty"

    conservative = evaluate_scientific_decision(
        _spec("80", max_span="3"), _records(), operator_approved=True,
        verify_source=_verified,
    )
    assert conservative["status"] == "indeterminate"
    assert conservative["reason"] == "decision_evidence_span_exceeds_policy"


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("threshold", "1.5", "knowledge_rational_expression_invalid"),
    ("guard_band", "-1", "scientific_decision_negative_guard_band"),
    ("guard_band", "__import__('os')", "knowledge_rational_expression_invalid"),
    ("maximum_evidence_span", "-1", "scientific_decision_negative_maximum_span"),
    ("relation", "execute", "Input should be"),
    ("spare_field", "bad", "Extra inputs are not permitted"),
])
def test_invalid_policy_fails_schema_validation(field, value, reason):
    options = {
        "query": EvidenceQuery(
            claim_id="demo_velocity", domain=KnowledgeDomain.PHYSICS,
            result_unit="m/s",
        ),
        "relation": "at_least", "threshold": "100",
    }
    options[field] = value
    with pytest.raises(ValidationError, match=reason):
        ScientificDecisionSpec.model_validate(options)


def test_operator_denial_invokes_no_source_verifier():
    calls = []
    report = evaluate_scientific_decision(
        _spec(), _records(), operator_approved=False,
        verify_source=lambda r: calls.append(r),
    )
    assert report["status"] == "blocked"
    assert calls == []


def test_single_source_and_conflicts_never_become_provisional_decisions():
    records = _records()
    out = evaluate_scientific_decision(
        _spec(), records[:1], operator_approved=True, verify_source=_verified,
    )
    assert out["status"] == "blocked"
    assert out["evidence_status"] == "insufficient"

    wrong = records[1].model_copy(update={"value": "200"})
    out = evaluate_scientific_decision(
        _spec(), [records[0], wrong], operator_approved=True,
        verify_source=lambda _: True,  # synthetic-only fixture
    )
    assert out["status"] == "blocked"
    assert out["evidence_status"] == "conflict"
    assert out["external_execution_authorized"] is False


def test_source_or_governance_tamper_prevents_decision():
    records = _records()
    out = evaluate_scientific_decision(
        _spec("0"), records, operator_approved=True,
        verify_source=lambda _: False,
    )
    assert out["status"] == "blocked"
    assert out["reason"] == "decision_scientific_evidence_blocked"


def test_decision_receipts_are_deterministic_without_source_url_leak():
    out1 = evaluate_scientific_decision(
        _spec("100"), _records(), operator_approved=True,
        verify_source=_verified,
    )
    out2 = evaluate_scientific_decision(
        _spec("100"), list(reversed(_records())), operator_approved=True,
        verify_source=_verified,
    )
    assert out1 == out2
    assert "example.org" not in json.dumps(out1)
    assert "synthetic-example" not in json.dumps(out1)


def test_cross_threshold_grid_625_uncertainty_scenarios():
    # All 25x25 cases are consistent (two identical central values,
    # different uncertainty radii). Derived conservative hull must
    # never turn an overlapping threshold into a 'pass'.
    count = 0
    for offset in range(-12, 13):
        for radius in range(1, 26):
            central = str(100 + offset)
            a = EvidenceRecord(
                claim_id="demo_velocity", domain=KnowledgeDomain.PHYSICS,
                value=central, unit="m/s",
                absolute_uncertainty=str(radius), kind=EvidenceKind.MEASUREMENT,
                source_id="source.a", source_uri="https://example.org/synthetic/a",
                source_version="test.v1",
                source_digest_sha256=hashlib.sha256(b"a").hexdigest(),
                source_license="synthetic-only", published_on=date(2026, 10, 10),
            )
            b = a.model_copy(update={
                "source_id": "source.b",
                "source_uri": "https://example.org/synthetic/b",
                "source_digest_sha256": hashlib.sha256(b"b").hexdigest(),
                "absolute_uncertainty": "1",
            })
            report = evaluate_scientific_decision(
                _spec("100"), [a, b],
                operator_approved=True,
                verify_source=lambda _: True,  # synthetic source-only fixture
            )
            assert report["conservative_lower"] == str(100 + offset - radius)
            assert report["conservative_upper"] == str(100 + offset + radius)
            expected = (
                "provisionally_supported" if offset >= radius else
                "provisionally_refuted" if offset + radius < 0 else
                "indeterminate"
            )
            assert report["status"] == expected
            assert report["physical_action_authorized"] is False
            count += 1
    assert count == 625


def test_cognitive_circuit_separates_source_verification_from_provisional_answer():
    spec = _spec("100")
    report, circuit = run_scientific_decision_circuit(
        decision_task(spec, task_id="threshold-mid"),
        spec=spec, records=_records(), verify_source=_verified,
        approved=True,
    )
    assert report["status"] == "indeterminate"
    assert report["cognitive_evidence_status"] == "verified"
    assert report["verified_cell_count"] == 1
    assert report["workspace_confidence"] == 0.0
    assert report["calibrated_confidence_available"] is False
    assert report["scientific_truth_certified"] is False
    assert circuit.spine.verify_integrity().ok

    spec_supported = _spec("95")
    positive, spine = run_scientific_decision_circuit(
        decision_task(spec_supported, task_id="threshold-low"),
        spec=spec_supported, records=_records(), verify_source=_verified,
        approved=True,
    )
    assert positive["status"] == "provisionally_supported"
    assert positive["cognitive_evidence_status"] == "verified"
    assert positive["physical_action_authorized"] is False
    assert spine.spine.verify_integrity().ok


def test_no_approval_blocks_cognitive_source_reads():
    spec = _spec("95")
    calls = []
    report, circuit = run_scientific_decision_circuit(
        decision_task(spec, task_id="deny"),
        spec=spec, records=_records(),
        verify_source=lambda row: calls.append(row) or True,
        approved=False,
    )
    assert report["status"] == "blocked"
    assert calls == []
    assert circuit.spine.events == []


def test_source_modification_between_first_and_critic_blocks_decision(tmp_path: Path):
    root = _root() / "scientific_v17"
    sources = tmp_path / "sources"
    sources.mkdir()
    for name in ("example.alpha.json", "example.beta.json"):
        (sources / name).write_bytes((root / name).read_bytes())
    verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    seen = []
    def mutate_source(record):
        passed = verifier.verify_source(record)
        seen.append(record.source_id)
        if len(seen) == 2:
            (sources / "example.beta.json").write_bytes(b"changed in second pass")
        return passed
    spec = _spec("95")
    report, circuit = run_scientific_decision_circuit(
        decision_task(spec, task_id="source-mid-race"),
        spec=spec, records=_records(),
        verify_source=mutate_source, approved=True,
    )
    assert report["status"] == "blocked"
    assert report["cognitive_evidence_status"] == "blocked"
    assert report["verified_cell_count"] == 0
    assert len(seen) >= 3
    assert circuit.spine.verify_integrity().ok


def test_external_pin_enforced_by_decision_critics(tmp_path: Path):
    original = _root()
    records = _records()
    src = LocalScientificEvidenceVerifier(
        original / "scientific_v17", operator_approved=True,
    )
    ledger = original / "scientific_v19" / "ledger.json"
    spec = _spec("95")
    report, circuit = run_scientific_decision_circuit(
        decision_task(spec, task_id="pin-confirmed"),
        spec=spec, records=records,
        verify_source=lambda record: evaluate_corpus_record(
            record, ledger_path=ledger, expected_head=_PIN,
            base_verifier=src.verify_source, approved=True,
        ), approved=True,
    )
    assert report["status"] == "provisionally_supported"
    assert circuit.spine.verify_integrity().ok

    denied, _ = run_scientific_decision_circuit(
        decision_task(spec, task_id="pin-denied"),
        spec=spec, records=records,
        verify_source=lambda record: evaluate_corpus_record(
            record, ledger_path=ledger, expected_head="f" * 64,
            base_verifier=src.verify_source, approved=True,
        ), approved=True,
    )
    assert denied["status"] == "blocked"


def _args(relation="at_least", threshold="95", approved=True):
    root = _root()
    result = [
        "--ledger", str(root / "scientific_v19" / "ledger.json"),
        "--pin", _PIN,
        "--manifest", str(root / "scientific_v17" / "manifest.json"),
        "--sources-dir", str(root / "scientific_v17"),
        "--claim-id", "demo_velocity", "--domain", "physics",
        "--unit", "m/s", "--relation", relation, "--threshold", threshold,
        "--pretty",
    ]
    if approved:
        result.append("--approve-read")
    return result


def test_cli_provisional_success_from_pinned_real_files(capsys):
    rc = main(_args())
    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "provisionally_supported"
    assert output["cognitive_evidence_status"] == "verified"
    assert output["corpus_external_pin_verified"] is True
    assert output["spine_verified"] is True
    assert output["scientific_truth_certified"] is False


def test_cli_ambiguous_or_refuted_uses_nonzero_exit(capsys):
    rc = main(_args(threshold="100"))
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["status"] == "indeterminate"

    rc = main(_args(threshold="105"))
    assert rc == 2
    assert json.loads(capsys.readouterr().out)["status"] == "provisionally_refuted"


def test_cli_denied_before_read(capsys):
    rc = main(_args(approved=False))
    assert rc == 2
    output = json.loads(capsys.readouterr().out)
    assert output["files_read"] is False
    assert output["status"] == "blocked"


def test_cli_bad_policy_refused_without_traceback(capsys):
    rc = main(_args(threshold="__import__('os')"))
    assert rc == 2
    output = json.loads(capsys.readouterr().out)
    assert output["reason"] == "decision_policy_invalid"
    assert "traceback" not in json.dumps(output).lower()
