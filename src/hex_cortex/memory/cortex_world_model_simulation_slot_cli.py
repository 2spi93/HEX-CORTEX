from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_world_model_simulation_slot import CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME
from hex_cortex.memory.cortex_world_model_simulation_slot import build_cortex_world_model_simulation_slot
from hex_cortex.memory.cortex_world_model_simulation_slot import summarize_cortex_world_model_simulation_slots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-world-model-simulation-slot")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_world_model_simulation_slots(args.profile / CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME)
    else:
        payload = build_cortex_world_model_simulation_slot(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
