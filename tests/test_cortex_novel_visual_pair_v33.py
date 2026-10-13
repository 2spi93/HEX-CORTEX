"""V33: evaluate an actually existing CPU checkpoint against new heldout images."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_novel_visual_pair_cli_v33 import main
from hex_cortex.memory.cortex_novel_visual_pair_v33 import evaluate_new_visual_pair
from test_cortex_active_world_integrity_v31 import _build_fixture, _hash


def _inputs(root: Path) -> tuple[Path, Path]:
    images = root / "new_images"
    images.mkdir()
    a, b = images / "a.png", images / "b.png"
    a.write_bytes(b"synthetic_placeholder_image_A_png")
    b.write_bytes(b"synthetic_placeholder_image_B_png")
    return a, b


def _install_real_cpu_checkpoint(root: Path) -> None:
    torch = pytest.importorskip("torch")
    safetensors = pytest.importorskip("safetensors.torch")
    from hex_cortex.memory.cortex_compact_world_model import _build_model

    state = _build_fixture(root)
    model = _build_model(torch, latent_dim=2, action_dim=1, hidden_dim=8)
    with torch.no_grad():
        for param in model.parameters():
            param.zero_()
    weights = state / "candidate" / "predictor.safetensors"
    safetensors.save_file(model.state_dict(), str(weights))
    weight_hash = hashlib.sha256(weights.read_bytes()).hexdigest()
    candidate_file = state / "candidate" / "candidate.json"
    candidate = json.loads(candidate_file.read_text(encoding="utf-8"))
    candidate["weights_hash"] = weight_hash
    candidate["config"] = {
        "architecture": "residual_mlp_v1",
        "latent_dim": 2, "action_dim": 1, "hidden_dim": 8,
    }
    candidate["candidate_hash"] = _hash({
        k: v for k, v in candidate.items() if k != "candidate_hash"
    })
    candidate_file.write_text(json.dumps(candidate), encoding="utf-8")
    (state / "registry" / "active_predictor.safetensors").write_bytes(
        weights.read_bytes()
    )
    active_candidate = dict(candidate)
    active_candidate["weights_file"] = "active_predictor.safetensors"
    active_candidate["promoted"] = True
    active_candidate["promotion_receipt_hash"] = _hash({
        "candidate_hash": candidate["candidate_hash"],
        "weights_hash": weight_hash,
    })
    (state / "registry" / "active_candidate.json").write_text(
        json.dumps(active_candidate), encoding="utf-8"
    )
    active_file = state / "registry" / "active.json"
    active = json.loads(active_file.read_text(encoding="utf-8"))
    active["candidate_hash"] = candidate["candidate_hash"]
    active["weights_hash"] = weight_hash
    active["promotion_receipt_hash"] = active_candidate["promotion_receipt_hash"]
    active["registry_hash"] = _hash({
        k: v for k, v in active.items() if k != "registry_hash"
    })
    active_file.write_text(json.dumps(active), encoding="utf-8")


def _evaluate(root: Path, *, approve_read: bool = True,
              approved_encoding: bool = False,
              approved_inference: bool = False,
              encoder_runner=None) -> dict:
    images = root / "new_images"
    return evaluate_new_visual_pair(
        project_root=root, image_root=images,
        current_image="a.png", next_image="b.png",
        action=[0.1], action_schema=["control"],
        approved_read=approve_read, approved_encoding=approved_encoding,
        approved_inference=approved_inference, encoder_runner=encoder_runner,
    )


def test_readonly_novel_pair_preflight_and_no_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_real_cpu_checkpoint(tmp_path)
    _inputs(tmp_path)
    import hex_cortex.memory.cortex_novel_visual_pair_v33 as module

    original = build_frozen_encoder_descriptor()
    original["descriptor_hash"] = _hash("encoder")
    monkeypatch.setattr(module, "build_frozen_encoder_descriptor", lambda **kw: original)
    assert _evaluate(tmp_path, approve_read=False)["status"] == "blocked"
    result = _evaluate(tmp_path)
    assert result["status"] == "novel_pair_preflight_only"
    assert result["novel_exact_image_hashes"] is True
    assert result["legacy_dataset_split_evidence_ok"] is True
    assert result["encoder_calls"] == 0
    assert result["model_forward_calls"] == 0
    assert result["test_episode_and_scene_independence_attested"] is False


def test_real_torch_cpu_model_inference_and_encoder_runner_are_gated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_real_cpu_checkpoint(tmp_path)
    _inputs(tmp_path)
    import hex_cortex.memory.cortex_novel_visual_pair_v33 as module

    descriptor = build_frozen_encoder_descriptor()
    descriptor["descriptor_hash"] = _hash("encoder")
    monkeypatch.setattr(module, "build_frozen_encoder_descriptor", lambda **kw: descriptor)
    calls = []
    def fake_encoder(path: Path, _model: str, _pool: str,
                     device: str, local_only: bool):
        calls.append((path.name, device, local_only))
        return ([1., 0.] if path.name == "a.png" else [0., 1.]), {
            "device": "cpu", "model_eval_mode": True,
            "requires_grad": False,
        }
    result = _evaluate(
        tmp_path, approved_encoding=True,
        approved_inference=True, encoder_runner=fake_encoder
    )
    assert result["status"] == "single_novel_pair_cpu_comparison_recorded"
    assert result["encoder_calls"] == 2
    assert result["model_forward_calls"] == 1
    assert result["latent_dim"] == 2
    assert result["active_candidate_mse"] == pytest.approx(1)
    assert result["identity_baseline_mse"] == pytest.approx(1)
    assert result["candidate_better_on_this_pair"] is False
    assert result["promotion_allowed_by_novel_pair_study"] is False
    assert result["gpu_used"] is False
    assert result["test_episode_and_scene_independence_attested"] is False
    assert calls == [("a.png", "cpu", True), ("b.png", "cpu", True)]


def test_exact_seen_image_denied_before_dinov2_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_real_cpu_checkpoint(tmp_path)
    _inputs(tmp_path)
    import hex_cortex.memory.cortex_novel_visual_pair_v33 as module
    historical = json.loads(
        (tmp_path / ".hex-cortex" / "world-model" / "transitions.jsonl")
        .read_text(encoding="utf-8").splitlines()[0]
    )
    real_sha256 = module._sha256
    monkeypatch.setattr(module, "_sha256", lambda p:
                        historical["current_image_hash"]
                        if p.name == "a.png" else real_sha256(p))
    seen = _evaluate(tmp_path, approved_encoding=True, approved_inference=True)
    assert seen["status"] == "blocked"
    assert seen["reason"] == "novel_pair_image_seen_in_active_dataset"
    assert seen["model_forward_calls"] == 0
    assert seen["current_seen"] is True


def test_operator_image_files_must_be_in_explicit_approved_root(
    tmp_path: Path,
) -> None:
    _inputs(tmp_path)
    result = evaluate_new_visual_pair(
        project_root=tmp_path, image_root=tmp_path / "new_images",
        current_image="../outside.png", next_image="b.png",
        action=[0.1], action_schema=["control"], approved_read=False,
    )
    assert result["status"] == "blocked"
    with pytest.raises(ValueError, match="novel_pair_image_path_invalid"):
        evaluate_new_visual_pair(
            project_root=tmp_path, image_root=tmp_path / "new_images",
            current_image="../outside.png", next_image="b.png",
            action=[0.1], action_schema=["control"], approved_read=True,
        )


def test_cli_no_implicit_read_or_network(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--image-root", "nonexistent_images",
        "--current-image", "a.png", "--next-image", "b.png",
        "--action", "0,0,0,0",
    ]
    assert main([*args, "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "configuration_only"
    assert report["files_read"] is False
    assert report["model_forward_calls"] == 0
    assert main(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
