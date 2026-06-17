from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_command_intake import OPERATOR_COMMAND_INTAKE_FILENAME
from hex_cortex.memory.operator_command_intake import ingest_operator_command
from hex_cortex.memory.operator_command_intake import summarize_operator_command_intakes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operator-command-intake")
    parser.add_argument("profile", type=Path)
    parser.add_argument("command", nargs="*")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_command_intakes(
            args.profile / OPERATOR_COMMAND_INTAKE_FILENAME
        )
    else:
        payload = ingest_operator_command(args.profile, " ".join(args.command))
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
