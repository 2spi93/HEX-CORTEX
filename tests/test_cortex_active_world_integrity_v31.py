"""Inspect true on-disk active-checkpoint evidence without loading torch/GPU."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_active_world_integrity_cli_v31 import main
from hex_cortex.memory.cortex_active_world_integrity_v31 import (
    audit_active_compact_integrity,
)
from hex_cortex.memory.cortex_observed_transition_dataset import (
    build_transition_dataset_manifest,
)


def _hash(v: object) -> str:
    return hashlib.sha256(json.dumps(
        v, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def _row(i: int, split: str) -> dict:
    encoder = _hash("encoder")
    result = {
        "record_type": "observed_transition_v1",
        "sample_id": f"sample-{i}",
        "split": split,
        "domain": "real_domain_operator_claim_unverified",
        "current_image_ref": f"i{i}.png",
        "next_image_ref": f"j{i}.png",
        "current_image_hash": _hash(f"current-{i}"),
        "next_image_hash": _hash(f"next-{i}"),
        "action_hash": _hash([0.1]),
        "current_latent_hash": _hash(f"latent-{i}"),
        "next_latent_hash": _hash(f"target-{i}"),
        "encoder": {"descriptor_hash": encoder, "latent_dim": 2},
        "action_schema": ["control"],
        "action_values": [0.1],
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
    }
    result["record_hash"] = _hash(result)
    result["next_action"] = "append_transition_record"
    return result


def _build_fixture(root: Path) -> Path:
    state = root / ".hex-cortex" / "world-model"
    (state / "candidate").mkdir(parents=True)
    (state / "registry").mkdir(parents=True)
    rows = [
        _row(0, "train"), _row(1, "train"), _row(2, "train"),
        _row(3, "validation"), _row(4, "test"), _row(5, "test"),
    ]
    (state / "transitions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
    )
    manifest = build_transition_dataset_manifest(rows, min_train=2, min_validation=1)
    assert manifest["manifest_allowed"] is True
    (state / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    weights = b"standin-weights-not-validated-safetensors"
    (state / "candidate" / "predictor.safetensors").write_bytes(weights)
    weight_sha = hashlib.sha256(weights).hexdigest()
    candidate = {
        "candidate_type": "compact_world_model_candidate_v1",
        "status": "trained",
        "promotion_allowed": True,
        "manifest_hash": manifest["manifest_hash"],
        "encoder_descriptor_hash": manifest["encoder_descriptor_hash"],
        "weights_file": "predictor.safetensors",
        "weights_hash": weight_sha,
    }
    candidate["candidate_hash"] = _hash(candidate)
    (state / "candidate" / "candidate.json").write_text(
        json.dumps(candidate), encoding="utf-8",
    )
    (state / "registry" / "active_predictor.safetensors").write_bytes(weights)
    promoted = dict(candidate)
    promoted.update({
        "weights_file": "active_predictor.safetensors",
        "promoted": True,
        "promotion_receipt_hash": _hash({
            "candidate_hash": candidate["candidate_hash"],
            "weights_hash": weight_sha,
        }),
    })
    (state / "registry" / "active_candidate.json").write_text(
        json.dumps(promoted), encoding="utf-8",
    )
    active = {
        "registry_type": "active_compact_world_model_v1",
        "candidate_file": "active_candidate.json",
        "weights_file": "active_predictor.safetensors",
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": weight_sha,
        "encoder_descriptor_hash": manifest["encoder_descriptor_hash"],
        "promotion_receipt_hash": promoted["promotion_receipt_hash"],
    }
    active["registry_hash"] = _hash(active)
    (state / "registry" / "active.json").write_text(
        json.dumps(active), encoding="utf-8",
    )
    return state


def test_deep_disk_verification_does_not_claim_real_world_or_inference(
    tmp_path: Path,
) -> None:
    _build_fixture(tmp_path)
    report = audit_active_compact_integrity(project_root=tmp_path, approved=True)
    assert report["status"] == "integrity_verified_on_disk"
    assert report["integrity_ok"] is True
    assert report["candidate_weights_sha256_verified"] is True
    assert report["active_weights_sha256_verified"] is True
    assert report["transition_record_count"] == 6
    assert report["split_counts"] == {"train": 3, "validation": 1, "test": 2}
    assert report["independent_dataset_attested"] is False
    assert report["model_inference_executed"] is False
    assert report["gpu_used"] is False
    assert report["files_written"] is False
    assert "environment_and_episode_independence_not_attested_by_v1_dataset" in report["warnings"]


def test_tampering_actual_active_weights_is_detected(tmp_path: Path) -> None:
    state = _build_fixture(tmp_path)
    (state / "registry" / "active_predictor.safetensors").write_bytes(b"corrupted")
    report = audit_active_compact_integrity(project_root=tmp_path, approved=True)
    assert report["integrity_ok"] is False
    assert "active_weights_hash_mismatch" in report["blockers"]
    assert report["active_weights_sha256_verified"] is False


def test_changed_transition_blocked_by_record_digest(tmp_path: Path) -> None:
    state = _build_fixture(tmp_path)
    file = state / "transitions.jsonl"
    lines = file.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["current_image_hash"] = _hash("fabricated-image")
    lines[0] = json.dumps(obj)
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = audit_active_compact_integrity(project_root=tmp_path, approved=True)
    assert report["integrity_ok"] is False
    assert "record_content_hash_mismatch" in report["blockers"]


def test_exact_image_train_test_overlap_is_not_independent(tmp_path: Path) -> None:
    state = _build_fixture(tmp_path)
    file = state / "transitions.jsonl"
    records = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    records[4]["current_image_hash"] = records[0]["current_image_hash"]
    for row in records:
        row["record_hash"] = _hash({
            k: v for k, v in row.items() if k not in ("record_hash", "next_action")
        })
    file.write_text(
        "".join(json.dumps(row) + "\n" for row in records),
        encoding="utf-8",
    )
    manifest = build_transition_dataset_manifest(records, min_train=2, min_validation=1)
    (state / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = audit_active_compact_integrity(project_root=tmp_path, approved=True)
    assert report["integrity_ok"] is False
    assert report["exact_cross_split_image_overlap_count"] >= 1
    assert "exact_image_overlap_between_splits" in report["blockers"]


def test_manually_modified_registry_and_candidate_detected(tmp_path: Path) -> None:
    state = _build_fixture(tmp_path)
    path = state / "registry" / "active_candidate.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result["encoder_descriptor_hash"] = "f" * 64
    path.write_text(json.dumps(result), encoding="utf-8")
    report = audit_active_compact_integrity(project_root=tmp_path, approved=True)
    assert "active_candidate_source_data_mismatch" in report["blockers"]


def test_explicit_file_permission_and_cli_dry_run(tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _build_fixture(tmp_path)
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(["--project-root", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["files_read"] is False
    assert main(["--project-root", str(tmp_path), "--approve-read"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "integrity_verified_on_disk"
    assert data["model_inference_executed"] is False



def test_active_cpu_smoke_requires_separate_inference_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from hex_cortex.memory.cortex_active_world_cpu_smoke_cli_v31 import main as smoke

    assert smoke(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["model_forward_calls"] == 0
    assert smoke(["--project-root", str(tmp_path), "--approve-read"]) == 2
    assert json.loads(capsys.readouterr().out)["model_forward_calls"] == 0


def test_actual_active_safetensors_cpu_forward_proves_only_runtime(
    tmp_path: Path,
) -> None:
    torch = pytest.importorskip("torch")
    safetensors = pytest.importorskip("safetensors.torch")
    from hex_cortex.memory.cortex_compact_world_model import _build_model
    from hex_cortex.memory.cortex_active_world_cpu_smoke_v31 import (
        run_active_world_cpu_smoke,
    )

    state = _build_fixture(tmp_path)
    model = _build_model(torch, latent_dim=2, action_dim=1, hidden_dim=8)
    with torch.no_grad():
        for p in model.parameters():
            p.zero_()
    weights = state / "candidate" / "predictor.safetensors"
    safetensors.save_file(model.state_dict(), str(weights))
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    candidate_file = state / "candidate" / "candidate.json"
    candidate = json.loads(candidate_file.read_text(encoding="utf-8"))
    candidate["weights_hash"] = digest
    candidate["config"] = {
        "architecture": "residual_mlp_v1",
        "latent_dim": 2, "action_dim": 1, "hidden_dim": 8,
    }
    candidate["candidate_hash"] = _hash({
        k: v for k, v in candidate.items() if k != "candidate_hash"
    })
    candidate_file.write_text(json.dumps(candidate), encoding="utf-8")
    active_weights = state / "registry" / "active_predictor.safetensors"
    active_weights.write_bytes(weights.read_bytes())
    promoted = dict(candidate)
    promoted["weights_file"] = "active_predictor.safetensors"
    promoted["promoted"] = True
    promoted["promotion_receipt_hash"] = _hash({
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": digest,
    })
    (state / "registry" / "active_candidate.json").write_text(
        json.dumps(promoted), encoding="utf-8",
    )
    active_file = state / "registry" / "active.json"
    active = json.loads(active_file.read_text(encoding="utf-8"))
    active["candidate_hash"] = candidate["candidate_hash"]
    active["weights_hash"] = digest
    active["promotion_receipt_hash"] = promoted["promotion_receipt_hash"]
    active["registry_hash"] = _hash({
        k: v for k, v in active.items() if k != "registry_hash"
    })
    active_file.write_text(json.dumps(active), encoding="utf-8")
    report = run_active_world_cpu_smoke(
        project_root=tmp_path, approved_read=True, approved_inference=True,
    )
    assert report["status"] == "cpu_forward_completed"
    assert report["model_forward_calls"] == 1
    assert report["weights_sha256_verified"] is True
    assert len(report["predicted_latent_sha256"]) == 64
    assert report["latent_dim"] == 2
    assert report["gpu_used"] is False
    assert report["real_world_prediction_tested"] is False
    assert report["files_written"] is False
    assert report["model_promoted"] is False
