from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_active_skill_index import CORTEX_ACTIVE_SKILL_INDEX_FILENAME
from hex_cortex.memory.cortex_active_skill_index import build_cortex_active_skill_index
from hex_cortex.memory.cortex_active_skill_index import summarize_cortex_active_skill_indexes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-active-skill-index")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_active_skill_indexes(
            args.profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME
        )
    else:
        payload = build_cortex_active_skill_index(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
