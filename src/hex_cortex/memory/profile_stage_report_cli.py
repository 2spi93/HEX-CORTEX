"""CLI for profile staging reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.controlled_skill_gate import (
    CONTROLLED_SKILL_GATE_FILENAME,
    evaluate_controlled_skill_gate,
    summarize_controlled_skill_gates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-stage-report")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_controlled_skill_gates(
            args.profile / CONTROLLED_SKILL_GATE_FILENAME
        )
    else:
        payload = evaluate_controlled_skill_gate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
