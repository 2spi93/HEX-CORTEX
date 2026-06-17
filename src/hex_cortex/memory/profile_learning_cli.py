"""CLI for planner learning summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.planner_replay_learning import (
    PLANNER_REPLAY_FILENAME,
    learn_from_planner_packets,
    summarize_planner_replay_learning,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-learning")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_planner_replay_learning(args.profile / PLANNER_REPLAY_FILENAME)
    else:
        payload = learn_from_planner_packets(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
