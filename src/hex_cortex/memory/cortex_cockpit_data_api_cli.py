from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_cockpit_data_api import CORTEX_COCKPIT_DATA_API_FILENAME
from hex_cortex.memory.cortex_cockpit_data_api import build_cortex_cockpit_data_api
from hex_cortex.memory.cortex_cockpit_data_api import summarize_cortex_cockpit_data_apis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-cockpit-data-api")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--ci-artifact-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_cockpit_data_apis(args.profile / CORTEX_COCKPIT_DATA_API_FILENAME)
    else:
        payload = build_cortex_cockpit_data_api(
            args.profile,
            output_dir=args.output_dir,
            ci_artifact_path=args.ci_artifact_path,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
