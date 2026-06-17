"""CLI for matching latent states to the skill registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.skill_registry_integration import (
    SKILL_REGISTRY_MATCH_FILENAME,
    match_latest_latent_to_skill_registry,
    summarize_skill_registry_matches,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-registry")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_skill_registry_matches(
            args.profile / SKILL_REGISTRY_MATCH_FILENAME
        )
    else:
        payload = match_latest_latent_to_skill_registry(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
