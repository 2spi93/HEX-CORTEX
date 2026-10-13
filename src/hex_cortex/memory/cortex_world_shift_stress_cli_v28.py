"""Run bounded synthetic world regime stress without model/device access."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.memory.cortex_world_shift_stress_v28 import stress_world_bias_regimes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stress fitted world residual on regime shifts.")
    parser.add_argument("--approve-stress", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "models_called": False,
            "files_read": False, "files_written": False,
            "gpu_used": False, "device_polled": False,
        }))
        return 0
    result = stress_world_bias_regimes(approved=args.approve_stress)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
