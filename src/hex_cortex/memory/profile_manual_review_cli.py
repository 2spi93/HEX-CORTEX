"""CLI for manual operator review notes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.manual_review_note import (
    MANUAL_REVIEW_NOTE_FILENAME,
    record_manual_review_note,
    summarize_manual_review_notes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-manual-review")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--skill", default="operator_watch_review")
    parser.add_argument("--choice", choices=["accept", "decline", "hold"], default="hold")
    parser.add_argument("--note", default="manual review recorded")
    parser.add_argument("--reviewer", default="operator_local")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_manual_review_notes(args.profile / MANUAL_REVIEW_NOTE_FILENAME)
    else:
        payload = record_manual_review_note(
            args.profile,
            selected_skill=args.skill,
            choice=args.choice,
            note=args.note,
            reviewer=args.reviewer,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
