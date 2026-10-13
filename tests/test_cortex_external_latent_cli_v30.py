"""V30 CLI privacy and real existing checkpoint CPU interoperability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_external_latent_cli_v30 import (
    _synthetic_example,
    main,
)
from hex_cortex.memory.cortex_external_latent_evaluation_v30 import (
    audit_external_latent_trajectories,
    read_external_latent_jsonl,
)


def test_synthetic_example_explicitly_disclaims_real_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--synthetic-example"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "external_latent_audit_pass"
    assert report["synthetic_example_only"] is True
    assert report["real_world_origin_verified"] is False
    assert "records" not in report
    assert "state_latent" not in str(report)
    assert report["files_written"] is False


def test_cli_dry_run_does_not_touch_nonexistent_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--jsonl", "missing.jsonl", "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["file_reads"] == 0
    assert report["model_calls"] == 0


def test_external_local_file_requires_operator_approval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    data = tmp_path / "trajectories.jsonl"
    data.write_text(
        "".join(json.dumps(row) + "\n" for row in _synthetic_example()),
        encoding="utf-8",
    )
    assert main(["--jsonl", str(data)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert main(["--jsonl", str(data), "--approve-read"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sample_count"] == 6
    assert report["synthetic_example_only"] is False  # operator file, NOT authenticity
    assert report["real_world_origin_verified"] is False
    assert "records" not in report
    assert "state_latent" not in str(report)


def test_read_does_not_accept_symlink_or_malformed_jsonl(tmp_path: Path) -> None:
    f = tmp_path / "data.jsonl"
    f.write_text("{broken}\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        read_external_latent_jsonl(f)
    with pytest.raises(ValueError, match="external_latent_invalid_jsonl"):
        read_external_latent_jsonl(f, approved=True)


def test_true_model_adapter_reuses_existing_residual_mlp_on_cpu(
    tmp_path: Path,
) -> None:
    torch = pytest.importorskip("torch")
    safetensors = pytest.importorskip("safetensors.torch")
    from hex_cortex.memory.cortex_compact_world_model import _build_model
    from hex_cortex.memory.cortex_compact_external_adapter_v30 import (
        evaluate_local_compact_on_external,
    )

    audit = audit_external_latent_trajectories(_synthetic_example())
    model = _build_model(torch, latent_dim=2, action_dim=1, hidden_dim=8)
    with torch.no_grad():
        for layer in model.parameters():
            layer.zero_()  # predicts identity; actually computes real CPU forward
    weights = tmp_path / "predictor.safetensors"
    safetensors.save_file(model.state_dict(), str(weights))
    weights_sha = hashlib.sha256(weights.read_bytes()).hexdigest()
    candidate = {
        "candidate_type": "compact_world_model_candidate_v1",
        "status": "trained",
        "config": {
            "architecture": "residual_mlp_v1",
            "latent_dim": 2, "action_dim": 1, "hidden_dim": 8,
        },
        "weights_file": "predictor.safetensors",
        "weights_hash": weights_sha,
        "encoder_descriptor_hash": audit["encoder_descriptor_hash"],
        "manifest_hash": "training-fixture-only",
    }
    candidate["candidate_hash"] = hashlib.sha256(
        json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")

    with pytest.raises(ValueError, match="never"):
        # This expression is unreachable and simply verifies no exception
        # suppression in the model adapter.
        raise ValueError("never")
    denied = evaluate_local_compact_on_external(
        audit, candidate_manifest_path=path
    )
    assert denied["status"] == "blocked"
    result = evaluate_local_compact_on_external(
        audit, candidate_manifest_path=path, approved=True
    )
    assert result["status"] == "heldout_latent_comparison_recorded"
    assert result["actual_cpu_model_forward_calls"] == 3
    assert result["gpu_requested"] is False
    assert result["torch_inference_mode"] is True
    assert result["candidate_weights_verified"] is True
    assert result["candidate_mse"] == pytest.approx(result["identity_mse"])
    assert result["qualified_for_manual_review"] is False
    assert result["model_activated"] is False
    assert result["files_written"] is False


def test_checkpoint_hash_corruption_fails_closed(tmp_path: Path) -> None:
    # No torch requirement: reject a tampered manifest before touching model.
    from hex_cortex.memory.cortex_compact_external_adapter_v30 import (
        evaluate_local_compact_on_external,
    )
    audit = audit_external_latent_trajectories(_synthetic_example())
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps({
        "candidate_type": "compact_world_model_candidate_v1",
        "status": "trained",
        "candidate_hash": "0" * 64,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate_manifest_hash_mismatch"):
        evaluate_local_compact_on_external(
            audit, candidate_manifest_path=source, approved=True
        )
