from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.final_freeze_stamp import FINAL_FREEZE_STAMP_FILENAME
from hex_cortex.memory.final_freeze_stamp import build_final_freeze_stamp
from hex_cortex.memory.final_freeze_stamp import summarize_final_freeze_stamps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="final-freeze-stamp")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_final_freeze_stamps(args.profile / FINAL_FREEZE_STAMP_FILENAME)
    else:
        payload = build_final_freeze_stamp(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
