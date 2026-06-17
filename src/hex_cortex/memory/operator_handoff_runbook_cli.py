"""CLI for operator handoff runbooks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_handoff_runbook import OPERATOR_HANDOFF_RUNBOOK_FILENAME
from hex_cortex.memory.operator_handoff_runbook import build_operator_handoff_runbook
from hex_cortex.memory.operator_handoff_runbook import summarize_operator_handoff_runbooks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operator-handoff-runbook")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_handoff_runbooks(
            args.profile / OPERATOR_HANDOFF_RUNBOOK_FILENAME
        )
    else:
        payload = build_operator_handoff_runbook(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
