from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_v14_advanced_modules_plan import CORTEX_V14_ADVANCED_MODULES_PLAN_FILENAME
from hex_cortex.memory.cortex_v14_advanced_modules_plan import build_cortex_v14_advanced_modules_plan
from hex_cortex.memory.cortex_v14_advanced_modules_plan import summarize_cortex_v14_advanced_modules_plans


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-v14-advanced-modules-plan")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_v14_advanced_modules_plans(args.profile / CORTEX_V14_ADVANCED_MODULES_PLAN_FILENAME)
    else:
        payload = build_cortex_v14_advanced_modules_plan(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
