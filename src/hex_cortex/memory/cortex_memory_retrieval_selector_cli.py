from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_memory_retrieval_selector import CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME
from hex_cortex.memory.cortex_memory_retrieval_selector import build_cortex_memory_retrieval_selector
from hex_cortex.memory.cortex_memory_retrieval_selector import summarize_cortex_memory_retrieval_selectors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-memory-retrieval-selector")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_memory_retrieval_selectors(
            args.profile / CORTEX_MEMORY_RETRIEVAL_SELECTOR_FILENAME
        )
    else:
        payload = build_cortex_memory_retrieval_selector(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
