"""Offline scorer for paired baseline-vs-CORTEX outputs, no model inference."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from hex_cortex.core.cortex_paired_science_benchmark_v21 import (
    PairedEvaluation,
    evaluate_paired_model_amplification,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal, _read_regular_file,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-amplification-eval")
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_read:
        out = {"status": "blocked", "reason": "bench_operator_approval_required",
               "model_called": False, "files_read": False}
        print(json.dumps(out, indent=2 if args.pretty else None, sort_keys=True))
        return 2
    try:
        raw = _read_regular_file(args.pairs, max_bytes=262_144)
        info = PairedEvaluation.model_validate(json.loads(raw))
        out = evaluate_paired_model_amplification(info, operator_approved=True)
    except (ValidationError, ValueError, TypeError, UnicodeDecodeError,
            LocalEvidenceRefusal):
        out = {
            "status": "blocked", "reason": "bench_pairs_invalid_or_unreadable",
            "model_called": False, "checkout_modified": False,
            "physical_action_authorized": False,
        }
    print(json.dumps(out, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if out["status"] == "scored" else 2


if __name__ == "__main__":
    raise SystemExit(main())
