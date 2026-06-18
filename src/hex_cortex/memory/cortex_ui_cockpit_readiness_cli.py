from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_ui_cockpit_readiness import CORTEX_UI_COCKPIT_READINESS_FILENAME
from hex_cortex.memory.cortex_ui_cockpit_readiness import build_cortex_ui_cockpit_readiness
from hex_cortex.memory.cortex_ui_cockpit_readiness import summarize_cortex_ui_cockpit_readiness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-ui-cockpit-readiness")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--ci-artifact-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_ui_cockpit_readiness(args.profile / CORTEX_UI_COCKPIT_READINESS_FILENAME)
    else:
        payload = build_cortex_ui_cockpit_readiness(args.profile, ci_artifact_path=args.ci_artifact_path)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
