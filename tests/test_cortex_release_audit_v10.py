"""Release evidence audit: offline, reproducible and not falsely certified."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_release_audit_v10 import build_release_audit, main


def test_repository_core_release_evidence_without_llm(capsys) -> None:
    repo = Path(__file__).resolve().parents[1]
    report = build_release_audit(repo)
    assert report["project"] == "HEX-CORTEX"
    assert report["core_offline_verified"] is True
    assert report["software_checks"]["offline_architecture_smoke_passed"] is True
    assert report["software_checks"]["durable_memory_smoke_passed"] is True
    assert report["software_checks"]["worktree_untrusted_python_denied"] is True
    assert report["gates"]["core_offline_contracts"]["status"] == "verified_offline"
    assert report["production_ready"] is False
    assert report["overall_release_certified"] is False
    assert report["server_deployed"] is False
    assert report["llm_benchmark_executed"] is False
    assert report["checkout_modified"] is False
    assert len(report["component_manifest_sha256"]) == 64
    assert main(["--project-root", str(repo)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["component_manifest_sha256"] == report["component_manifest_sha256"]


def test_unknown_checkout_cannot_claim_core_success(tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    report = build_release_audit(tmp_path)
    assert report["core_offline_verified"] is False
    assert report["software_checks"]["all_required_components_present"] is False
    assert report["overall_release_certified"] is False
    assert main(["--project-root", str(tmp_path), "--pretty"]) == 2
    assert json.loads(capsys.readouterr().out)["production_ready"] is False


def test_audit_maintains_explicit_unverified_external_gates() -> None:
    report = build_release_audit(Path(__file__).resolve().parents[1])
    gates = report["gates"]
    assert gates["hosted_brain_live_api"]["status"] == "optional_not_verified"
    assert gates["a2a_v1_reference_sdk_interoperability"]["status"] == "not_verified"
    assert gates["mcp_2026_07_28_reference_sdk_interoperability"]["status"] == "not_verified"
    assert gates["untrusted_python_os_isolation"]["status"] == "disabled_pending_separate_isolation"
    assert gates["cr_jepa_lora_or_local_model_benchmarks"]["status"] == "research_deferred_not_release_gate"


def test_manifest_is_stable_when_files_unchanged() -> None:
    repo = Path(__file__).resolve().parents[1]
    first = build_release_audit(repo)
    second = build_release_audit(repo)
    assert first["component_manifest_sha256"] == second["component_manifest_sha256"]
    assert all(row["present"] for row in first["components"].values())
    assert all(len(row["sha256"]) == 64 for row in first["components"].values())
