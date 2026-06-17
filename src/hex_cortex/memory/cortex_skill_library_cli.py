from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_skill_library import CORTEX_SKILL_LIBRARY_FILENAME
from hex_cortex.memory.cortex_skill_library import build_cortex_skill_library
from hex_cortex.memory.cortex_skill_library import summarize_cortex_skill_library


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-skill-library")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_skill_library(args.profile / CORTEX_SKILL_LIBRARY_FILENAME)
    else:
        payload = build_cortex_skill_library(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
