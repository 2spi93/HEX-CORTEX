from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_branch_plan_review_gate import CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME
from hex_cortex.memory.cortex_branch_plan_review_gate import build_cortex_branch_plan_review_gate
from hex_cortex.memory.cortex_branch_plan_review_gate import summarize_cortex_branch_plan_review_gates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-branch-plan-review-gate")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_branch_plan_review_gates(
            args.profile / CORTEX_BRANCH_PLAN_REVIEW_GATE_FILENAME
        )
    else:
        payload = build_cortex_branch_plan_review_gate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
