from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from hex_cortex.memory.cortex_evidence_reconciliation import append_canonical_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-service-decommission-cert")
    parser.add_argument("service_id", choices=("n8n",))
    parser.add_argument("--decommission-reference", required=True)
    parser.add_argument("--uninstalled", action="store_true")
    parser.add_argument("--no-running-service", action="store_true")
    parser.add_argument("--no-running-container", action="store_true")
    parser.add_argument("--old-secret-removed", action="store_true")
    parser.add_argument("--data-retention-reviewed", action="store_true")
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument(
        "--output",
        default=".hex-cortex/receipts/n8n-decommission.json",
    )
    parser.add_argument(
        "--evidence-jsonl",
        default=".hex-cortex/receipts/00-canonical-evidence.jsonl",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = certify_service_decommission(
        service_id=args.service_id,
        decommission_reference=args.decommission_reference,
        uninstalled=args.uninstalled,
        no_running_service=args.no_running_service,
        no_running_container=args.no_running_container,
        old_secret_removed=args.old_secret_removed,
        data_retention_reviewed=args.data_retention_reviewed,
        operator_approved=args.operator_approved,
        output_path=Path(args.output),
        evidence_jsonl=Path(args.evidence_jsonl),
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "decommissioned" else 2


def certify_service_decommission(
    *,
    service_id: str,
    decommission_reference: str,
    uninstalled: bool,
    no_running_service: bool,
    no_running_container: bool,
    old_secret_removed: bool,
    data_retention_reviewed: bool,
    operator_approved: bool,
    output_path: Path,
    evidence_jsonl: Path,
) -> dict[str, object]:
    blockers: list[str] = []
    if service_id != "n8n":
        blockers.append("service_id_not_supported")
    if not decommission_reference.strip():
        blockers.append("decommission_reference_missing")
    for ready, blocker in (
        (uninstalled, "service_not_confirmed_uninstalled"),
        (no_running_service, "running_service_not_excluded"),
        (no_running_container, "running_container_not_excluded"),
        (old_secret_removed, "old_secret_removal_not_confirmed"),
        (data_retention_reviewed, "data_retention_not_reviewed"),
        (operator_approved, "operator_approval_required"),
    ):
        if not ready:
            blockers.append(blocker)

    decommissioned = not blockers
    payload = {
        "receipt_type": "service_decommission_v1",
        "service_id": service_id,
        "status": "decommissioned" if decommissioned else "blocked",
        "uninstalled": uninstalled,
        "no_running_service": no_running_service,
        "no_running_container": no_running_container,
        "old_secret_removed": old_secret_removed,
        "data_retention_reviewed": data_retention_reviewed,
        "operator_approved": operator_approved,
        "decommission_reference_hash": (
            _hash_text(decommission_reference.strip())
            if decommission_reference.strip()
            else None
        ),
        "secret_rotation_required": False if decommissioned else None,
        "certified_at": datetime.now(UTC).isoformat(),
        "raw_secret_persisted": False,
        "blockers": sorted(set(blockers)),
        "next_action": (
            "retain_service_decommission_certificate"
            if decommissioned
            else "complete_service_decommission_controls"
        ),
    }
    payload["receipt_hash"] = _stable_hash(payload)

    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    evidence_append = None
    if decommissioned:
        evidence_append = append_canonical_evidence(
            output_path=evidence_jsonl,
            record=payload,
        )
    return {
        **payload,
        "receipt_path": str(target),
        "canonical_evidence_append": evidence_append,
    }


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
