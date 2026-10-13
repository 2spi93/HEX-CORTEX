"""Inspect existing HEX-CORTEX skill pipeline without mutation or inference."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_skill_capability_audit_v25 import audit_skill_profile


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit existing skill candidates, approvals, usage and trial evidence."
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "files_written": False, "model_called": False,
        }))
        return 0
    try:
        report = audit_skill_profile(args.profile)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
