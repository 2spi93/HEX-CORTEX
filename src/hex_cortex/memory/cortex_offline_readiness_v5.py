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
