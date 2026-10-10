"""Model-free ChemistryCell CLI: idealized atom balance and molar simulation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.core.cortex_chemistry_cell_v15 import run_chemistry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hexcortex-chemistry",
        description="Exact atom balancing + idealized mole inventory simulation",
    )
    parser.add_argument("--reactant", action="append", required=True)
    parser.add_argument("--product", action="append", required=True)
    parser.add_argument(
        "--amount", action="append", metavar="FORMULA=MOLES",
        help="Exact rational mole amount of a reactant; one per reactant",
    )
    parser.add_argument(
        "--approve-simulate", action="store_true",
        help="Explicit approval for bounded calculation (no laboratory action)",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    inventory: dict[str, str] | None = None
    if args.amount is not None:
        inventory = {}
        for item in args.amount:
            if "=" not in item or len(item) > 144:
                parser.error("--amount requires FORMULA=MOLES")
            formula, quantity = item.split("=", 1)
            if not formula or not quantity or formula in inventory:
                parser.error("--amount must contain a distinct, nonempty formula and moles")
            inventory[formula] = quantity
    result = run_chemistry(
        args.reactant, args.product,
        amounts_mol=inventory, approved=args.approve_simulate,
    )
    print(json.dumps(result, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if result["status"] == "verified_idealized_stoichiometry" else 2


if __name__ == "__main__":
    raise SystemExit(main())
