from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_skill_guidance_renderer import CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
from hex_cortex.memory.cortex_skill_guidance_renderer import render_cortex_skill_guidance
from hex_cortex.memory.cortex_skill_guidance_renderer import summarize_cortex_skill_guidance_renderers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-skill-guidance-renderer")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_skill_guidance_renderers(
            args.profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
        )
    else:
        payload = render_cortex_skill_guidance(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
