from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_latent_world_model_simulation_contract import CORTEX_LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME
from hex_cortex.memory.cortex_latent_world_model_simulation_contract import build_cortex_latent_world_model_simulation_contract
from hex_cortex.memory.cortex_latent_world_model_simulation_contract import summarize_cortex_latent_world_model_simulation_contracts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-latent-world-model-simulation-contract")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_latent_world_model_simulation_contracts(args.profile / CORTEX_LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME)
    else:
        payload = build_cortex_latent_world_model_simulation_contract(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
