"""CLI for registry review dry runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.registry_review_dry_run import (
    REGISTRY_REVIEW_DRY_RUN_FILENAME,
    build_registry_review_dry_run,
    summarize_registry_review_dry_runs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-dry-run")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_registry_review_dry_runs(
            args.profile / REGISTRY_REVIEW_DRY_RUN_FILENAME
        )
    else:
        payload = build_registry_review_dry_run(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
