"""CLI for scoring profile cognitive traces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cognitive_trace_evaluation import (
    EVALUATION_FILENAME,
    evaluate_latest_cognitive_trace,
    summarize_cognitive_trace_evaluations,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-score")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cognitive_trace_evaluations(args.profile / EVALUATION_FILENAME)
    else:
        payload = evaluate_latest_cognitive_trace(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
