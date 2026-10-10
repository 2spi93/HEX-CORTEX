"""V20 read-only science decision CLI with independently pinned local sources.

The result is a provisional *bounded interval* judgment, never a calibrated
probability, universal scientific proof or permission to operate machinery.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from hex_cortex.core.cortex_scientific_corpus_v19 import (
    CorpusRefusal,
    corpus_status,
    evaluate_corpus_record,
    load_corpus_events,
)
from hex_cortex.core.cortex_scientific_decision_v20 import ScientificDecisionSpec
from hex_cortex.core.cortex_scientific_decision_circuit_v20 import (
    decision_task,
    run_scientific_decision_circuit,
)
from hex_cortex.core.cortex_scientific_knowledge_v16 import EvidenceQuery
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal,
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-science-decision")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--pin", required=True, help="Separately trusted SHA-256 head")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument(
        "--domain", required=True, choices=[d.value for d in KnowledgeDomain]
    )
    parser.add_argument("--unit", required=True)
    parser.add_argument("--relation", required=True, choices=["at_least", "at_most"])
    parser.add_argument("--threshold", required=True)
    parser.add_argument("--guard-band", default="0")
    parser.add_argument("--max-span")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    def emit(output: dict[str, object]) -> int:
        print(json.dumps(output, sort_keys=True, indent=2 if args.pretty else None))
        return 0 if output.get("status") == "provisionally_supported" else 2

    if not args.approve_read:
        return emit({
            "status": "blocked", "reason": "decision_operator_approval_required",
            "files_read": False, "model_used": False,
            "physical_action_authorized": False,
        })
    try:
        spec = ScientificDecisionSpec(
            query=EvidenceQuery(
                claim_id=args.claim_id, domain=KnowledgeDomain(args.domain),
                result_unit=args.unit,
            ),
            relation=args.relation, threshold=args.threshold,
            guard_band=args.guard_band, maximum_evidence_span=args.max_span,
        )
    except (ValidationError, ValueError, TypeError):
        return emit({
            "status": "blocked", "reason": "decision_policy_invalid",
            "model_used": False, "physical_action_authorized": False,
        })
    try:
        events = load_corpus_events(args.ledger, approved=True)
        policy = corpus_status(events, expected_head=args.pin)
        records = load_local_scientific_manifest(args.manifest, approved=True)
    except (CorpusRefusal, LocalEvidenceRefusal) as exc:
        return emit({
            "status": "blocked", "reason": str(exc),
            "model_used": False, "physical_action_authorized": False,
        })

    source = LocalScientificEvidenceVerifier(
        args.sources_dir, operator_approved=True,
    )

    def independently_verify(record):
        return evaluate_corpus_record(
            record,
            ledger_path=args.ledger,
            expected_head=args.pin,
            base_verifier=source.verify_source,
            approved=True,
        )

    result, circuit = run_scientific_decision_circuit(
        decision_task(spec, task_id="operator-scientific-decision"),
        spec=spec, records=records, verify_source=independently_verify,
        approved=True,
    )
    result["spine_verified"] = circuit.spine.verify_integrity().ok
    result["corpus_external_pin_verified"] = policy["external_pin_verified"]
    result["corpus_head_sha256"] = policy["head_sha256"]
    result["publisher_authenticity_verified"] = False
    result["scientific_truth_certified"] = False
    result["physical_action_authorized"] = False
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
