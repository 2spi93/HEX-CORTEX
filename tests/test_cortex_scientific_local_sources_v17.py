"""V17 real filesystem evidence bytes: intentional forgery and tamper boundaries."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceKind,
    EvidenceQuery,
    EvidenceRecord,
    review_scientific_knowledge,
)
from hex_cortex.core.cortex_scientific_knowledge_cli_v17 import main
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal,
    LocalScientificEvidenceVerifier,
    expected_scientific_source_bytes,
    load_local_scientific_manifest,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain


def _record(source_id: str, value: str = "100", unit: str = "m/s") -> EvidenceRecord:
    return EvidenceRecord(
        claim_id="test_speed",
        domain=KnowledgeDomain.PHYSICS,
        value=value, unit=unit,
        absolute_uncertainty="1", kind=EvidenceKind.MEASUREMENT,
        source_id=source_id,
        source_uri="https://example.org/synthetic/" + source_id,
        source_version="synthetic.1",
        source_digest_sha256="0" * 64,
        source_license="synthetic-fixture-no-truth-claim",
        published_on=date(2026, 10, 10),
    )


def _fixture(root: Path, *, value_b: str = "100"):
    sources = root / "science"
    sources.mkdir()
    records = []
    for source_id, value in [("source.alpha", "100"), ("source.beta", value_b)]:
        template = _record(source_id, value)
        raw = expected_scientific_source_bytes(template)
        (sources / (source_id + ".json")).write_bytes(raw)
        records.append(template.model_copy(update={
            "source_digest_sha256": hashlib.sha256(raw).hexdigest(),
        }))
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps([r.model_dump(mode="json") for r in records]),
        encoding="utf-8",
    )
    return sources, manifest, records


def _query() -> EvidenceQuery:
    return EvidenceQuery(
        claim_id="test_speed", domain=KnowledgeDomain.PHYSICS, result_unit="m/s"
    )


def test_real_bytes_and_structured_claims_read_to_consistent_receipt(tmp_path: Path):
    sources, manifest, _records = _fixture(tmp_path)
    records = load_local_scientific_manifest(manifest, approved=True)
    verified = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert all(verified.verify_source(r) for r in records)
    result = review_scientific_knowledge(
        _query(), records, operator_approved=True,
        verify_source=verified.verify_source,
    )
    assert result["status"] == "consistent_evidence_not_certified"
    assert result["host_checked_source_count"] == 2
    assert result["truth_certified"] is False
    assert result["source_independence_certified"] is False


def test_no_manifest_read_without_operator_approval(tmp_path: Path):
    sources, manifest, records = _fixture(tmp_path)
    with pytest.raises(LocalEvidenceRefusal, match="local_evidence_read_approval_required"):
        load_local_scientific_manifest(manifest, approved=False)
    assert not LocalScientificEvidenceVerifier(
        sources, operator_approved=False
    ).verify_source(records[0])


def test_tampered_source_bytes_block_consensus(tmp_path: Path):
    sources, manifest, records = _fixture(tmp_path)
    file_path = sources / "source.beta.json"
    raw = file_path.read_bytes()
    file_path.write_bytes(raw.replace(b'"value":"100"', b'"value":"110"'))
    verified = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert verified.verify_source(records[0])
    assert not verified.verify_source(records[1])
    result = review_scientific_knowledge(
        _query(), load_local_scientific_manifest(manifest, approved=True),
        operator_approved=True, verify_source=verified.verify_source,
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "knowledge_source_not_verified_by_host"


def test_attacker_rehashing_source_alone_does_not_change_manifest(tmp_path: Path):
    sources, _manifest, records = _fixture(tmp_path)
    altered = records[0].model_copy(update={"value": "555"})
    # A fabricated record cannot pass verification against the unchanged
    # source witness, even though the source file itself remains valid.
    verified = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert not verified.verify_source(altered)
    assert verified.verify_source(records[0])


def test_revised_manifest_without_matching_bytes_fails(tmp_path: Path):
    sources, manifest, records = _fixture(tmp_path)
    edited = records[0].model_copy(update={
        "source_digest_sha256": "f" * 64,
    })
    assert not LocalScientificEvidenceVerifier(sources, operator_approved=True).verify_source(edited)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw[0]["source_digest_sha256"] = "f" * 64
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    loaded = load_local_scientific_manifest(manifest, approved=True)
    assert loaded[0].source_digest_sha256 == "f" * 64
    assert not LocalScientificEvidenceVerifier(sources, operator_approved=True).verify_source(loaded[0])


def test_source_or_directory_symlinks_denied(tmp_path: Path):
    sources, _manifest, records = _fixture(tmp_path)
    malicious = sources / "source.beta.json"
    malicious.unlink()
    try:
        malicious.symlink_to(sources / "source.alpha.json")
    except OSError:
        pytest.skip("creating symlinks requires privileges on this host")
    verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert verifier.verify_source(records[0])
    assert not verifier.verify_source(records[1])


def test_nonexistent_source_fails_closed(tmp_path: Path):
    sources, _manifest, records = _fixture(tmp_path)
    (sources / "source.beta.json").unlink()
    verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert not verifier.verify_source(records[1])


def test_manifest_large_or_malformed_denied(tmp_path: Path):
    source = tmp_path / "manifest.json"
    source.write_bytes(b"x" * 70_000)
    with pytest.raises(LocalEvidenceRefusal, match="local_evidence_bytes_budget_exceeded"):
        load_local_scientific_manifest(source, approved=True)
    source.write_text("{bad", encoding="utf-8")
    with pytest.raises(LocalEvidenceRefusal, match="local_evidence_manifest_invalid"):
        load_local_scientific_manifest(source, approved=True)


def test_source_larger_than_budget_denied(tmp_path: Path):
    sources, _manifest, records = _fixture(tmp_path)
    (sources / "source.alpha.json").write_bytes(b"x" * 20_000)
    assert not LocalScientificEvidenceVerifier(
        sources, operator_approved=True,
    ).verify_source(records[0])


def test_cli_without_read_approval_is_nonreading(tmp_path: Path, capsys):
    exit_code = main([
        "--manifest", str(tmp_path / "never.json"),
        "--sources-dir", str(tmp_path / "never"),
        "--claim-id", "test_speed", "--domain", "physics",
        "--unit", "m/s",
    ])
    assert exit_code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["files_read"] is False


def test_cli_real_local_source_match(tmp_path: Path, capsys):
    sources, manifest, _records = _fixture(tmp_path)
    code = main([
        "--manifest", str(manifest), "--sources-dir", str(sources),
        "--claim-id", "test_speed", "--domain", "physics",
        "--unit", "m/s", "--approve-read", "--pretty",
    ])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "consistent_evidence_not_certified"
    assert report["truth_certified"] is False


def test_cli_actual_document_disagreement(tmp_path: Path, capsys):
    sources, manifest, _records = _fixture(tmp_path, value_b="110")
    code = main([
        "--manifest", str(manifest), "--sources-dir", str(sources),
        "--claim-id", "test_speed", "--domain", "physics",
        "--unit", "m/s", "--approve-read",
    ])
    assert code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "conflict"
    assert report["reason"] == "knowledge_source_intervals_disagree"


def test_cli_no_source_directory_cannot_claim_verified(tmp_path: Path, capsys):
    sources, manifest, _records = _fixture(tmp_path)
    code = main([
        "--manifest", str(manifest), "--sources-dir", str(sources / "missing"),
        "--claim-id", "test_speed", "--domain", "physics",
        "--unit", "m/s", "--approve-read",
    ])
    assert code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"


def test_operator_cannot_inject_path_from_source_identifier(tmp_path: Path):
    sources, _manifest, records = _fixture(tmp_path)
    malicious = records[0].model_copy(update={"source_id": "evil/../../secret"})
    verifier = LocalScientificEvidenceVerifier(sources, operator_approved=True)
    assert not verifier.verify_source(malicious)



def test_checked_in_demo_manifest_and_source_octets_match_on_this_os(capsys):
    repo = Path(__file__).resolve().parents[1]
    location = repo / "examples" / "scientific_v17"
    records = load_local_scientific_manifest(location / "manifest.json", approved=True)
    verifier = LocalScientificEvidenceVerifier(location, operator_approved=True)
    assert len(records) == 2
    assert all(verifier.verify_source(item) for item in records)
    code = main([
        "--manifest", str(location / "manifest.json"),
        "--sources-dir", str(location),
        "--claim-id", "demo_velocity", "--domain", "physics",
        "--unit", "m/s", "--approve-read",
    ])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "consistent_evidence_not_certified"
    assert report["interval_lower"] == "99"
    assert report["interval_upper"] == "101"
