from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_hypothesis_tree import CORTEX_HYPOTHESIS_TREE_FILENAME
from hex_cortex.memory.cortex_hypothesis_tree import build_cortex_hypothesis_tree
from hex_cortex.memory.cortex_hypothesis_tree import summarize_cortex_hypothesis_trees


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-hypothesis-tree")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_hypothesis_trees(args.profile / CORTEX_HYPOTHESIS_TREE_FILENAME)
    else:
        payload = build_cortex_hypothesis_tree(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
