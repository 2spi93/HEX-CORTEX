"""Explicit SI PhysicsCell CLI; no network, model or physical control."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.core.cortex_physics_cell_v14 import _LAWS, calculate_physics


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hexcortex-physics",
        description="Bounded, exact classical physics calculations in SI units",
    )
    parser.add_argument("--law", required=True, choices=sorted(_LAWS))
    for name, unit in (
        ("mass", "kg"), ("acceleration", "m/s^2"), ("speed", "m/s"),
        ("distance", "m"), ("duration", "s"), ("energy", "J"), ("volume", "m^3"),
    ):
        parser.add_argument(f"--{name}", help=f"Exact rational quantity in {unit}")
    parser.add_argument(
        "--approve-calculate", action="store_true",
        help="Explicit authorization to compute these user-provided quantities",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    expected, _unit = _LAWS[args.law]
    provided = {
        key: {"value": str(value), "unit": expected.get(key, "unsupported")}
        for key in ("mass", "acceleration", "speed", "distance",
                    "duration", "energy", "volume")
        if (value := getattr(args, key)) is not None
    }
    result = calculate_physics(
        args.law, provided, approved=args.approve_calculate,
    )
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["status"] == "verified_classical_formula" else 2


if __name__ == "__main__":
    raise SystemExit(main())
