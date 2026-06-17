"""CLI for scoring local world-state candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.world_state_candidate_evaluation import (
    WORLD_STATE_EVALUATION_FILENAME,
    evaluate_latest_world_state_candidate,
    summarize_world_state_candidate_evaluations,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-world-score")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_world_state_candidate_evaluations(
            args.profile / WORLD_STATE_EVALUATION_FILENAME
        )
    else:
        payload = evaluate_latest_world_state_candidate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
