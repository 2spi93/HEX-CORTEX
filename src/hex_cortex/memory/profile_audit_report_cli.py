"""CLI for profile audit reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.skill_execution_audit import (
    SKILL_EXECUTION_AUDIT_FILENAME,
    build_skill_execution_audit,
    summarize_skill_execution_audits,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-audit-report")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_skill_execution_audits(
            args.profile / SKILL_EXECUTION_AUDIT_FILENAME
        )
    else:
        payload = build_skill_execution_audit(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
