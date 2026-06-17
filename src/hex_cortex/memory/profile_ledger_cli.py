"""CLI for operator signature ledger records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_signature_ledger import (
    OPERATOR_SIGNATURE_LEDGER_FILENAME,
    build_operator_signature_ledger,
    summarize_operator_signature_ledgers,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-ledger")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_signature_ledgers(
            args.profile / OPERATOR_SIGNATURE_LEDGER_FILENAME
        )
    else:
        payload = build_operator_signature_ledger(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
