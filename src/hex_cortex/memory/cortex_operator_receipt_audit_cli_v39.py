"""Read-only CLI for operator V38 real-CPU receipt consistency audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_operator_receipt_audit_v39 import (
    audit_uploaded_v38_receipts_v39,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V39: inspect actual V38 operator receipts; no weights, no model"
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest", default="research/v38_uploaded/boxes.json")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true")
    group.add_argument("--run-dir")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "files_read": False,
            "files_written": False, "model_called": False,
        }, sort_keys=True))
        return 0
    try:
        report = audit_uploaded_v38_receipts_v39(
            project_root=Path(args.project_root),
            run_selection=args.run_dir or "latest",
            manifest_path=args.manifest,
            approved_read=args.approve_read,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reason = str(exc)
        report = {
            "status": "blocked",
            "reason": reason if reason.startswith("v39_") else "v39_invalid_operator_receipt",
            "files_written": False, "model_called": False,
        }
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "v39_receipt_consistency_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
