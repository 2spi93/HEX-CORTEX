"""CLI for review audit bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.review_audit_bundle import (
    REVIEW_AUDIT_BUNDLE_FILENAME,
    build_review_audit_bundle,
    summarize_review_audit_bundles,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-bundle")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_review_audit_bundles(
            args.profile / REVIEW_AUDIT_BUNDLE_FILENAME
        )
    else:
        payload = build_review_audit_bundle(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
