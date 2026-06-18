from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_controlled_skill_use import CORTEX_CONTROLLED_SKILL_USE_FILENAME
from hex_cortex.memory.cortex_controlled_skill_use import record_cortex_controlled_skill_use
from hex_cortex.memory.cortex_controlled_skill_use import summarize_cortex_controlled_skill_uses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-controlled-skill-use")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--intent", default="inspect")
    parser.add_argument("--task", default="inspect active skill guidance")
    parser.add_argument("--skill-key", default=None)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_controlled_skill_uses(
            args.profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME
        )
    else:
        payload = record_cortex_controlled_skill_use(
            args.profile,
            intent=args.intent,
            task_text=args.task,
            skill_key=args.skill_key,
            domain=args.domain,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
