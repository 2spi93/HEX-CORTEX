"""Inspect or revoke V25 skill-trial evidence. Never executes a model."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_procedural_skill_evidence_v25 import (
    assess_skill_evidence,
    revoke_skill,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only skill status or explicit operator revocation."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--skill", required=True, choices=[
        "multiply_decomposition", "fraction_reduction", "addition_compensation",
    ])
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--reason")
    parser.add_argument("--approve-revoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "files_written": False, "model_called": False,
        }))
        return 0
    if args.revoke and not (args.approve_revoke and args.reason):
        parser.error("revocation requires --reason and --approve-revoke")
    if not args.revoke and (args.approve_revoke or args.reason):
        parser.error("revocation flags are only valid together with --revoke")
    try:
        if args.revoke:
            output = revoke_skill(
                project_root=args.project_root, skill_id=args.skill,
                reason=args.reason, approved=True,
            )
        else:
            output = assess_skill_evidence(
                project_root=args.project_root, skill_id=args.skill,
            )
    except (ValueError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
