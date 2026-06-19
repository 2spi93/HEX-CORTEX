import json
from pathlib import Path

from hex_cortex.memory.cortex_environment_sequence import build_environment_sequence_manifest
from hex_cortex.memory.cortex_environment_sequence import ingest_environment_episode
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records


def _runner(image_path, model_ref, pooling, device, local_files_only):
    index = int(image_path.stem.split("-")[-1])
    vector = [float(index), 1.0, 0.0, 0.0]
    return vector, {
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
        "hidden_size": 4,
        "patch_size": 14,
    }


def _write_episode(source_root: Path, episode_id: str, action_offset: float = 0.0):
    frames = source_root / episode_id / "frames"
    frames.mkdir(parents=True)
    for index in range(3):
        (frames / f"frame-{index:06d}.png").write_bytes(f"{episode_id}:{index}".encode())
    actions_path = source_root / episode_id / "actions.jsonl"
    rows = []
    for index in range(2):
        rows.append(
            {
                "step_index": index,
                "action_id": f"move_{index}",
                "action_schema": ["x", "y"],
                "action_values": [action_offset + index * 0.1, 0.0],
                "reward": float(index),
                "terminated": index == 1,
                "truncated": False,
                "observed_at": f"2026-06-19T20:00:0{index}+00:00",
                "next_observed_at": f"2026-06-19T20:00:0{index + 1}+00:00",
            }
        )
    actions_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return frames, actions_path


def test_ingest_environment_episode_creates_managed_sequence(tmp_path: Path) -> None:
    frames, actions = _write_episode(tmp_path / "source", "episode-a")
    workspace = tmp_path / "workspace"
    dataset = tmp_path / "dataset.jsonl"
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = ingest_environment_episode(
        frames_dir=frames,
        actions_jsonl=actions,
        workspace_root=workspace,
        dataset_jsonl=dataset,
        domain="screen_lab_v1",
        episode_id="episode-a",
        split="train",
        encoder_descriptor=descriptor,
        operator_approved=True,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "completed"
    assert receipt["transition_count"] == 2
    assert receipt["appended_count"] == 2
    records = load_transition_records(dataset)
    assert [record["step_index"] for record in records] == [0, 1]
    assert all(record["source_kind"] == "real_environment_sequence_v1" for record in records)
    assert records[0]["next_image_hash"] == records[1]["current_image_hash"]
    assert records[0]["latent_vector_persisted"] is False
    assert records[0]["current_image_ref"].startswith("screen_lab_v1/episode-a/")


def test_ingest_requires_explicit_approval(tmp_path: Path) -> None:
    frames, actions = _write_episode(tmp_path / "source", "episode-a")
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = ingest_environment_episode(
        frames_dir=frames,
        actions_jsonl=actions,
        workspace_root=tmp_path / "workspace",
        dataset_jsonl=tmp_path / "dataset.jsonl",
        domain="screen_lab_v1",
        episode_id="episode-a",
        split="train",
        encoder_descriptor=descriptor,
        operator_approved=False,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "blocked"
    assert "operator_approval_required" in receipt["blockers"]


def test_episode_aware_manifest_prevents_cross_split_leakage(tmp_path: Path) -> None:
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    workspace = tmp_path / "workspace"
    dataset = tmp_path / "dataset.jsonl"
    source = tmp_path / "source"
    specifications = [
        ("train-a", "train", 0.0),
        ("train-b", "train", 0.2),
        ("validation-a", "validation", 0.4),
        ("test-a", "test", 0.6),
    ]
    for episode_id, split, offset in specifications:
        frames, actions = _write_episode(source, episode_id, offset)
        receipt = ingest_environment_episode(
            frames_dir=frames,
            actions_jsonl=actions,
            workspace_root=workspace,
            dataset_jsonl=dataset,
            domain="screen_lab_v1",
            episode_id=episode_id,
            split=split,
            encoder_descriptor=descriptor,
            operator_approved=True,
            encoder_runner=_runner,
        )
        assert receipt["status"] == "completed"

    manifest = build_environment_sequence_manifest(
        load_transition_records(dataset),
        min_train_episodes=2,
        min_validation_episodes=1,
        min_test_episodes=1,
        min_train_steps=4,
        min_validation_steps=2,
        min_test_steps=2,
    )

    assert manifest["manifest_allowed"] is True
    assert manifest["training_ready"] is True
    assert manifest["promotion_ready"] is True
    assert manifest["episode_count"] == 4
    assert manifest["episode_counts"] == {"train": 2, "validation": 1, "test": 1}
    assert manifest["split_policy"] == "episode_level_no_cross_split_leakage"


def test_manifest_blocks_episode_split_leakage(tmp_path: Path) -> None:
    frames, actions = _write_episode(tmp_path / "source", "episode-a")
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    dataset = tmp_path / "dataset.jsonl"
    ingest_environment_episode(
        frames_dir=frames,
        actions_jsonl=actions,
        workspace_root=tmp_path / "workspace",
        dataset_jsonl=dataset,
        domain="screen_lab_v1",
        episode_id="episode-a",
        split="train",
        encoder_descriptor=descriptor,
        operator_approved=True,
        encoder_runner=_runner,
    )
    records = load_transition_records(dataset)
    records[1]["split"] = "test"

    manifest = build_environment_sequence_manifest(records)

    assert manifest["manifest_allowed"] is False
    assert "episode_split_leakage:episode-a" in manifest["blockers"]
