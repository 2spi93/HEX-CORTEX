"""Operator-facing governed scientific circuit: externally pinned source ledger.

The pin must come from a separate trusted record, NOT be read from the
editable ledger. This command does not change corpus data or allow actuation.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cortex_scientific_corpus_v19 import (
    CorpusRefusal,
    corpus_status,
    evaluate_corpus_record,
    load_corpus_events,
)
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
    parser = argparse.ArgumentParser(prog="hexcortex-science-governed")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--pin", required=True, help="Trusted SHA-256 head supplied separately")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--domain", required=True,
                        choices=[item.value for item in KnowledgeDomain])
    parser.add_argument("--unit", required=True)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_read:
        output = {"status": "blocked", "reason": "corpus_operator_read_approval_required",
                  "files_read": False, "model_used": False,
                  "physical_action_authorized": False}
        print(json.dumps(output, sort_keys=True, indent=2 if args.pretty else None))
        return 2

    try:
        # Preflight all ledger events and externally pinned head.
        events = load_corpus_events(args.ledger, approved=True)
        policy = corpus_status(events, expected_head=args.pin)
        records = load_local_scientific_manifest(args.manifest, approved=True)
    except (CorpusRefusal, LocalEvidenceRefusal) as exc:
        output = {"status": "blocked", "reason": str(exc),
                  "model_used": False, "physical_action_authorized": False,
                  "checkout_modified": False}
    else:
        verifier = LocalScientificEvidenceVerifier(
            args.sources_dir, operator_approved=True,
        )

        def check_source(record):
            return evaluate_corpus_record(
                record, ledger_path=args.ledger, expected_head=args.pin,
                base_verifier=verifier.verify_source, approved=True,
            )

        task = Task(
            task_id="governed-scientific-knowledge",
            content=json.dumps({
                "claim_id": args.claim_id, "domain": args.domain,
                "result_unit": args.unit,
            }, sort_keys=True),
            domain_hints=[args.domain],
            risk=0.1, novelty=0.1, uncertainty=0.1,
        )
        output, circuit = run_scientific_evidence_circuit(
            task, records=records, verify_source=check_source, approved=True,
        )
        output["spine_verified"] = circuit.spine.verify_integrity().ok
        output["corpus_external_pin_verified"] = policy["external_pin_verified"]
        output["corpus_head_sha256"] = policy["head_sha256"]
        output["publisher_authenticity_verified"] = False
        output["scientific_truth_certified"] = False
        output["physical_action_authorized"] = False

    print(json.dumps(output, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if output["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
