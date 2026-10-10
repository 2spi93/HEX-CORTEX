"""Live operator CLI for the model-free scientific evidence CognitiveCircuit.

The provided scientific corpus is local, explicitly approved and untrusted
until source bytes pass validation. No model calls, physical commands or file
writes. This CLI's source checks do NOT certify scientific truth.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cortex_scientific_evidence_circuit_v18 import (
    run_scientific_evidence_circuit,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal,
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.schemas import Task
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-science-circuit")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sources-dir", required=True, type=Path)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--domain", required=True,
                        choices=[d.value for d in KnowledgeDomain])
    parser.add_argument("--unit", required=True)
    parser.add_argument(
        "--approve-read", action="store_true",
        help="Explicit approval for local source reads and in-process evidence review",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_read:
        output = {
            "status": "blocked", "reason": "science_circuit_read_approval_required",
            "files_read": False, "model_used": False,
            "physical_action_authorized": False,
        }
        print(json.dumps(output, sort_keys=True, indent=2 if args.pretty else None))
        return 2
    try:
        records = load_local_scientific_manifest(args.manifest, approved=True)
    except LocalEvidenceRefusal as exc:
        output = {"status": "blocked", "reason": str(exc),
                  "model_used": False, "checkout_modified": False}
    else:
        item = Task(
            task_id="operator-scientific-knowledge",
            content=json.dumps({
                "claim_id": args.claim_id,
                "domain": args.domain,
                "result_unit": args.unit,
            }, sort_keys=True),
            domain_hints=[args.domain],
            risk=0.1, novelty=0.1, uncertainty=0.1,
            latency_budget_ms=1000,
        )
        verifier = LocalScientificEvidenceVerifier(
            args.sources_dir, operator_approved=True,
        )
        output, circuit = run_scientific_evidence_circuit(
            item, records=records, verify_source=verifier.verify_source,
            approved=True,
        )
        output["spine_verified"] = circuit.spine.verify_integrity().ok
        output["physical_action_authorized"] = False
    print(json.dumps(output, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if output["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
