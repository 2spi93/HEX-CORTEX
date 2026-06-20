from pathlib import Path

from hex_cortex.memory.cortex_operational_audit_v2 import (
    audit_hermes_fleet_evidence,
    audit_security_disposition,
)


def test_security_accepts_certified_n8n_decommission(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows" / "secret-scan.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Secret Scan\n", encoding="utf-8")
    receipts = [
        {
            "receipt_type": "service_decommission_v1",
            "service_id": "n8n",
            "status": "decommissioned",
            "uninstalled": True,
            "no_running_service": True,
            "no_running_container": True,
            "old_secret_removed": True,
            "data_retention_reviewed": True,
            "raw_secret_persisted": False,
        }
    ]

    payload = audit_security_disposition(tmp_path, receipts)

    assert payload["security_operational_ready"] is True
    assert payload["n8n_security_disposition"] == "decommissioned"
    assert payload["n8n_secret_rotation_certified"] is False


def test_hermes_fleet_receipt_enables_server_facts() -> None:
    payload = audit_hermes_fleet_evidence(
        [
            {
                "receipt_type": "hermes_fleet_certificate_v1",
                "status": "ready",
                "dual_node_ready": True,
                "private_transport_ready": True,
                "hermes_adapter_ready": True,
                "server_primary_ready": True,
                "kali_vm_ready": True,
                "memory_policy": "separate_no_merge",
                "raw_secret_persisted": False,
            }
        ]
    )

    assert payload["fleet_ready"] is True
    assert payload["server_primary_ready"] is True
    assert payload["kali_vm_ready"] is True
