from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_operational_audit import audit_screen_lab_policy_v2
from hex_cortex.memory.cortex_operational_audit import build_operational_audit
from hex_cortex.memory.cortex_operational_audit import write_operational_audit_receipt


def test_operational_audit_can_certify_complete_evidence(tmp_path: Path) -> None:
    state_root = tmp_path / ".hex-cortex"
    _write_active_world_model(state_root)
    _write_policy_candidate(state_root, promotion_allowed=True, promotion_blockers=[])
    _write_receipts(state_root)
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    secret_scan = tmp_path / ".github" / "workflows" / "secret-scan.yml"
    secret_scan.parent.mkdir(parents=True)
    secret_scan.write_text("name: secret scan\n", encoding="utf-8")

    payload = build_operational_audit(
        tmp_path,
        execute_network=False,
        filesystem_receipt=_filesystem_receipt(),
        runtime_receipt={
            "runtime_facts": {
                "runtime_orchestration_available": True,
                "local_model_runtime_available": True,
                "ollama_endpoint_configured": True,
                "llama_server_endpoint_configured": False,
            }
        },
        media_receipt={"healthy": True, "network_call_performed": True},
        research_receipt={"operational_ready": True, "network_call_performed": True},
        encoder_receipt={"runtime_ready": True, "network_call_performed": False},
        model_cache_present=True,
        runtime_fact_overrides={
            "hermes_adapter_available": True,
            "private_or_tunneled_transport_available": True,
        },
    )

    assert payload["code_ready"] is True
    assert payload["runtime_ready"] is True
    assert payload["models_ready"] is True
    assert payload["research_ready"] is True
    assert payload["media_ready"] is True
    assert payload["world_model_ready"] is True
    assert payload["policy_v2_ready"] is True
    assert payload["self_correction_ready"] is True
    assert payload["remote_api_ready"] is True
    assert payload["server_ready"] is True
    assert payload["security_ready"] is True
    assert payload["branch_ready"] is True
    assert payload["operational_ready"] is True
    assert payload["wiring"]["operational_ready"] is True
    assert len(payload["audit_hash"]) == 64
    assert payload["raw_secret_persisted"] is False


def test_operational_audit_stays_blocked_without_live_evidence(tmp_path: Path) -> None:
    payload = build_operational_audit(
        tmp_path,
        execute_network=False,
        filesystem_receipt={"runtime_facts": {}},
        runtime_receipt={"runtime_facts": {}},
        media_receipt={"healthy": False},
        research_receipt={"operational_ready": False},
        encoder_receipt={"runtime_ready": False},
        model_cache_present=False,
    )

    assert payload["branch_ready"] is False
    assert payload["operational_ready"] is False
    assert payload["research_ready"] is False
    assert payload["media_ready"] is False
    assert payload["policy_v2_ready"] is False
    assert payload["self_correction_ready"] is False
    assert payload["remote_api_ready"] is False
    assert payload["next_action"] == "run_searxng_live_citation_audit"


def test_policy_v2_clean_rejection_is_reviewable(tmp_path: Path) -> None:
    state_root = tmp_path / ".hex-cortex"
    _write_policy_candidate(
        state_root,
        promotion_allowed=False,
        promotion_blockers=["test_top1_action_accuracy_below_threshold"],
    )

    audit = audit_screen_lab_policy_v2(state_root)

    assert audit["heldout_evaluated"] is True
    assert audit["policy_gate_passed"] is False
    assert audit["promotion_allowed"] is False
    assert audit["clean_rejection"] is True
    assert audit["gate_ready"] is True


def test_operational_audit_receipt_is_written_without_secret(tmp_path: Path) -> None:
    payload = {
        "audit_type": "hex_cortex_operational_truth_v1",
        "audit_hash": "a" * 64,
        "raw_secret_persisted": False,
    }
    target = tmp_path / "receipts" / "operational-audit.json"

    receipt = write_operational_audit_receipt(target, payload)

    assert receipt["written"] is True
    assert receipt["raw_secret_persisted"] is False
    assert json.loads(target.read_text(encoding="utf-8"))["audit_hash"] == "a" * 64


def _filesystem_receipt() -> dict[str, object]:
    return {
        "runtime_facts": {
            "cli_entrypoint_available": True,
            "mcp_server_available": True,
            "claude_project_configured": True,
            "claude_runtime_available": True,
            "research_social_credentials_available": True,
            "server_federation_audit_available": True,
            "service_packaging_available": True,
            "hardware_adapter_available": True,
            "project_adapter_available": True,
        }
    }


def _write_active_world_model(state_root: Path) -> None:
    registry = state_root / "world-model" / "registry"
    registry.mkdir(parents=True)
    weights = registry / "active_predictor.safetensors"
    weights.write_bytes(b"deterministic-weights")
    weights_hash = hashlib.sha256(weights.read_bytes()).hexdigest()
    candidate = registry / "active_candidate.json"
    candidate.write_text(json.dumps({"candidate_hash": "candidate-hash"}), encoding="utf-8")
    active = {
        "registry_type": "active_compact_world_model_v1",
        "candidate_file": candidate.name,
        "weights_file": weights.name,
        "candidate_hash": "candidate-hash",
        "weights_hash": weights_hash,
    }
    (registry / "active.json").write_text(json.dumps(active), encoding="utf-8")


def _write_policy_candidate(
    state_root: Path,
    *,
    promotion_allowed: bool,
    promotion_blockers: list[str],
) -> None:
    candidate_dir = state_root / "screen-lab-policy-v2" / "candidate"
    candidate_dir.mkdir(parents=True)
    candidate = {
        "candidate_type": "action_discriminative_world_model_candidate_v2",
        "candidate_hash": "policy-candidate-hash",
        "policy_gate_passed": promotion_allowed,
        "promotion_allowed": promotion_allowed,
        "promotion_blockers": promotion_blockers,
        "metrics": {
            "top1_action_accuracy": 1.0 if promotion_allowed else 0.75,
            "positive_margin_rate": 1.0 if promotion_allowed else 0.75,
        },
    }
    (candidate_dir / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")


def _write_receipts(state_root: Path) -> None:
    receipt_path = state_root / "receipts" / "field-certification.jsonl"
    receipt_path.parent.mkdir(parents=True)
    rows = [
        {"receipt_type": "isolated_worktree_create_v1", "status": "created"},
        {"receipt_type": "reviewable_patch_apply_v1", "status": "applied"},
        {"receipt_type": "allowlisted_check_run_v1", "status": "passed"},
        {
            "evaluation_type": "self_correction_candidate_evaluation_v1",
            "status": "promotable",
        },
        {
            "receipt_type": "coding_model_execution_v1",
            "provider_id": "remote_api",
            "status": "completed",
            "model_call_performed": True,
            "raw_secret_persisted": False,
            "raw_response_persisted": False,
        },
        {"receipt_type": "secret_rotation_v1", "secret_id": "n8n", "status": "rotated"},
    ]
    receipt_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
