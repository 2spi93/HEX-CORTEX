from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_frontier_oracle_fallback_contract import CORTEX_FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME
from hex_cortex.memory.cortex_frontier_oracle_fallback_contract import build_cortex_frontier_oracle_fallback_contract
from hex_cortex.memory.cortex_frontier_oracle_fallback_contract import summarize_cortex_frontier_oracle_fallback_contracts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-frontier-oracle-fallback-contract")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_frontier_oracle_fallback_contracts(args.profile / CORTEX_FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME)
    else:
        payload = build_cortex_frontier_oracle_fallback_contract(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
