from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_first_local_model_dry_run import CORTEX_FIRST_LOCAL_MODEL_DRY_RUN_FILENAME
from hex_cortex.memory.cortex_first_local_model_dry_run import build_cortex_first_local_model_dry_run
from hex_cortex.memory.cortex_first_local_model_dry_run import summarize_cortex_first_local_model_dry_runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-first-local-model-dry-run")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--task-text", default="Use the local compact expert contract to produce advisory planning output only.")
    parser.add_argument("--selected-skill-key", default=None)
    parser.add_argument("--backend-kind", default="mock")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_first_local_model_dry_runs(args.profile / CORTEX_FIRST_LOCAL_MODEL_DRY_RUN_FILENAME)
    else:
        payload = build_cortex_first_local_model_dry_run(
            args.profile,
            task_text=args.task_text,
            selected_skill_key=args.selected_skill_key,
            backend_kind=args.backend_kind,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
