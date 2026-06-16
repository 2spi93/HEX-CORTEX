"""CLI for compact profile operator status history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.profile_operator_status_history import (
    STATUS_HISTORY_FILENAME,
    record_profile_operator_status_history,
    summarize_profile_operator_status_history,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-operator-status-history")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--policy-limit", type=int, default=6)
    parser.add_argument("--policy-stability-window", type=int, default=3)
    parser.add_argument("--minimum-ready-score", type=float, default=1.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_profile_operator_status_history(
            args.profile / STATUS_HISTORY_FILENAME,
        )
    else:
        payload = record_profile_operator_status_history(
            args.profile,
            refresh=args.refresh,
            policy_limit=args.policy_limit,
            policy_stability_window=args.policy_stability_window,
            minimum_ready_score=args.minimum_ready_score,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
