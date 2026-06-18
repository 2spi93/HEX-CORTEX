from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_local_model_advice import CORTEX_LOCAL_MODEL_ADVICE_FILENAME
from hex_cortex.memory.cortex_local_model_advice import build_cortex_local_model_advice
from hex_cortex.memory.cortex_local_model_advice import summarize_cortex_local_model_advice


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-local-model-advice")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--task-text", default="Produce an optimized advisory plan for the next HEX-CORTEX local model integration step.")
    parser.add_argument("--selected-skill-key", default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_local_model_advice(args.profile / CORTEX_LOCAL_MODEL_ADVICE_FILENAME)
    else:
        payload = build_cortex_local_model_advice(
            args.profile,
            task_text=args.task_text,
            selected_skill_key=args.selected_skill_key,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
