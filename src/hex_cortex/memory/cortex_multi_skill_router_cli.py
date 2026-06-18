from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_multi_skill_router import CORTEX_MULTI_SKILL_ROUTER_FILENAME
from hex_cortex.memory.cortex_multi_skill_router import build_cortex_multi_skill_router
from hex_cortex.memory.cortex_multi_skill_router import summarize_cortex_multi_skill_routers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-multi-skill-router")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--intent", default="plan")
    parser.add_argument("--task-text", default="Route the next safe HEX-CORTEX memory-first improvement to the best active skill.")
    parser.add_argument("--requested-domain")
    parser.add_argument("--requested-skill-key")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_multi_skill_routers(args.profile / CORTEX_MULTI_SKILL_ROUTER_FILENAME)
    else:
        payload = build_cortex_multi_skill_router(
            args.profile,
            intent=args.intent,
            task_text=args.task_text,
            requested_domain=args.requested_domain,
            requested_skill_key=args.requested_skill_key,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
