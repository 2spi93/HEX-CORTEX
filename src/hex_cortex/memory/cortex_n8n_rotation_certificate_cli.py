from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from hex_cortex.memory.cortex_evidence_reconciliation import append_canonical_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-n8n-rotation-cert")
    parser.add_argument("--previous-key-id", required=True)
    parser.add_argument("--active-key-id", required=True)
    parser.add_argument("--rotation-method", choices=("ui", "api"), required=True)
    parser.add_argument("--backup-reference", required=True)
    parser.add_argument("--feature-enabled-all-instances", action="store_true")
    parser.add_argument("--all-instances-restarted", action="store_true")
    parser.add_argument("--credentials-read-verified", action="store_true")
    parser.add_argument("--staging-validated", action="store_true")
    parser.add_argument("--old-key-retained-readable", action="store_true")
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument(
        "--output",
        default=".hex-cortex/receipts/n8n-secret-rotation.json",
    )
    parser.add_argument(
        "--evidence-jsonl",
        default=".hex-cortex/receipts/00-canonical-evidence.jsonl",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = certify_n8n_rotation(
        previous_key_id=args.previous_key_id,
        active_key_id=args.active_key_id,
        rotation_method=args.rotation_method,
        backup_reference=args.backup_reference,
        feature_enabled_all_instances=args.feature_enabled_all_instances,
        all_instances_restarted=args.all_instances_restarted,
        credentials_read_verified=args.credentials_read_verified,
        staging_validated=args.staging_validated,
        old_key_retained_readable=args.old_key_retained_readable,
        operator_approved=args.operator_approved,
        output_path=Path(args.output),
        evidence_jsonl=Path(args.evidence_jsonl),
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "rotated" else 2


def certify_n8n_rotation(
    *,
    previous_key_id: str,
    active_key_id: str,
    rotation_method: str,
    backup_reference: str,
    feature_enabled_all_instances: bool,
    all_instances_restarted: bool,
    credentials_read_verified: bool,
    staging_validated: bool,
    old_key_retained_readable: bool,
    operator_approved: bool,
    output_path: Path,
    evidence_jsonl: Path,
) -> dict[str, object]:
    blockers: list[str] = []
    if not operator_approved:
        blockers.append("operator_approval_required")
    if rotation_method not in {"ui", "api"}:
        blockers.append("rotation_method_invalid")
    if not previous_key_id.strip() or not active_key_id.strip():
        blockers.append("key_id_missing")
    if previous_key_id.strip() == active_key_id.strip():
        blockers.append("active_key_id_unchanged")
    if not backup_reference.strip():
        blockers.append("database_backup_reference_missing")
    for ready, blocker in (
        (feature_enabled_all_instances, "rotation_feature_not_confirmed_all_instances"),
        (all_instances_restarted, "all_instances_restart_not_confirmed"),
        (credentials_read_verified, "credential_decryption_not_verified"),
        (staging_validated, "staging_validation_not_confirmed"),
        (old_key_retained_readable, "previous_key_readability_not_confirmed"),
    ):
        if not ready:
            blockers.append(blocker)

    rotated = not blockers
    payload = {
        "receipt_type": "secret_rotation_v1",
        "secret_id": "n8n",
        "rotation_scope": "n8n_data_encryption_key",
        "status": "rotated" if rotated else "blocked",
        "rotation_method": rotation_method,
        "previous_key_id_hash": _hash_text(previous_key_id.strip()) if previous_key_id.strip() else None,
        "active_key_id_hash": _hash_text(active_key_id.strip()) if active_key_id.strip() else None,
        "key_material_persisted": False,
        "database_backup_confirmed": bool(backup_reference.strip()),
        "backup_reference_hash": _hash_text(backup_reference.strip()) if backup_reference.strip() else None,
        "feature_enabled_all_instances": feature_enabled_all_instances,
        "all_instances_restarted": all_instances_restarted,
        "credentials_read_verified": credentials_read_verified,
        "staging_validated": staging_validated,
        "previous_key_retained_readable": old_key_retained_readable,
        "operator_approved": operator_approved,
        "certified_at": datetime.now(UTC).isoformat(),
        "raw_secret_persisted": False,
        "blockers": sorted(set(blockers)),
        "next_action": "retain_security_certificate" if rotated else "complete_n8n_rotation_controls",
    }
    payload["receipt_hash"] = _stable_hash(payload)

    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    evidence_append = None
    if rotated:
        evidence_append = append_canonical_evidence(output_path=evidence_jsonl, record=payload)
    return {**payload, "receipt_path": str(target), "canonical_evidence_append": evidence_append}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
