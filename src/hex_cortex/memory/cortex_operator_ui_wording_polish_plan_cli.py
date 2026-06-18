from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_operator_ui_wording_polish_plan import CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME
from hex_cortex.memory.cortex_operator_ui_wording_polish_plan import build_cortex_operator_ui_wording_polish_plan
from hex_cortex.memory.cortex_operator_ui_wording_polish_plan import summarize_cortex_operator_ui_wording_polish_plans


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-operator-ui-wording-polish-plan")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_operator_ui_wording_polish_plans(args.profile / CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME)
    else:
        payload = build_cortex_operator_ui_wording_polish_plan(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
