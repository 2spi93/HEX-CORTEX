from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_operational_audit import _category_blockers
from hex_cortex.memory.cortex_operational_audit import _iter_receipts
from hex_cortex.memory.cortex_operational_audit import _next_action
from hex_cortex.memory.cortex_operational_audit import build_operational_audit as build_operational_audit_v1
from hex_cortex.memory.cortex_operational_audit import write_operational_audit_receipt
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring


def build_operational_audit(project_root: Path, **kwargs: object) -> dict[str, object]:
    payload = build_operational_audit_v1(project_root, **kwargs)
    root = project_root.resolve()
    receipts = list(_iter_receipts(root / ".hex-cortex"))
    security = audit_security_disposition(root, receipts)
    hermes_fleet = audit_hermes_fleet_evidence(receipts)
    cognitive_genome = audit_cognitive_genome(root / "config" / "cognitive_genome_v1.json")

    facts_value = payload.get("runtime_facts")
    facts = dict(facts_value) if isinstance(facts_value, dict) else {}
    if hermes_fleet["fleet_ready"] is True:
        facts["hermes_adapter_available"] = True
        facts["private_or_tunneled_transport_available"] = True

    wiring = audit_cortex_wiring(build_cortex_bundle(), runtime_facts=facts)
    category_blockers = _category_blockers(
        facts=facts,
        wiring=wiring,
        policy_v2=_dict(payload.get("screen_lab_policy_v2")),
        self_correction=_dict(payload.get("self_correction")),
        remote_api=_dict(payload.get("remote_api")),
        security=security,
    )
    category_blockers["cognitive_genome_ready"] = (
        []
        if cognitive_genome.get("genome_ready") is True
        else list(cognitive_genome.get("blockers", ["cognitive_genome_not_ready"]))
    )
    categories = {name: not blockers for name, blockers in category_blockers.items()}
    branch_ready = all(
        categories[name]
        for name in (
            "code_ready",
            "runtime_ready",
            "models_ready",
            "research_ready",
            "media_ready",
            "world_model_ready",
            "policy_v2_ready",
            "self_correction_ready",
            "remote_api_ready",
            "security_ready",
            "cognitive_genome_ready",
        )
    )
    operational_ready = branch_ready and categories["server_ready"]

    payload.update(
        {
            **categories,
            "branch_ready": branch_ready,
            "operational_ready": operational_ready,
            "runtime_facts": facts,
            "category_blockers": category_blockers,
            "wiring": wiring,
            "security": security,
            "hermes_fleet": hermes_fleet,
            "cognitive_genome": cognitive_genome,
            "next_action": _next_action(category_blockers),
        }
    )
    payload.pop("audit_hash", None)
    payload["audit_hash"] = _stable_hash(payload)
    return payload


def audit_security_disposition(
    project_root: Path,
    receipts: list[dict[str, object]],
) -> dict[str, object]:
    gitignore = _read_text(project_root / ".gitignore")
    env_ignored = any(
        line.strip() in {".env", "*.env", "**/.env"}
        for line in gitignore.splitlines()
    )
    secret_scan_configured = any(
        (project_root / path).is_file()
        for path in (
            ".gitleaks.toml",
            ".github/workflows/secret-scan.yml",
            ".github/workflows/secrets.yml",
        )
    )
    n8n_rotated = any(
        row.get("receipt_type") == "secret_rotation_v1"
        and row.get("secret_id") == "n8n"
        and row.get("status") == "rotated"
        for row in receipts
    )
    n8n_decommissioned = any(
        row.get("receipt_type") == "service_decommission_v1"
        and row.get("service_id") == "n8n"
        and row.get("status") == "decommissioned"
        and row.get("uninstalled") is True
        and row.get("no_running_service") is True
        and row.get("no_running_container") is True
        and row.get("old_secret_removed") is True
        and row.get("data_retention_reviewed") is True
        and row.get("raw_secret_persisted") is False
        for row in receipts
    )
    n8n_disposition_ready = n8n_rotated or n8n_decommissioned
    ready = env_ignored and secret_scan_configured and n8n_disposition_ready
    blockers = []
    if not env_ignored:
        blockers.append("env_ignore_policy_missing")
    if not secret_scan_configured:
        blockers.append("ci_secret_detection_missing")
    if not n8n_disposition_ready:
        blockers.append("n8n_security_disposition_not_certified")
    disposition = "rotated" if n8n_rotated else "decommissioned" if n8n_decommissioned else "pending"
    return {
        "audit_type": "security_operational_audit_v2",
        "env_ignore_policy_ready": env_ignored,
        "secret_scan_configured": secret_scan_configured,
        "n8n_secret_rotation_certified": n8n_rotated,
        "n8n_service_decommission_certified": n8n_decommissioned,
        "n8n_security_disposition": disposition,
        "security_contract_ready": env_ignored,
        "security_operational_ready": ready,
        "blockers": blockers,
        "next_action": "retain_security_certificate" if ready else "close_security_blockers",
    }


def audit_hermes_fleet_evidence(
    receipts: list[dict[str, object]],
) -> dict[str, object]:
    certificates = [
        row
        for row in receipts
        if row.get("receipt_type") == "hermes_fleet_certificate_v1"
        and row.get("status") == "ready"
    ]
    latest = certificates[-1] if certificates else {}
    ready = (
        latest.get("dual_node_ready") is True
        and latest.get("private_transport_ready") is True
        and latest.get("hermes_adapter_ready") is True
        and latest.get("memory_policy") == "separate_no_merge"
        and latest.get("raw_secret_persisted") is False
    )
    return {
        "audit_type": "hermes_fleet_operational_audit_v1",
        "fleet_ready": ready,
        "server_primary_ready": latest.get("server_primary_ready") is True,
        "kali_vm_ready": latest.get("kali_vm_ready") is True,
        "private_transport_ready": latest.get("private_transport_ready") is True,
        "memory_policy": latest.get("memory_policy"),
        "blockers": [] if ready else ["hermes_dual_node_fleet_not_certified"],
        "next_action": "operate_hermes_fleet" if ready else "certify_hermes_dual_node_fleet",
    }


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "audit_hermes_fleet_evidence",
    "audit_security_disposition",
    "build_operational_audit",
    "write_operational_audit_receipt",
]
