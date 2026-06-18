from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_cockpit_live_refresh_filters_drilldown_plus import CORTEX_COCKPIT_LIVE_REFRESH_FILTERS_DRILLDOWN_PLUS_FILENAME
from hex_cortex.memory.cortex_cockpit_live_refresh_filters_drilldown_plus import build_cortex_cockpit_live_refresh_filters_drilldown_plus
from hex_cortex.memory.cortex_cockpit_live_refresh_filters_drilldown_plus import summarize_cortex_cockpit_live_refresh_filters_drilldown_plus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-cockpit-live-refresh-filters-drilldown-plus")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--index-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_cockpit_live_refresh_filters_drilldown_plus(args.profile / CORTEX_COCKPIT_LIVE_REFRESH_FILTERS_DRILLDOWN_PLUS_FILENAME)
    else:
        payload = build_cortex_cockpit_live_refresh_filters_drilldown_plus(args.profile, index_path=args.index_path)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
