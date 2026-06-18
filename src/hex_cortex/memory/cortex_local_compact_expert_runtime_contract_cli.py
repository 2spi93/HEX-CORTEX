from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_local_compact_expert_runtime_contract import CORTEX_LOCAL_COMPACT_EXPERT_RUNTIME_CONTRACT_FILENAME
from hex_cortex.memory.cortex_local_compact_expert_runtime_contract import build_cortex_local_compact_expert_runtime_contract
from hex_cortex.memory.cortex_local_compact_expert_runtime_contract import summarize_cortex_local_compact_expert_runtime_contracts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-local-compact-expert-runtime-contract")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_local_compact_expert_runtime_contracts(args.profile / CORTEX_LOCAL_COMPACT_EXPERT_RUNTIME_CONTRACT_FILENAME)
    else:
        payload = build_cortex_local_compact_expert_runtime_contract(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
