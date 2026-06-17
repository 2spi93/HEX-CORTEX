from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_learning_event import CORTEX_LEARNING_EVENT_FILENAME
from hex_cortex.memory.cortex_learning_event import record_cortex_learning_event
from hex_cortex.memory.cortex_learning_event import summarize_cortex_learning_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-learning-event")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--outcome", default="success")
    parser.add_argument("--domain", default="coding")
    parser.add_argument("--scope", default="self")
    parser.add_argument("--source-ref", default=None)
    parser.add_argument("--problem", default="")
    parser.add_argument("--action-taken", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--lesson", default="")
    parser.add_argument("--reusable-rule", default="")
    parser.add_argument("--confidence", type=float, default=0.5)
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_learning_events(
            args.profile / CORTEX_LEARNING_EVENT_FILENAME
        )
    else:
        payload = record_cortex_learning_event(
            args.profile,
            outcome=args.outcome,
            domain=args.domain,
            scope=args.scope,
            source_ref=args.source_ref,
            problem=args.problem,
            action_taken=args.action_taken,
            result=args.result,
            lesson=args.lesson,
            reusable_rule=args.reusable_rule,
            confidence=args.confidence,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
