"""Model-free, evidence-honest release audit for HEX-CORTEX.

This checks wiring and immutable tracked files without running arbitrary
programs from the repository or contacting external providers. It never
certifies unexecuted cloud requests, interop against reference SDKs, or
untrusted code execution in a hardened OS sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_offline_readiness_v5 import offline_readiness

_COMPONENT_FILES = {
    "clock": "src/hex_cortex/core/cognitive_clock.py",
    "spine": "src/hex_cortex/spine/canonical_spine.py",
    "spine_persistence": "src/hex_cortex/spine/jsonl_store.py",
    "router": "src/hex_cortex/core/router.py",
    "workspace": "src/hex_cortex/core/workspace.py",
    "registry": "src/hex_cortex/core/cell_registry.py",
    "cognitive_circuit": "src/hex_cortex/core/cognitive_circuit_v1.py",
    "cognitive_replay_pipeline": "src/hex_cortex/core/cognitive_replay_pipeline_v11.py",
    "cloud_adapters": "src/hex_cortex/memory/cortex_cloud_brain_v5.py",
    "permissions": "src/hex_cortex/memory/cortex_local_harness_v2.py",
    "gateway": "src/hex_cortex/memory/cortex_gateway.py",
    "worktree": "src/hex_cortex/memory/cortex_worktree_executor.py",
    "durable_journal": "src/hex_cortex/memory/cortex_durable_jsonl_v7.py",
    "skill_candidate": "src/hex_cortex/memory/cortex_skill_candidate.py",
    "skill_review": "src/hex_cortex/memory/cortex_skill_evidence_review_v7.py",
    "mcp": "src/hex_cortex/memory/cortex_mcp_modern.py",
    "a2a": "src/hex_cortex/memory/cortex_a2a_local.py",
}
_DOCUMENTS = (
    "docs/PROJECT_ALIGNMENT.md",
    "docs/ORIGINAL_VISION_GAP_AUDIT_2026_10.md",
    "docs/CLOUD_FIRST_NO_BENCHMARK_V5.md",
    "docs/DURABLE_MEMORY_AND_LEARNING_V7.md",
    "docs/SAFE_HANDS_WORKTREE_V8.md",
    "docs/GATEWAY_EFFECT_RECOVERY_V9.md",
    "docs/RELEASE_ACCEPTANCE_V10.md",
)


def build_release_audit(root: Path) -> dict[str, object]:
    root = Path(root).resolve()
    items = {}
    for name, relative in _COMPONENT_FILES.items():
        path = root / relative
        # Avoid following symlinks to arbitrary private files.
        if path.is_symlink() or not path.is_file():
            items[name] = {"present": False}
            continue
        data = path.read_bytes()
        items[name] = {
            "present": True,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }
    documents = {
        relative: (root / relative).is_file() and not (root / relative).is_symlink()
        for relative in _DOCUMENTS
    }
    offline = offline_readiness()
    software_checks = {
        "python_package_manifest": (root / "pyproject.toml").is_file(),
        "all_required_components_present": all(
            item["present"] for item in items.values()
        ),
        "documentation_manifest_present": all(documents.values()),
        "offline_architecture_smoke_passed": offline["status"] == "passed",
        "no_local_llm_dependency": offline["local_model_required"] is False,
        "no_cloud_costs_in_smoke": (
            offline["remote_provider_called"] is False
            and offline["api_credentials_required"] is False
        ),
        "worktree_untrusted_python_denied": offline["checks"].get(
            "untrusted_python_execution_denied"
        ) is True,
        "durable_memory_smoke_passed": offline["checks"].get(
            "atomic_learning_memory_roundtrip"
        ) is True,
    }
    gates = {
        "core_offline_contracts": {
            "status": "verified_offline" if all(software_checks.values()) else "blocked",
            "evidence_type": "component_file_digests_plus_runtime_smoke",
        },
        "pytest_ruff_windows_linux": {
            "status": "requires_external_ci_evidence",
            "evidence_type": "git_workflow_run_or_operator_command",
        },
        "a2a_v1_reference_sdk_interoperability": {
            "status": "not_verified",
            "evidence_type": "external_official_sdk_client_required",
        },
        "mcp_2026_07_28_reference_sdk_interoperability": {
            "status": "not_verified",
            "evidence_type": "external_official_sdk_client_required",
        },
        "untrusted_python_os_isolation": {
            "status": "disabled_pending_separate_isolation",
            "evidence_type": "vm_or_verified_isolation_required",
        },
        "full_coding_task_with_independent_verification": {
            "status": "not_verified",
            "evidence_type": "real_independent_task_and_reviewer_required",
        },
        "crash_consistent_multi_file_recovery": {
            "status": "not_verified",
            "evidence_type": "transactional_storage_or_recovery_protocol_required",
        },
        "hosted_brain_live_api": {
            "status": "optional_not_verified",
            "evidence_type": "operator_credentials_consent_and_paid_service",
        },
        "cr_jepa_lora_or_local_model_benchmarks": {
            "status": "research_deferred_not_release_gate",
            "evidence_type": "none_required_for_offline_release",
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(items, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "report_type": "hex_cortex_release_evidence_v10",
        "project": "HEX-CORTEX",
        "architecture_mode": "local_control_plane_cloud_brain_optional",
        "core_offline_verified": all(software_checks.values()),
        "overall_release_certified": False,
        "production_ready": False,
        "software_checks": software_checks,
        "gates": gates,
        "components": items,
        "documents_present": documents,
        "component_manifest_sha256": fingerprint,
        "reported_tests_executed_by_this_command": False,
        "llm_benchmark_executed": False,
        "api_key_required": False,
        "server_deployed": False,
        "checkout_modified": False,
        "not_verified_warning": (
            "Real SDK interoperability, OS sandboxing, autonomous coding, "
            "multi-file crash recovery and live cloud provider access are not certified."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-release-audit")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    report = build_release_audit(args.project_root)
    print(json.dumps(report, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if report["core_offline_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
