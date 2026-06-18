from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_interactive_cockpit_shell import CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME
from hex_cortex.memory.cortex_interactive_cockpit_shell import build_cortex_interactive_cockpit_shell
from hex_cortex.memory.cortex_interactive_cockpit_shell import summarize_cortex_interactive_cockpit_shells


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-interactive-cockpit-shell")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--data-api-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_interactive_cockpit_shells(args.profile / CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME)
    else:
        payload = build_cortex_interactive_cockpit_shell(
            args.profile,
            output_dir=args.output_dir,
            data_api_path=args.data_api_path,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
