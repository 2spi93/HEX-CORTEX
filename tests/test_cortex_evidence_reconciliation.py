import json
from pathlib import Path

from hex_cortex.memory.cortex_evidence_reconciliation import append_canonical_evidence
from hex_cortex.memory.cortex_evidence_reconciliation import reconcile_evidence_receipts


def test_reconciliation_reads_pretty_json_and_jsonl(tmp_path: Path) -> None:
    state_root = tmp_path / ".hex-cortex"
    receipts = state_root / "receipts" / "self-correction"
    receipts.mkdir(parents=True)
    (receipts / "worktree.json").write_text(
        json.dumps(
            {"receipt_type": "isolated_worktree_create_v1", "status": "created"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (receipts / "checks.jsonl").write_text(
        json.dumps({"receipt_type": "allowlisted_check_run_v1", "status": "passed"})
        + "\n",
        encoding="utf-8",
    )

    payload = reconcile_evidence_receipts(state_root=state_root)

    assert payload["status"] == "reconciled"
    assert payload["record_count"] == 2
    output = Path(str(payload["output_path"]))
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert {row["receipt_type"] for row in rows} == {
        "isolated_worktree_create_v1",
        "allowlisted_check_run_v1",
    }


def test_reconciliation_strips_volatile_and_secret_fields(tmp_path: Path) -> None:
    state_root = tmp_path / ".hex-cortex"
    receipts = state_root / "receipts"
    receipts.mkdir(parents=True)
    (receipts / "remote.json").write_text(
        json.dumps(
            {
                "receipt_type": "coding_model_execution_v1",
                "status": "completed",
                "volatile_result_text": "do not persist",
                "authorization": "Bearer secret",
                "raw_secret_persisted": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = reconcile_evidence_receipts(state_root=state_root)
    row = json.loads(
        Path(str(payload["output_path"])).read_text(encoding="utf-8").splitlines()[0]
    )

    assert "volatile_result_text" not in row
    assert "authorization" not in row
    assert row["raw_secret_persisted"] is False
    assert row["reconciled_sensitive_fields_removed"] == [
        "authorization",
        "volatile_result_text",
    ]


def test_append_canonical_evidence_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "00-canonical-evidence.jsonl"
    record = {"receipt_type": "coding_model_execution_v1", "status": "completed"}

    first = append_canonical_evidence(output_path=target, record=record)
    second = append_canonical_evidence(output_path=target, record=record)

    assert first["status"] == "appended"
    assert second["status"] == "already_present"
    assert len(target.read_text(encoding="utf-8").splitlines()) == 1
