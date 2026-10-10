"""V19 source admission, revocation, versioning and rollback regressions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hex_cortex.core.cortex_scientific_corpus_cli_v19 import main
from hex_cortex.core.cortex_scientific_corpus_v19 import (
    CorpusEvent,
    CorpusOperation,
    CorpusRefusal,
    corpus_status,
    evaluate_corpus_record,
    inspect_corpus,
    load_corpus_events,
    new_corpus_event,
    record_fingerprint,
)
from hex_cortex.core.cortex_scientific_evidence_circuit_v18 import (
    run_scientific_evidence_circuit,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.schemas import Task


PIN = "8eadc291e08d7292c07519c955fa4e52611577dc57f25a16f962c2c42c6a44c5"


def _examples():
    repo = Path(__file__).resolve().parents[1]
    root = repo / "examples"
    records = load_local_scientific_manifest(
        root / "scientific_v17" / "manifest.json", approved=True,
    )
    events = load_corpus_events(
        root / "scientific_v19" / "ledger.json", approved=True,
    )
    return root, records, events


def _task() -> Task:
    return Task(
        task_id="policy-science-task",
        content=json.dumps({
            "claim_id": "demo_velocity", "domain": "physics",
            "result_unit": "m/s",
        }),
        domain_hints=["physics"], risk=0.1, novelty=0.1, uncertainty=0.1,
    )


def _copy_sources(root: Path, tmp_path: Path) -> Path:
    sources = tmp_path / "sources"
    sources.mkdir()
    for item in (root / "scientific_v17").glob("*.json"):
        (sources / item.name).write_bytes(item.read_bytes())
    return sources


def _write_events(path: Path, events: list[CorpusEvent]) -> None:
    path.write_text(
        json.dumps([event.model_dump(mode="json") for event in events]),
        encoding="utf-8",
    )


def test_committed_synthetic_ledger_pins_exact_admitted_records():
    _root, records, events = _examples()
    state, head = inspect_corpus(events, expected_head=PIN)
    assert head == PIN
    assert len(state) == 2
    for record in records:
        revision, fingerprint, active = state[record.source_id]
        assert revision == 1
        assert active is True
        assert fingerprint == record_fingerprint(record)
    assert corpus_status(events, expected_head=PIN)["sources_active"] == 2
    assert corpus_status(events, expected_head=PIN)["scientific_truth_certified"] is False


def test_real_bytes_governed_end_to_end_circuit(tmp_path: Path):
    root, records, events = _examples()
    sources = _copy_sources(root, tmp_path)
    ledger = tmp_path / "ledger.json"
    _write_events(ledger, events)
    verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)

    def verified(record):
        return evaluate_corpus_record(
            record, ledger_path=ledger, expected_head=PIN,
            base_verifier=verifier.verify_source, approved=True,
        )

    result, circuit = run_scientific_evidence_circuit(
        _task(), records=records, verify_source=verified, approved=True,
    )
    assert result["status"] == "verified"
    assert result["verified_cell_count"] == 1
    assert result["model_used"] is False
    assert result["checkout_modified"] is False
    assert circuit.spine.verify_integrity().ok


def test_revoked_source_rejected_even_though_document_hash_remains_valid(
    tmp_path: Path,
):
    root, records, events = _examples()
    sources = _copy_sources(root, tmp_path)
    ledger = tmp_path / "ledger.json"
    revoke = new_corpus_event(
        events, operation=CorpusOperation.REVOKE, source_id=records[1].source_id,
        revision=1, record_sha256=record_fingerprint(records[1]),
    )
    governed = [*events, revoke]
    _write_events(ledger, governed)
    assert inspect_corpus(governed, expected_head=revoke.event_hash)[0][
        records[1].source_id
    ][2] is False

    file_verifier = LocalScientificEvidenceVerifier(
        sources, operator_approved=True,
    )
    assert file_verifier.verify_source(records[1])  # still valid bytes
    assert not evaluate_corpus_record(
        records[1], ledger_path=ledger, expected_head=revoke.event_hash,
        base_verifier=file_verifier.verify_source, approved=True,
    )
    result, circuit = run_scientific_evidence_circuit(
        _task(), records=records,
        verify_source=lambda record: evaluate_corpus_record(
            record, ledger_path=ledger, expected_head=revoke.event_hash,
            base_verifier=file_verifier.verify_source, approved=True,
        ),
        approved=True,
    )
    assert result["status"] == "blocked"
    assert circuit.spine.verify_integrity().ok


def test_replaying_old_ledger_cannot_undo_revocation_with_externally_pinned_head(
    tmp_path: Path,
):
    root, records, events = _examples()
    ledger = tmp_path / "ledger.json"
    _write_events(ledger, events)
    revocation = new_corpus_event(
        events, operation=CorpusOperation.REVOKE, source_id=records[1].source_id,
        revision=1, record_sha256=record_fingerprint(records[1]),
    )
    with pytest.raises(CorpusRefusal, match="corpus_externally_pinned_head_mismatch"):
        inspect_corpus(load_corpus_events(ledger, approved=True),
                       expected_head=revocation.event_hash)
    file_verifier = LocalScientificEvidenceVerifier(
        root / "scientific_v17", operator_approved=True,
    )
    assert not evaluate_corpus_record(
        records[1], ledger_path=ledger, expected_head=revocation.event_hash,
        base_verifier=file_verifier.verify_source, approved=True,
    )


def test_source_revoked_between_cell_and_critic_blocks_final_verdict(
    tmp_path: Path,
):
    root, records, events = _examples()
    sources = _copy_sources(root, tmp_path)
    ledger = tmp_path / "ledger.json"
    _write_events(ledger, events)
    file_verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    calls = []

    def changing_verifier(record):
        result = evaluate_corpus_record(
            record, ledger_path=ledger, expected_head=PIN,
            base_verifier=file_verifier.verify_source, approved=True,
        )
        calls.append(record.source_id)
        if len(calls) == 2:
            revocation = new_corpus_event(
                events, operation=CorpusOperation.REVOKE,
                source_id=records[1].source_id, revision=1,
                record_sha256=record_fingerprint(records[1]),
            )
            _write_events(ledger, [*events, revocation])
        return result

    output, circuit = run_scientific_evidence_circuit(
        _task(), records=records, verify_source=changing_verifier,
        approved=True,
    )
    assert output["status"] == "blocked"
    assert len(calls) >= 3
    assert circuit.spine.verify_integrity().ok


def test_higher_revision_replaces_prior_version_and_old_record_fails(
    tmp_path: Path,
):
    root, records, events = _examples()
    original = records[0]
    revised = original.model_copy(update={"source_version": "demo.v2"})
    admit_v2 = new_corpus_event(
        events, operation=CorpusOperation.ADMIT, source_id=original.source_id,
        revision=2, record_sha256=record_fingerprint(revised),
    )
    modified = [*events, admit_v2]
    state, pin = inspect_corpus(modified, expected_head=admit_v2.event_hash)
    assert state[original.source_id] == (2, record_fingerprint(revised), True)
    assert pin == admit_v2.event_hash
    ledger = tmp_path / "ledger.json"
    _write_events(ledger, modified)
    verifier = LocalScientificEvidenceVerifier(
        root / "scientific_v17", operator_approved=True,
    )
    assert not evaluate_corpus_record(
        original, ledger_path=ledger, expected_head=pin,
        base_verifier=verifier.verify_source, approved=True,
    )
    # Even with a correctly updated ledger, old bytes do NOT match the new version.
    assert not evaluate_corpus_record(
        revised, ledger_path=ledger, expected_head=pin,
        base_verifier=verifier.verify_source, approved=True,
    )


@pytest.mark.parametrize(("operation", "revision", "reason"), [
    (CorpusOperation.ADMIT, 1, "corpus_revision_not_increasing"),
    (CorpusOperation.ADMIT, 0, "Input should be greater than or equal to 1"),
    (CorpusOperation.REVOKE, 2, "corpus_revoke_target_mismatch"),
])
def test_invalid_revision_or_revocation_rejected(operation, revision, reason):
    _root, records, events = _examples()
    with pytest.raises((CorpusRefusal, ValidationError), match=reason):
        new_corpus_event(
            events, operation=operation, source_id=records[0].source_id,
            revision=revision, record_sha256=record_fingerprint(records[0]),
        )


def test_double_revocation_and_revoke_without_admission_denied():
    _root, records, events = _examples()
    revoke = new_corpus_event(
        events, operation=CorpusOperation.REVOKE,
        source_id=records[0].source_id, revision=1,
        record_sha256=record_fingerprint(records[0]),
    )
    with pytest.raises(CorpusRefusal, match="corpus_revoke_requires_active_source"):
        new_corpus_event(
            [*events, revoke], operation=CorpusOperation.REVOKE,
            source_id=records[0].source_id, revision=1,
            record_sha256=record_fingerprint(records[0]),
        )
    with pytest.raises(CorpusRefusal, match="corpus_revoke_requires_active_source"):
        new_corpus_event([], operation=CorpusOperation.REVOKE,
                         source_id=records[0].source_id, revision=1,
                         record_sha256=record_fingerprint(records[0]))


def test_edit_any_historical_event_breaks_hash_chain():
    _root, _records, events = _examples()
    corrupted = [events[0].model_copy(update={"record_sha256": "a" * 64}), events[1]]
    with pytest.raises(CorpusRefusal, match="corpus_history_chain_invalid"):
        inspect_corpus(corrupted, expected_head=PIN)


def test_reorder_events_breaks_monotonic_chain():
    _root, _records, events = _examples()
    with pytest.raises(CorpusRefusal, match="corpus_history_chain_invalid"):
        inspect_corpus(list(reversed(events)))


def test_unpinned_ledger_not_acceptable_for_record_authorization(tmp_path: Path):
    _root, records, events = _examples()
    ledger = tmp_path / "ledger.json"
    _write_events(ledger, events)
    assert not evaluate_corpus_record(
        records[0], ledger_path=ledger, expected_head="garbage",
        base_verifier=lambda _: True, approved=True,
    )
    assert not evaluate_corpus_record(
        records[0], ledger_path=ledger, expected_head=PIN,
        base_verifier=lambda _: True, approved=False,
    )


def test_ledger_not_read_without_operator_permission(tmp_path: Path):
    with pytest.raises(CorpusRefusal, match="corpus_operator_read_approval_required"):
        load_corpus_events(tmp_path / "absent.json", approved=False)


def test_ledger_symlink_denied_when_available(tmp_path: Path):
    _root, _records, events = _examples()
    real = tmp_path / "ledger.json"
    _write_events(real, events)
    symlink = tmp_path / "alias.json"
    try:
        symlink.symlink_to(real)
    except OSError:
        pytest.skip("symlink privileges unavailable on this host")
    with pytest.raises(CorpusRefusal, match="corpus_ledger_read_or_schema_invalid"):
        load_corpus_events(symlink, approved=True)


def test_malformed_or_oversized_ledger_denied(tmp_path: Path):
    ledger = tmp_path / "ledger.json"
    ledger.write_bytes(b"{" * 100_000)
    with pytest.raises(CorpusRefusal, match="corpus_ledger_read_or_schema_invalid"):
        load_corpus_events(ledger, approved=True)
    ledger.write_text('{"action":"admit"}', encoding="utf-8")
    with pytest.raises(CorpusRefusal, match="corpus_events_budget_invalid"):
        load_corpus_events(ledger, approved=True)


def test_corpus_status_discloses_no_claims_or_source_names():
    _root, records, events = _examples()
    status = corpus_status(events, expected_head=PIN)
    assert status["external_pin_verified"] is True
    assert status["publisher_authenticity_verified"] is False
    assert records[0].source_id not in json.dumps(status)
    assert records[0].claim_id not in json.dumps(status)


def test_actual_operator_cli_verifies_pinned_corpus(capsys):
    root, _records, _events = _examples()
    rc = main([
        "--ledger", str(root / "scientific_v19" / "ledger.json"),
        "--pin", PIN,
        "--manifest", str(root / "scientific_v17" / "manifest.json"),
        "--sources-dir", str(root / "scientific_v17"),
        "--claim-id", "demo_velocity", "--domain", "physics",
        "--unit", "m/s", "--approve-read", "--pretty",
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "verified"
    assert result["corpus_external_pin_verified"] is True
    assert result["spine_verified"] is True
    assert result["scientific_truth_certified"] is False
    assert result["physical_action_authorized"] is False


def test_actual_operator_cli_rejects_wrong_trusted_pin(capsys):
    root, _records, _events = _examples()
    rc = main([
        "--ledger", str(root / "scientific_v19" / "ledger.json"),
        "--pin", "a" * 64,
        "--manifest", str(root / "scientific_v17" / "manifest.json"),
        "--sources-dir", str(root / "scientific_v17"),
        "--claim-id", "demo_velocity", "--domain", "physics",
        "--unit", "m/s", "--approve-read",
    ])
    assert rc == 2
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "corpus_externally_pinned_head_mismatch"


def test_cli_does_not_read_any_files_without_approval(capsys):
    rc = main([
        "--ledger", "absent-ledger.json", "--pin", PIN,
        "--manifest", "absent-manifest.json",
        "--sources-dir", "absent-dir",
        "--claim-id", "demo_velocity", "--domain", "physics",
        "--unit", "m/s",
    ])
    assert rc == 2
    output = json.loads(capsys.readouterr().out)
    assert output["files_read"] is False
