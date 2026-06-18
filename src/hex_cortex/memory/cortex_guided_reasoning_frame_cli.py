from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_guided_reasoning_frame import CORTEX_GUIDED_REASONING_FRAME_FILENAME
from hex_cortex.memory.cortex_guided_reasoning_frame import build_cortex_guided_reasoning_frame
from hex_cortex.memory.cortex_guided_reasoning_frame import summarize_cortex_guided_reasoning_frames


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-guided-reasoning-frame")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_guided_reasoning_frames(
            args.profile / CORTEX_GUIDED_REASONING_FRAME_FILENAME
        )
    else:
        payload = build_cortex_guided_reasoning_frame(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
