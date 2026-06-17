"""CLI for scoring skills from local world-state candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.world_state_skill_score import (
    WORLD_STATE_SKILL_SCORE_FILENAME,
    score_latest_world_state_skill,
    summarize_world_state_skill_scores,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-skill")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_world_state_skill_scores(
            args.profile / WORLD_STATE_SKILL_SCORE_FILENAME
        )
    else:
        payload = score_latest_world_state_skill(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
