"""V18 scientific evidence → real CognitiveCircuit → Critic → CanonicalSpine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.core.cortex_scientific_evidence_circuit_v18 import (
    ScientificCircuitRefusal,
    run_scientific_evidence_circuit,
    scientific_evidence_cell_result,
    scientific_query_from_task,
    verify_scientific_evidence_cell_result,
)
from hex_cortex.core.cortex_scientific_evidence_circuit_cli_v18 import main
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.schemas import Task


def _demo():
    root = Path(__file__).resolve().parents[1] / "examples" / "scientific_v17"
    records = load_local_scientific_manifest(root / "manifest.json", approved=True)
    verifier = LocalScientificEvidenceVerifier(root, operator_approved=True)
    return root, records, verifier


def _task(domain="physics", unit="m/s"):
    return Task(
        task_id="knowledge-scientific-circuit",
        content=json.dumps({
            "claim_id": "demo_velocity", "domain": domain, "result_unit": unit,
        }),
        domain_hints=[domain], risk=0.1, novelty=0.1, uncertainty=0.1,
    )


def test_scientific_evidence_reaches_real_critic_and_verified_spine():
    _root, records, verifier = _demo()
    task = _task()
    output, circuit = run_scientific_evidence_circuit(
        task, records=records, verify_source=verifier.verify_source, approved=True,
    )
    assert output["status"] == "verified"
    assert output["verified_cell_count"] == 1
    assert output["selected_cells"] == ["scientific-evidence"]
    assert output["model_used"] is False
    assert output["checkout_modified"] is False
    assert circuit.spine.verify_integrity().ok
    assert circuit.spine.project().total_events >= 2
    assert task.content not in str(circuit.spine.events)


def test_evidence_cell_has_no_truth_or_physical_authorization_claims():
    _root, records, verifier = _demo()
    task = _task()
    candidate = scientific_evidence_cell_result(
        "scientific-evidence", task, records=records,
        verify_source=verifier.verify_source, operator_approved=True,
    )
    assert candidate.payload["truth_certified"] is False
    assert candidate.payload["physical_action_authorized"] is False
    assert verify_scientific_evidence_cell_result(
        candidate, task, records=records, verify_source=verifier.verify_source,
    )
    assert not verify_scientific_evidence_cell_result(
        candidate.model_copy(update={"payload": {"truth_certified": True}}),
        task, records=records, verify_source=verifier.verify_source,
    )


def test_missing_approval_no_host_verifier_called_and_no_spine_events():
    _root, records, _verifier = _demo()
    calls = []
    def record_call(record):
        calls.append(record)
        return True
    output, circuit = run_scientific_evidence_circuit(
        _task(), records=records, verify_source=record_call, approved=False,
    )
    assert output["status"] == "blocked"
    assert calls == []
    assert circuit.spine.events == []


def test_missing_source_verifier_blocks_science_evidence():
    _root, records, _verifier = _demo()
    output, circuit = run_scientific_evidence_circuit(
        _task(), records=records, verify_source=None, approved=True,
    )
    assert output["status"] == "blocked"
    assert circuit.spine.verify_integrity().ok


def test_sources_are_rechecked_after_cell_proposal_before_final_acceptance(
    tmp_path: Path,
):
    sample_dir, records, _verifier = _demo()
    for name in ("example.alpha.json", "example.beta.json"):
        (tmp_path / name).write_bytes((sample_dir / name).read_bytes())
    verifier = LocalScientificEvidenceVerifier(tmp_path, operator_approved=True)
    state = {"calls": 0}
    def mutate_after_first_pass(record):
        ok = verifier.verify_source(record)
        state["calls"] += 1
        if state["calls"] == 2:
            (tmp_path / "example.beta.json").write_bytes(b"tampered document")
        return ok
    result, circuit = run_scientific_evidence_circuit(
        _task(), records=records,
        verify_source=mutate_after_first_pass, approved=True,
    )
    assert state["calls"] >= 3
    assert result["status"] == "blocked"
    assert result["verified_cell_count"] == 0
    assert circuit.spine.verify_integrity().ok


def test_conflict_or_domain_mismatch_blocks_cell_without_safety_bypass():
    _root, records, verifier = _demo()
    incompatible = [
        row.model_copy(update={"value": "500"}) if row.source_id == "example.beta"
        else row for row in records
    ]
    # The changed record does not correspond to source bytes: fail closed.
    failed, circuit = run_scientific_evidence_circuit(
        _task(), records=incompatible,
        verify_source=verifier.verify_source, approved=True,
    )
    assert failed["status"] == "blocked"
    assert circuit.spine.verify_integrity().ok
    incorrect_domain, _ = run_scientific_evidence_circuit(
        _task(domain="chemistry"), records=records,
        verify_source=verifier.verify_source, approved=True,
    )
    assert incorrect_domain["status"] == "blocked"


def test_unexpected_scientific_task_keys_denied():
    with pytest.raises(ScientificCircuitRefusal, match="scientific_task_shape_invalid"):
        scientific_query_from_task(Task(
            content='{"claim_id":"demo_velocity","domain":"physics","result_unit":"m/s","exec":"rm -rf"}',
            domain_hints=["physics"],
        ))


def test_domain_hint_mismatch_is_denied():
    with pytest.raises(ScientificCircuitRefusal, match="scientific_task_domain_mismatch"):
        scientific_query_from_task(Task(
            content='{"claim_id":"demo_velocity","domain":"physics","result_unit":"m/s"}',
            domain_hints=["chemistry"],
        ))


def test_science_circuit_cli_reads_real_manifest_and_runs(capsys):
    root, _records, _verifier = _demo()
    rc = main([
        "--manifest", str(root / "manifest.json"), "--sources-dir", str(root),
        "--claim-id", "demo_velocity", "--domain", "physics", "--unit", "m/s",
        "--approve-read", "--pretty",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "verified"
    assert out["spine_verified"] is True
    assert out["physical_action_authorized"] is False


def test_science_circuit_cli_without_permission_is_nonreading(tmp_path: Path, capsys):
    rc = main([
        "--manifest", str(tmp_path / "private.json"),
        "--sources-dir", str(tmp_path), "--claim-id", "demo_velocity",
        "--domain", "physics", "--unit", "m/s",
    ])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["files_read"] is False
    assert out["model_used"] is False


def test_science_circuit_cli_with_missing_file_blocks(tmp_path: Path, capsys):
    rc = main([
        "--manifest", str(tmp_path / "nonexistent.json"),
        "--sources-dir", str(tmp_path), "--claim-id", "demo_velocity",
        "--domain", "physics", "--unit", "m/s", "--approve-read",
    ])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "blocked"
    assert out["model_used"] is False
