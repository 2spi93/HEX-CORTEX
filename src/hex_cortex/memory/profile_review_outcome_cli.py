"""CLI for operator review outcomes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_review_outcome import (
    OPERATOR_REVIEW_OUTCOME_FILENAME,
    record_operator_review_outcome,
    summarize_operator_review_outcomes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-review-outcome")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--outcome", default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_review_outcomes(
            args.profile / OPERATOR_REVIEW_OUTCOME_FILENAME
        )
    else:
        payload = record_operator_review_outcome(
            args.profile,
            requested_outcome=args.outcome,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
