"""Tests of V37 fixture lifecycle and proof-of-non-generalization safeguards."""
from __future__ import annotations

import hashlib

import pytest

from hex_cortex.memory.cortex_real_cpu_smoke_cli_v37 import main
from hex_cortex.memory.cortex_real_cpu_smoke_v37 import run_real_cpu_smoke_v37


def _checkpoint(root):
    (root / "model.pt").write_bytes(b"synthetic-dummy-checkpoint-for-test-only")
    return hashlib.sha256((root / "model.pt").read_bytes()).hexdigest()


def test_no_permission_no_files_or_model(tmp_path):
    result = run_real_cpu_smoke_v37(
        project_root=tmp_path, checkpoint_path="model.pt",
        checkpoint_sha256="0" * 64,
    )
    assert result["status"] == "blocked"
    assert result["files_written"] is False
    assert result["model_called"] is False
    assert not list(tmp_path.iterdir())


def test_injected_synthetic_fixture_exact_iou_and_cleanup(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    from PIL import ImageDraw
    sha = _checkpoint(tmp_path)

    def test_mask_generator(image, boxes, checkpoint):
        assert image.size == (384, 288)
        assert boxes == {"synthetic_ellipse": (48, 54, 180, 218)}
        assert checkpoint.name == "model.pt"
        truth = Image.new("L", image.size, 0)
        ImageDraw.Draw(truth).ellipse((54, 60, 174, 212), fill=255)
        return {"synthetic_ellipse": truth}

    before = sorted(p.name for p in tmp_path.iterdir())
    report = run_real_cpu_smoke_v37(
        project_root=tmp_path, checkpoint_path="model.pt",
        checkpoint_sha256=sha, approved_read=True,
        approved_model_load=True, approved_temp_write=True,
        _infer=test_mask_generator,
    )
    assert report["status"] == "synthetic_smoke_executed"
    assert report["actual_mobile_sam_inference_called"] is False
    assert report["synthetic_reference_iou"] == 1.0
    assert report["independent_visual_generalization_attested"] is False
    assert report["files_persisted"] is False
    assert report["checkpoint_modified"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_wrong_checkpoint_digest_removes_temp_files_and_no_model(tmp_path):
    pytest.importorskip("PIL.Image")
    _checkpoint(tmp_path)
    calls = []

    def should_not_run(*args):
        calls.append(True)
        return {}

    with pytest.raises(ValueError, match="v36_checkpoint_digest_mismatch"):
        run_real_cpu_smoke_v37(
            project_root=tmp_path, checkpoint_path="model.pt",
            checkpoint_sha256="0" * 64, approved_read=True,
            approved_model_load=True, approved_temp_write=True,
            _infer=should_not_run,
        )
    assert calls == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["model.pt"]


def test_cli_dry_run_requires_no_existing_image_or_weights(capsys):
    args = [
        "--checkpoint", "nonexistent.pt",
        "--checkpoint-sha256", "0" * 64,
    ]
    assert main([*args, "--dry-run"]) == 0
    assert '"model_called": false' in capsys.readouterr().out
    assert main(args) == 2
    assert '"status": "blocked"' in capsys.readouterr().out
