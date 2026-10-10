"""Model-free architecture readiness smoke: zero API calls, zero benchmarks.

The checks verify wiring and fail-closed contracts, NOT production readiness.
Only the OS temporary directory is used; no project files are modified.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cortex_exact_math_v13 import calculate_exact
from hex_cortex.core.cortex_physics_cell_v14 import calculate_physics
from hex_cortex.core.cortex_chemistry_cell_v15 import run_chemistry
from datetime import date
import hashlib
from hex_cortex.core.cortex_scientific_evidence_circuit_v18 import run_scientific_evidence_circuit
from hex_cortex.core.cortex_scientific_corpus_v19 import (
    CorpusOperation,
    evaluate_corpus_record,
    new_corpus_event,
    record_fingerprint,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalScientificEvidenceVerifier,
    expected_scientific_source_bytes,
)
from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceKind,
    EvidenceQuery,
    EvidenceRecord,
    review_scientific_knowledge,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain
from hex_cortex.core.cortex_homeostasis_v13 import HealthObservation, homeostatic_review
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cognitive_replay_pipeline_v11 import run_circuit_replay_memory
from hex_cortex.core.universal_capabilities_v12 import (
    DeploymentTarget,
    RequestedOperation,
    plan_universal_task,
)
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task as CoreTask
from hex_cortex.memory.cortex_durable_jsonl_v7 import (
    atomic_jsonl_snapshot,
    exclusive_jsonl_writer,
)
from hex_cortex.memory.cortex_skill_evidence_review_v7 import review_skill_evidence
from hex_cortex.memory.cortex_worktree_executor import run_allowlisted_checks
from hex_cortex.memory.cortex_cloud_brain_v5 import CloudBrain
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
    build_readonly_harness,
)


def offline_readiness() -> dict[str, object]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="hex-cortex-offline-") as folder:
        root = Path(folder)
        (root / "README.md").write_text("model-free smoke only", encoding="utf-8")
        harness = build_readonly_harness(root, session_id="offline-readiness")
        denied = run_clocked_local_task(
            harness,
            Task("read-denied", "repo_read", "Do not read", "repo_manifest"),
            approved=False,
        )
        checks["unapproved_tool_denied"] = (
            denied["status"] == "blocked" and denied["reason"] == "tool_not_authorized"
        )
        approved = run_clocked_local_task(
            harness,
            Task("read-approved", "repo_read", "Inventory only", "repo_manifest"),
            approved=True,
        )
        checks["approved_read_only_manifest"] = (
            approved["status"] == "complete"
            and approved["tool_result"] == {
                "project_id": "HEX-CORTEX", "manifest": ["README.md"]
            }
        )
        checks["canonical_spine_integrity"] = harness.verify_replay()
        model_harness = LocalHarness(
            Session("model-free", root),
            grants=frozenset({Capability.CALL_MODEL}),
            budget=Budget(max_model_calls=1, max_tool_calls=0),
        )
        calls: list[str] = []

        def fake_brain(model: str, task: Task) -> str:
            calls.append(model)
            return "simulated answer"

        decision = run_clocked_local_task(
            model_harness, Task("mock", "coding", "Simulated input"),
            models=["fake-provider"], brain=fake_brain, approved=True,
        )
        checks["provider_independent_clock"] = (
            decision["status"] == "complete"
            and decision["canonical_spine_verified"] is True
            and calls == ["fake-provider"]
        )
        checks["redacted_receipts"] = (
            "Simulated input" not in json.dumps(model_harness.receipts)
            and "simulated answer" not in json.dumps(model_harness.receipts)
            and model_harness.verify_replay()
        )
    # Original cortex backbone: real deterministic Router + Registry +
    # GlobalWorkspace + CognitiveClock + CanonicalSpine, no model or network.
    registry = CellRegistry([
        CellSpec(cell_id="logic", role=CellRole.LOGIC, domains=["coding"]),
    ])
    circuit = CognitiveCircuit(registry)
    task = CoreTask(
        task_id="model-free-circuit", content="restricted deterministic test",
        domain_hints=["coding"], risk=0.1, novelty=0.1, uncertainty=0.1,
    )
    result = circuit.run(
        task, approved=True,
        cell_handler=lambda cell_id, core_task: CellResult(
            cell_id=cell_id, task_id=core_task.task_id,
            confidence=0.7, uncertainty=0.3,
            evidence_refs=["offline:deterministic-fixture"],
        ),
        verify_evidence=lambda evidence: evidence.evidence_refs == [
            "offline:deterministic-fixture"
        ],
    )
    checks["original_cortex_integrated_circuit"] = (
        result["status"] == "verified"
        and result["model_used"] is False
        and result["spine_verified"] is True
        and result["checkout_modified"] is False
    )
    followup = run_circuit_replay_memory(
        circuit,
        CoreTask(
            task_id="model-free-replay", content="synthetic regression fixture",
            domain_hints=["coding"], risk=0.1, novelty=0.1, uncertainty=0.1,
        ),
        approved=True,
        cell_handler=lambda cell_id, task: CellResult(
            cell_id=cell_id, task_id=task.task_id, confidence=0.7,
            uncertainty=0.3, evidence_refs=["fixture:checked"],
        ),
        verify_evidence=lambda candidate: candidate.evidence_refs == ["fixture:checked"],
    )
    checks["cell_to_spine_to_replay_memory_proposal"] = (
        followup.status == "memory_proposed_not_promoted"
        and followup.spine_verified
        and followup.memory_proposal_sha256 is not None
        and followup.skill_promoted is False
        and followup.memory_persisted is False
    )
    # A real filesystem transaction is tested in the disposable OS temp root.
    with tempfile.TemporaryDirectory(prefix="hex-cortex-memory-v7-") as folder:
        path = Path(folder) / "journal.jsonl"
        with exclusive_jsonl_writer(path):
            atomic_jsonl_snapshot(path, ['{"safe":true}'])
        checks["atomic_learning_memory_roundtrip"] = (
            path.read_text(encoding="utf-8") == '{"safe":true}\n'
            and not path.with_name(path.name + ".write-lock").exists()
        )
        review = review_skill_evidence(
            Path(folder) / "uncreated-profile",
            candidate_hash="a" * 64,
            operator_approved=False,
        )
        checks["unapproved_learning_review_denied"] = (
            review["status"] == "blocked"
            and review["skill_promoted"] is False
            and review["skill_activated"] is False
        )
    # The read-only smoke actively verifies generated-code execution is
    # blocked before reaching Python/pytest, even with generic approval.
    with tempfile.TemporaryDirectory(prefix="hex-cortex-hands-v8-") as folder:
        worktree = Path(folder)
        (worktree / ".git").write_text(
            "gitdir: /fake/local/worktrees/test\\n", encoding="utf-8"
        )
        denied_tests = run_allowlisted_checks(
            worktree_path=worktree, check_ids=["pytest"],
            operator_approved=True,
        )
        checks["untrusted_python_execution_denied"] = (
            denied_tests["status"] == "blocked"
            and denied_tests["blockers"] == ["untrusted_pytest_requires_os_sandbox"]
            and denied_tests["execution_performed"] is False
        )
    # Cross-domain V12: neither scientific claims nor physical actions
    # may be marked as operational by a mere declarative capability.
    scientific = plan_universal_task(
        CoreTask(
            task_id="cross-domain-science", content="fixture only",
            domain_hints=["chemistry", "materials"],
        ),
        operator_approved=True,
    )
    drone = plan_universal_task(
        CoreTask(
            task_id="physical-safety", content="fixture only",
            domain_hints=["aerospace", "robotics"],
        ),
        target=DeploymentTarget.DRONE,
        operation=RequestedOperation.ACTUATE,
        operator_approved=True,
    )
    checks["universal_science_contract_without_fake_expertise"] = (
        scientific["status"] == "advisory_only"
        and "molecular_chemistry" in scientific["matched_capability_ids"]
        and scientific["calculation_executed"] is False
    )
    checks["physical_actuation_denied_even_with_approval"] = (
        drone["status"] == "blocked"
        and drone["physical_actuation_allowed"] is False
        and drone["physical_actuation_performed"] is False
    )
    # V13: the first operational mathematical organ performs an exact
    # rational computation, and a bio-inspired feedback advisor quarantines
    # corrupt state. Neither system calls a model or physical device.
    exact = calculate_exact("1 / 3 + 1 / 6", approved=True)
    checks["independently_checked_exact_math"] = (
        exact["status"] == "verified_exact_arithmetic"
        and exact["numerator"] == 1
        and exact["denominator"] == 2
        and exact["independent_traversal_agrees"] is True
    )
    feedback = homeostatic_review(HealthObservation(
        cell_id="simulated-cell", error_rate=0.0, latency_ratio=0.1,
        consecutive_failures=0, spine_integrity_ok=False,
    ))
    checks["homeostatic_integrity_quarantine_advisory"] = (
        feedback["advisory_state"] == "quarantined"
        and feedback["registry_mutated"] is False
        and feedback["physical_actuation_allowed"] is False
    )
    physical = calculate_physics(
        "force",
        {
            "mass": {"value": "3", "unit": "kg"},
            "acceleration": {"value": "2/3", "unit": "m/s^2"},
        },
        approved=True,
    )
    unsafe_units = calculate_physics(
        "force",
        {
            "mass": {"value": "3", "unit": "m"},
            "acceleration": {"value": "2", "unit": "m/s^2"},
        },
        approved=True,
    )
    checks["physics_si_exact_laws_and_unit_safety"] = (
        physical["status"] == "verified_classical_formula"
        and physical["numerator"] == 2
        and physical["unit"] == "N"
        and physical["si_dimensions"] == [1, 1, -2, 0, 0, 0, 0]
        and unsafe_units["status"] == "blocked"
        and unsafe_units["calculation_performed"] is False
        and physical["hardware_actuation_allowed"] is False
    )
    # V15: a true bounded stoichiometric mole simulation, with exact
    # atom inventories and fixed rounded-weight mass conservation.
    chemistry = run_chemistry(
        ["H2", "O2"], ["H2O"],
        amounts_mol={"H2": "3", "O2": "1"}, approved=True,
    )
    chemistry_sim = chemistry.get("simulation") or {}
    invalid_reaction = run_chemistry(["O2"], ["CO2"], approved=True)
    checks["chemistry_exact_atoms_and_mass_conservation"] = (
        chemistry["status"] == "verified_idealized_stoichiometry"
        and chemistry_sim.get("products_mol") == {"H2O": "2"}
        and chemistry_sim.get("unreacted_mol") == {"H2": "1", "O2": "0"}
        and chemistry_sim.get("element_inventory_conserved") is True
        and chemistry_sim.get("mass_conserved_under_fixed_rounded_weights") is True
        and chemistry["laboratory_action_performed"] is False
        and invalid_reaction["status"] == "blocked"
    )
    # V16 uses two synthetic host-authenticated SOURCE FIXTURES;
    # agreement is NOT independent external certification or scientific truth.
    def fixture(source: str, value: str) -> EvidenceRecord:
        return EvidenceRecord(
            claim_id="source_comparison_fixture",
            domain=KnowledgeDomain.PHYSICS,
            value=value,
            unit="m/s",
            absolute_uncertainty="1",
            kind=EvidenceKind.MEASUREMENT,
            source_id=source,
            source_uri="https://example.org/synthetic/" + source,
            source_version="test.1",
            source_digest_sha256=hashlib.sha256(source.encode()).hexdigest(),
            source_license="synthetic-test-fixture",
            published_on=date(2026, 10, 10),
        )

    source_query = EvidenceQuery(
        claim_id="source_comparison_fixture",
        domain=KnowledgeDomain.PHYSICS,
        result_unit="m/s",
    )
    source_a = fixture("fixture.a", "100")
    source_b = fixture("fixture.b", "110")
    disagreement = review_scientific_knowledge(
        source_query, [source_a, source_b],
        operator_approved=True,
        verify_source=lambda _: True,  # explicitly synthetic trusted-host stub
    )
    verifier_absent = review_scientific_knowledge(
        source_query, [source_a, source_b],
        operator_approved=True,
    )
    checks["scientific_provenance_conflict_detected"] = (
        disagreement["status"] == "conflict"
        and disagreement["truth_certified"] is False
        and disagreement["physical_action_authorized"] is False
    )
    checks["unverified_scientific_source_denied"] = (
        verifier_absent["status"] == "blocked"
        and verifier_absent["reason"] == "trusted_source_verifier_required"
    )
    # V17: verify real source BYTES in the disposable temp directory,
    # not a mocked true callback. No external publisher authentication.
    with tempfile.TemporaryDirectory(prefix="hex-cortex-sources-v17-") as folder:
        source_root = Path(folder)
        witnesses: list[EvidenceRecord] = []
        for sid in ("local.alpha", "local.beta"):
            prototype = EvidenceRecord(
                claim_id="offline_bytes_fixture",
                domain=KnowledgeDomain.PHYSICS,
                value="100", unit="m/s", absolute_uncertainty="1",
                kind=EvidenceKind.MEASUREMENT,
                source_id=sid,
                source_uri="https://example.org/synthetic/" + sid,
                source_version="fixture.v1",
                source_digest_sha256="0" * 64,
                source_license="synthetic-test-only",
                published_on=date(2026, 10, 10),
            )
            witness_bytes = expected_scientific_source_bytes(prototype)
            (source_root / (sid + ".json")).write_bytes(witness_bytes)
            witnesses.append(prototype.model_copy(update={
                "source_digest_sha256": hashlib.sha256(witness_bytes).hexdigest()
            }))
        verifier = LocalScientificEvidenceVerifier(
            source_root, operator_approved=True,
        )
        source_check = review_scientific_knowledge(
            EvidenceQuery(
                claim_id="offline_bytes_fixture",
                domain=KnowledgeDomain.PHYSICS,
                result_unit="m/s",
            ),
            witnesses, operator_approved=True,
            verify_source=verifier.verify_source,
        )
        routed, scientific_circuit = run_scientific_evidence_circuit(
            CoreTask(
                task_id="source-backed-science-v18",
                content=json.dumps({
                    "claim_id": "offline_bytes_fixture",
                    "domain": "physics",
                    "result_unit": "m/s",
                }),
                domain_hints=["physics"],
                risk=0.1, novelty=0.1, uncertainty=0.1,
            ),
            records=witnesses, verify_source=verifier.verify_source,
            approved=True,
        )
        checks["scientific_sources_routed_to_verified_cognitive_spine"] = (
            routed["status"] == "verified"
            and routed["verified_cell_count"] == 1
            and scientific_circuit.spine.verify_integrity().ok
            and routed["model_used"] is False
            and routed["checkout_modified"] is False
        )
        # V19 governance: real source bytes remain valid after revocation,
        # but their independently pinned admissions must be current.
        admitted = []
        for witness in witnesses:
            admitted.append(new_corpus_event(
                admitted,
                operation=CorpusOperation.ADMIT,
                source_id=witness.source_id, revision=1,
                record_sha256=record_fingerprint(witness),
            ))
        ledger = source_root / "corpus-ledger.json"
        ledger.write_text(
            json.dumps([row.model_dump(mode="json") for row in admitted]),
            encoding="utf-8",
        )
        first_pin = admitted[-1].event_hash
        admitted_before_revocation = all(
            evaluate_corpus_record(
                record, ledger_path=ledger, expected_head=first_pin,
                base_verifier=verifier.verify_source, approved=True,
            )
            for record in witnesses
        )
        revoked = new_corpus_event(
            admitted, operation=CorpusOperation.REVOKE,
            source_id=witnesses[1].source_id, revision=1,
            record_sha256=record_fingerprint(witnesses[1]),
        )
        ledger.write_text(
            json.dumps([row.model_dump(mode="json")
                        for row in [*admitted, revoked]]),
            encoding="utf-8",
        )
        checks["scientific_corpus_revocation_blocks_valid_source"] = (
            admitted_before_revocation
            and verifier.verify_source(witnesses[1])
            and not evaluate_corpus_record(
                witnesses[1], ledger_path=ledger,
                expected_head=revoked.event_hash,
                base_verifier=verifier.verify_source, approved=True,
            )
        )
        checks["scientific_corpus_external_pin_denies_history_rollback"] = (
            not evaluate_corpus_record(
                witnesses[0], ledger_path=ledger, expected_head=first_pin,
                base_verifier=verifier.verify_source, approved=True,
            )
        )
        (source_root / "local.beta.json").write_bytes(b"corrupt")
        source_tamper_denied = not verifier.verify_source(witnesses[1])
        checks["local_scientific_source_byte_integrity"] = (
            source_check["status"] == "consistent_evidence_not_certified"
            and source_check["truth_certified"] is False
            and source_tamper_denied
        )
    # Constructors only; neither provider is contacted or authenticated.
    checks["cloud_adapter_interfaces"] = (
        CloudBrain("openai").api_key_variable == "OPENAI_API_KEY"
        and CloudBrain("anthropic").api_key_variable == "ANTHROPIC_API_KEY"
    )
    return {
        "check_type": "hex_cortex_offline_architecture_smoke_v5",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "local_model_required": False,
        "benchmark_executed": False,
        "remote_provider_called": False,
        "api_credentials_required": False,
        "checkout_modified": False,
        "production_ready": False,
        "reason_production_not_certified": (
            "offline wiring and unit tests cannot certify remote provider access "
            "or end-to-end autonomous project execution"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-readiness")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    report = offline_readiness()
    print(json.dumps(report, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
