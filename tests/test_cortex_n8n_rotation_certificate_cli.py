import json
from pathlib import Path

from hex_cortex.memory.cortex_n8n_rotation_certificate_cli import certify_n8n_rotation


def test_n8n_rotation_certificate_persists_only_hashes(tmp_path: Path) -> None:
    output = tmp_path / "rotation.json"
    evidence = tmp_path / "evidence.jsonl"
    payload = certify_n8n_rotation(
        previous_key_id="old-key-metadata-id",
        active_key_id="new-key-metadata-id",
        rotation_method="ui",
        backup_reference="backup-2026-06-20T1200Z",
        feature_enabled_all_instances=True,
        all_instances_restarted=True,
        credentials_read_verified=True,
        staging_validated=True,
        old_key_retained_readable=True,
        operator_approved=True,
        output_path=output,
        evidence_jsonl=evidence,
    )

    assert payload["status"] == "rotated"
    assert payload["raw_secret_persisted"] is False
    assert payload["key_material_persisted"] is False
    persisted = output.read_text(encoding="utf-8")
    assert "old-key-metadata-id" not in persisted
    assert "new-key-metadata-id" not in persisted
    assert "backup-2026-06-20T1200Z" not in persisted
    canonical = json.loads(evidence.read_text(encoding="utf-8").strip())
    assert canonical["receipt_type"] == "secret_rotation_v1"
    assert canonical["secret_id"] == "n8n"
    assert canonical["status"] == "rotated"


def test_n8n_rotation_certificate_rejects_same_key_id(tmp_path: Path) -> None:
    payload = certify_n8n_rotation(
        previous_key_id="same",
        active_key_id="same",
        rotation_method="api",
        backup_reference="backup-ref",
        feature_enabled_all_instances=True,
        all_instances_restarted=True,
        credentials_read_verified=True,
        staging_validated=True,
        old_key_retained_readable=True,
        operator_approved=True,
        output_path=tmp_path / "rotation.json",
        evidence_jsonl=tmp_path / "evidence.jsonl",
    )

    assert payload["status"] == "blocked"
    assert "active_key_id_unchanged" in payload["blockers"]
    assert payload["canonical_evidence_append"] is None


def test_n8n_rotation_certificate_requires_all_controls(tmp_path: Path) -> None:
    payload = certify_n8n_rotation(
        previous_key_id="old",
        active_key_id="new",
        rotation_method="ui",
        backup_reference="",
        feature_enabled_all_instances=False,
        all_instances_restarted=False,
        credentials_read_verified=False,
        staging_validated=False,
        old_key_retained_readable=False,
        operator_approved=False,
        output_path=tmp_path / "rotation.json",
        evidence_jsonl=tmp_path / "evidence.jsonl",
    )

    assert payload["status"] == "blocked"
    assert "operator_approval_required" in payload["blockers"]
    assert "database_backup_reference_missing" in payload["blockers"]
    assert payload["canonical_evidence_append"] is None
