import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records
from hex_cortex.memory.cortex_screen_lab import bootstrap_screen_lab
from hex_cortex.memory.cortex_screen_lab import generate_screen_lab_suite

pytest.importorskip("PIL")


def _runner(image_path, model_ref, pooling, device, local_files_only):
    frame_index = int(image_path.stem.split("-")[-1])
    return [float(frame_index), 1.0, 0.0, 0.0], {
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
        "hidden_size": 4,
        "patch_size": 14,
    }


def test_generate_screen_lab_suite_creates_expected_episode_splits(tmp_path: Path) -> None:
    suite = generate_screen_lab_suite(source_root=tmp_path / "source", seed=42)

    assert suite["status"] == "generated"
    assert suite["episode_count"] == 4
    assert suite["transition_count"] == 24
    assert suite["split_transition_counts"] == {
        "train": 16,
        "validation": 4,
        "test": 4,
    }
    assert suite["capture_provenance"] == "deterministic_screen_lab_simulator_v1"
    assert suite["physical_world"] is False
    for episode in suite["episodes"]:
        frames = sorted(Path(episode["frames_dir"]).glob("*.png"))
        actions = Path(episode["actions_jsonl"]).read_text(encoding="utf-8").splitlines()
        assert len(frames) == episode["frame_count"]
        assert len(actions) == episode["transition_count"]
        first_action = json.loads(actions[0])
        assert first_action["environment_metadata"]["externally_observed"] is False


def test_bootstrap_screen_lab_produces_training_ready_manifest(tmp_path: Path) -> None:
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    workspace = tmp_path / "screen-lab"

    receipt = bootstrap_screen_lab(
        workspace_root=workspace,
        encoder_descriptor=descriptor,
        operator_approved=True,
        seed=42,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "ready"
    assert receipt["transition_count"] == 24
    assert receipt["appended_count"] == 24
    assert receipt["manifest_allowed"] is True
    assert receipt["training_ready"] is True
    assert receipt["promotion_ready"] is True
    assert receipt["training_performed"] is False
    assert receipt["execution_performed"] is False
    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["episode_counts"] == {"train": 2, "validation": 1, "test": 1}
    assert len(load_transition_records(workspace / "transitions.jsonl")) == 24


def test_bootstrap_screen_lab_requires_explicit_approval(tmp_path: Path) -> None:
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = bootstrap_screen_lab(
        workspace_root=tmp_path / "screen-lab",
        encoder_descriptor=descriptor,
        operator_approved=False,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["operator_approval_required"]
