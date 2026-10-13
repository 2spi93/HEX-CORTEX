"""Frozen image encoder cross-module integration, without model download."""
from __future__ import annotations

import struct
from pathlib import Path

from hex_cortex.memory.cortex_local_vision_bridge_v26 import encode_operator_image


def _png(root: Path) -> Path:
    path = root / "selected.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
        + struct.pack(">II", 16, 12) + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    return path


def test_encoder_never_runs_without_two_approvals(tmp_path: Path) -> None:
    path = _png(tmp_path)
    calls: list[bool] = []

    def runner(*_args):
        calls.append(True)
        return [1.0, 2.0], {"device": "cpu"}

    result = encode_operator_image(
        project_root=tmp_path, image_path=path,
        approved_read=True, runner=runner,
    )
    assert result["status"] == "blocked"
    assert not calls


def test_cached_cpu_encoder_receipt_no_vector_persistence(tmp_path: Path) -> None:
    path = _png(tmp_path)
    calls: list[tuple] = []

    def fake_runner(*args):
        calls.append(args)
        return [1.0, 2.0, 2.0], {
            "device": "cpu", "model_eval_mode": True,
            "requires_grad": False,
        }

    result = encode_operator_image(
        project_root=tmp_path, image_path=path,
        approved_read=True, approved_encoding=True,
        runner=fake_runner,
    )
    assert result["status"] == "embedding_created"
    assert result["embedding_dim"] == 3
    assert result["embedding_sha256"]
    assert result["encoder_receipt_sha256"]
    assert result["source_sha256"]
    assert result["width_px"] == 16
    assert result["height_px"] == 12
    assert calls[0][3] == "cpu"
    assert calls[0][4] is True
    assert result["network_call_performed"] is False
    assert result["model_download_allowed"] is False
    assert result["object_detection_performed"] is False
    assert result["embedding_vector_persisted"] is False


def test_missing_model_weights_are_not_relabelled_as_success(tmp_path: Path) -> None:
    path = _png(tmp_path)

    def missing_weights(*_args):
        raise FileNotFoundError("cache empty")

    result = encode_operator_image(
        project_root=tmp_path, image_path=path,
        approved_read=True, approved_encoding=True,
        runner=missing_weights,
    )
    assert result["status"] == "blocked"
    assert result["encoder_status"] == "failed"
    assert result["encoder_error_type"] == "FileNotFoundError"
    assert result["embedding_sha256"] is None
