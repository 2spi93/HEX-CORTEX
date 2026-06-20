import json
from pathlib import Path

from hex_cortex.memory.cortex_service_decommission_certificate_cli import (
    certify_service_decommission,
)


def test_n8n_decommission_certificate_closes_old_secret_scope(tmp_path: Path) -> None:
    output = tmp_path / "n8n-decommission.json"
    evidence = tmp_path / "evidence.jsonl"
    payload = certify_service_decommission(
        service_id="n8n",
        decommission_reference="n8n-removed-2026-06-20",
        uninstalled=True,
        no_running_service=True,
        no_running_container=True,
        old_secret_removed=True,
        data_retention_reviewed=True,
        operator_approved=True,
        output_path=output,
        evidence_jsonl=evidence,
    )

    assert payload["status"] == "decommissioned"
    assert payload["secret_rotation_required"] is False
    assert payload["raw_secret_persisted"] is False
    persisted = output.read_text(encoding="utf-8")
    assert "n8n-removed-2026-06-20" not in persisted
    canonical = json.loads(evidence.read_text(encoding="utf-8").strip())
    assert canonical["receipt_type"] == "service_decommission_v1"
    assert canonical["service_id"] == "n8n"


def test_n8n_decommission_certificate_requires_old_secret_removal(tmp_path: Path) -> None:
    payload = certify_service_decommission(
        service_id="n8n",
        decommission_reference="removed",
        uninstalled=True,
        no_running_service=True,
        no_running_container=True,
        old_secret_removed=False,
        data_retention_reviewed=True,
        operator_approved=True,
        output_path=tmp_path / "n8n.json",
        evidence_jsonl=tmp_path / "evidence.jsonl",
    )

    assert payload["status"] == "blocked"
    assert "old_secret_removal_not_confirmed" in payload["blockers"]
    assert payload["canonical_evidence_append"] is None
