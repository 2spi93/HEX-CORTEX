"""CLI for registry update proposal gate reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.registry_update_proposal_gate import (
    REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME,
    evaluate_registry_update_proposal_gate,
    summarize_registry_update_proposal_gates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-proposal")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_registry_update_proposal_gates(
            args.profile / REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME
        )
    else:
        payload = evaluate_registry_update_proposal_gate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
