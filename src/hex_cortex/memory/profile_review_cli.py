"""CLI for operator review packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.operator_review_packet import (
    OPERATOR_REVIEW_PACKET_FILENAME,
    build_operator_review_packet,
    summarize_operator_review_packets,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-review")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_operator_review_packets(
            args.profile / OPERATOR_REVIEW_PACKET_FILENAME
        )
    else:
        payload = build_operator_review_packet(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
