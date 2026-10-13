"""Math/physics/chemistry CognitiveCircuit CLI; no model, network or GPU."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.core.cortex_verified_science_circuit import (
    run_verified_science_circuit,
)

_EXAMPLES = {
    "mathematics": "127*413",
    "physics": json.dumps({
        "law": "force",
        "inputs": {
            "mass": {"value": "2", "unit": "kg"},
            "acceleration": {"value": "3", "unit": "m/s^2"},
        },
    }, sort_keys=True),
    "chemistry": json.dumps({
        "reactants": ["H2", "O2"], "products": ["H2O"]
    }, sort_keys=True),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify three existing scientific cells through the original cognitive circuit."
    )
    parser.add_argument("--domain", choices=list(_EXAMPLES), required=True)
    parser.add_argument("--task-id", default="science-demonstration")
    data = parser.add_mutually_exclusive_group(required=True)
    data.add_argument("--example", action="store_true")
    data.add_argument("--request")
    parser.add_argument("--approve-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "domain": args.domain,
            "model_called": False,
            "calculation_performed": False,
            "files_read": False,
            "files_written": False,
            "gpu_used": False,
        }, sort_keys=True))
        return 0
    request = _EXAMPLES[args.domain] if args.example else args.request
    try:
        report = run_verified_science_circuit(
            domain=args.domain, task_id=args.task_id, request=request,
            approved=args.approve_run,
        )
    except (ValueError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "verified_science_circuit" else 2


if __name__ == "__main__":
    raise SystemExit(main())
