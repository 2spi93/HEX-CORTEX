from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME
from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import build_cortex_interactive_cockpit_ux_polish
from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import summarize_cortex_interactive_cockpit_ux_polishes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-interactive-cockpit-ux-polish")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--index-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_interactive_cockpit_ux_polishes(args.profile / CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME)
    else:
        payload = build_cortex_interactive_cockpit_ux_polish(args.profile, index_path=args.index_path)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
