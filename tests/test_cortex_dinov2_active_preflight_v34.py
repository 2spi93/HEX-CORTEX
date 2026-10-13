"""V34: no unapproved cached models, network, GPU or checkpoint mutations."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_dinov2_active_preflight_cli_v34 import main
from hex_cortex.memory.cortex_dinov2_active_preflight_v34 import (
    inspect_active_dinov2,
)
from hex_cortex.memory.cortex_frozen_encoder import (
    build_frozen_encoder_descriptor,
)
from test_cortex_active_world_integrity_v31 import _build_fixture, _hash


def _patched_descriptor(monkeypatch: pytest.MonkeyPatch) -> None:
    import hex_cortex.memory.cortex_dinov2_active_preflight_v34 as target

    real = build_frozen_encoder_descriptor(device="cpu")
    real["descriptor_hash"] = _hash("encoder")
    monkeypatch.setattr(
        target, "build_frozen_encoder_descriptor",
        lambda **kw: dict(real),
    )


def test_dry_run_and_missing_read_approval_are_strict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["encoder_loaded"] is False
    assert main(["--project-root", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert inspect_active_dinov2(project_root=tmp_path)["cache_probed"] is False


def test_descriptor_match_does_not_implicitly_probe_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    _patched_descriptor(monkeypatch)
    def probe(_ref: str):
        raise AssertionError("cache must not be probed")
    result = inspect_active_dinov2(
        project_root=tmp_path, approved_read=True,
        cache_probe=probe,
    )
    assert result["status"] == "active_encoder_descriptor_matches"
    assert result["descriptor_matches_active_checkpoint"] is True
    assert result["cache_probed"] is False
    assert result["encoder_loaded"] is False
    assert result["legacy_split_evidence_ok"] is True


def test_requested_encoder_mismatch_blocks_cache_and_inference(
    tmp_path: Path,
) -> None:
    _build_fixture(tmp_path)
    result = inspect_active_dinov2(
        project_root=tmp_path, approved_read=True,
        approved_cache_probe=True,
        cache_probe=lambda _: (_ for _ in ()).throw(AssertionError("cache probed")),
    )
    assert result["status"] == "active_encoder_descriptor_mismatch"
    assert result["cache_probed"] is False
    assert result["encoder_loaded"] is False


def test_cached_metadata_detection_never_claims_model_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    _patched_descriptor(monkeypatch)
    result = inspect_active_dinov2(
        project_root=tmp_path, approved_read=True,
        approved_cache_probe=True,
        cache_probe=lambda _: {
            "config": True, "preprocessor": True, "weights_file_hint": True,
        },
        cpu_loader=lambda _: (_ for _ in ()).throw(AssertionError("loaded")),
    )
    assert result["status"] == "active_encoder_cached_files_detected_not_loaded"
    assert result["cache_probed"] is True
    assert result["encoder_loaded"] is False
    assert result["cache_not_model_load_attestation"] is True
    assert result["files_written"] is False


def test_missing_cached_file_stops_before_cpu_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    _patched_descriptor(monkeypatch)
    result = inspect_active_dinov2(
        project_root=tmp_path, approved_read=True,
        approved_cache_probe=True, approved_load=True,
        cache_probe=lambda _: {
            "config": True, "preprocessor": False, "weights_file_hint": True,
        },
        cpu_loader=lambda _: (_ for _ in ()).throw(AssertionError("loaded")),
    )
    assert result["status"] == "active_encoder_cached_artifacts_missing"
    assert result["encoder_loaded"] is False


def test_cpu_load_is_separately_approved_and_dim_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    _patched_descriptor(monkeypatch)
    cache = lambda _: {
        "config": True, "preprocessor": True, "weights_file_hint": True,
    }
    assert inspect_active_dinov2(
        project_root=tmp_path, approved_read=True, approved_load=True,
        cache_probe=cache,
    )["status"] == "blocked"
    result = inspect_active_dinov2(
        project_root=tmp_path, approved_read=True,
        approved_cache_probe=True, approved_load=True,
        cache_probe=cache,
        cpu_loader=lambda _: {
            "hidden_size": 2, "device": "cpu", "model_eval_mode": True,
            "requires_grad": False,
        },
    )
    assert result["status"] == "active_encoder_cached_weights_loaded_cpu"
    assert result["loaded_hidden_size"] == 2
    assert result["encoder_loaded"] is True
    assert result["gpu_used"] is False
    for detail in (
        {"hidden_size": 768, "device": "cpu", "model_eval_mode": True,
         "requires_grad": False},
        {"hidden_size": 2, "device": "cuda", "model_eval_mode": True,
         "requires_grad": False},
    ):
        mismatch = inspect_active_dinov2(
            project_root=tmp_path, approved_read=True,
            approved_cache_probe=True, approved_load=True,
            cache_probe=cache, cpu_loader=lambda _ref: detail,
        )
        assert mismatch["status"] == "active_encoder_cpu_or_dimension_mismatch"
        assert mismatch["encoder_loaded"] is False


def test_local_cache_input_contract_rejects_fake_boolean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_fixture(tmp_path)
    _patched_descriptor(monkeypatch)
    with pytest.raises(ValueError, match="active_encoder_invalid_local_cache_probe"):
        inspect_active_dinov2(
            project_root=tmp_path, approved_read=True,
            approved_cache_probe=True,
            cache_probe=lambda _: {
                "config": "yes", "preprocessor": True, "weights_file_hint": True,
            },
        )
