from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_observed_transition_dataset import append_transition_jsonl
from hex_cortex.memory.cortex_observed_transition_dataset import build_transition_dataset_manifest
from hex_cortex.memory.cortex_observed_transition_dataset import capture_observed_transition

_ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_ALLOWED_SPLITS = {"train", "validation", "test"}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def ingest_environment_episode(
    *,
    frames_dir: Path,
    actions_jsonl: Path,
    workspace_root: Path,
    dataset_jsonl: Path,
    domain: str,
    episode_id: str,
    split: str,
    encoder_descriptor: dict[str, object],
    operator_approved: bool = False,
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    blockers = _validate_episode_inputs(
        frames_dir=frames_dir,
        actions_jsonl=actions_jsonl,
        domain=domain,
        episode_id=episode_id,
        split=split,
        encoder_descriptor=encoder_descriptor,
        operator_approved=operator_approved,
    )
    if blockers:
        return _blocked_ingest(blockers)
    frames = _list_frames(frames_dir)
    try:
        actions = load_environment_actions(actions_jsonl)
    except (OSError, ValueError) as exc:
        return _blocked_ingest([str(exc)])
    if len(frames) < 2:
        return _blocked_ingest(["at_least_two_frames_required"])
    if len(actions) != len(frames) - 1:
        return _blocked_ingest(["action_count_must_equal_frame_count_minus_one"])
    action_blockers = _validate_action_sequence(actions)
    if action_blockers:
        return _blocked_ingest(action_blockers)

    output_root = (workspace_root.resolve() / "output").resolve()
    episode_root = (output_root / domain / episode_id).resolve()
    if not episode_root.is_relative_to(output_root):
        return _blocked_ingest(["managed_episode_path_escape"])
    episode_root.mkdir(parents=True, exist_ok=True)
    managed_frames = _copy_frames(frames, episode_root)

    records: list[dict[str, object]] = []
    appended = 0
    duplicates = 0
    for index, action in enumerate(actions):
        record = capture_observed_transition(
            comfy_root=workspace_root,
            current_image_path=managed_frames[index],
            next_image_path=managed_frames[index + 1],
            action=list(action["action_values"]),
            action_schema=list(action["action_schema"]),
            split=split,
            domain=domain,
            source_receipt_hash=action.get("source_receipt_hash"),
            next_source_receipt_hash=action.get("next_source_receipt_hash"),
            encoder_descriptor=encoder_descriptor,
            encoder_runner=encoder_runner,
        )
        if record.get("blockers"):
            return _blocked_ingest(
                [f"step_{index}:{blocker}" for blocker in record.get("blockers", [])],
                completed_steps=len(records),
            )
        record.update(
            {
                "source_kind": "real_environment_sequence_v1",
                "episode_id": episode_id,
                "step_index": index,
                "action_id": action["action_id"],
                "reward": action.get("reward"),
                "terminated": bool(action.get("terminated", False)),
                "truncated": bool(action.get("truncated", False)),
                "observed_at": action.get("observed_at"),
                "next_observed_at": action.get("next_observed_at"),
                "environment_metadata": action.get("environment_metadata", {}),
                "managed_frame_copy": True,
            }
        )
        record["sample_id"] = "environment_transition_" + _stable_hash(
            {
                "domain": domain,
                "episode_id": episode_id,
                "step_index": index,
                "current_image_hash": record["current_image_hash"],
                "next_image_hash": record["next_image_hash"],
                "action_hash": record["action_hash"],
            }
        )[:24]
        record.pop("record_hash", None)
        record["record_hash"] = _stable_hash(record)
        append_receipt = append_transition_jsonl(dataset_jsonl, record)
        appended += int(append_receipt["appended"] is True)
        duplicates += int(append_receipt["duplicate"] is True)
        records.append(record)

    receipt = {
        "receipt_type": "real_environment_episode_ingest_v1",
        "status": "completed",
        "domain": domain,
        "episode_id": episode_id,
        "split": split,
        "source_frame_count": len(frames),
        "transition_count": len(records),
        "appended_count": appended,
        "duplicate_count": duplicates,
        "dataset_jsonl": str(dataset_jsonl.resolve()),
        "managed_episode_root": str(episode_root),
        "encoder_descriptor_hash": encoder_descriptor.get("descriptor_hash"),
        "network_call_performed": any(
            bool(record.get("network_call_performed")) for record in records
        ),
        "training_performed": False,
        "execution_performed": False,
        "raw_frame_embedded_in_receipt": False,
        "latent_vector_persisted": False,
        "blockers": [],
        "next_action": "build_episode_aware_manifest",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def load_environment_actions(path: Path) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    with path.resolve().open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid_action_jsonl_line:{line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"action_record_not_object:{line_number}")
            actions.append(payload)
    return actions


def build_environment_sequence_manifest(
    records: list[dict[str, object]],
    *,
    min_train_episodes: int = 2,
    min_validation_episodes: int = 1,
    min_test_episodes: int = 1,
    min_train_steps: int = 16,
    min_validation_steps: int = 4,
    min_test_steps: int = 4,
) -> dict[str, object]:
    blockers: list[str] = []
    sequence_records = [
        record
        for record in records
        if record.get("source_kind") == "real_environment_sequence_v1"
    ]
    if len(sequence_records) != len(records):
        blockers.append("non_environment_records_present")
    episodes: dict[str, list[dict[str, object]]] = defaultdict(list)
    episode_splits: dict[str, set[str]] = defaultdict(set)
    for index, record in enumerate(sequence_records):
        episode_id = record.get("episode_id")
        step_index = record.get("step_index")
        if not isinstance(episode_id, str) or not episode_id:
            blockers.append(f"record_{index}:episode_id_missing")
            continue
        if not isinstance(step_index, int) or step_index < 0:
            blockers.append(f"record_{index}:step_index_invalid")
            continue
        episodes[episode_id].append(record)
        split = record.get("split")
        if isinstance(split, str):
            episode_splits[episode_id].add(split)
    for episode_id, splits in episode_splits.items():
        if len(splits) != 1:
            blockers.append(f"episode_split_leakage:{episode_id}")
    for episode_id, episode_records in episodes.items():
        ordered = sorted(episode_records, key=lambda item: int(item["step_index"]))
        expected = list(range(len(ordered)))
        observed = [int(item["step_index"]) for item in ordered]
        if observed != expected:
            blockers.append(f"episode_steps_not_contiguous:{episode_id}")
        for offset in range(len(ordered) - 1):
            if ordered[offset].get("next_image_hash") != ordered[offset + 1].get(
                "current_image_hash"
            ):
                blockers.append(f"episode_frame_continuity_break:{episode_id}:{offset}")
            if ordered[offset].get("terminated") is True or ordered[offset].get("truncated") is True:
                blockers.append(f"episode_terminal_before_last_step:{episode_id}:{offset}")
        timestamp_blocker = _episode_timestamp_blocker(ordered)
        if timestamp_blocker:
            blockers.append(f"{timestamp_blocker}:{episode_id}")

    base_manifest = build_transition_dataset_manifest(
        sequence_records,
        min_train=min_train_steps,
        min_validation=min_validation_steps,
        min_test=min_test_steps,
    )
    blockers.extend(base_manifest.get("blockers", []))
    episode_counts = {
        split: sum(splits == {split} for splits in episode_splits.values())
        for split in ("train", "validation", "test")
    }
    episode_thresholds_met = (
        episode_counts["train"] >= min_train_episodes
        and episode_counts["validation"] >= min_validation_episodes
        and episode_counts["test"] >= min_test_episodes
    )
    blockers = sorted(set(blockers))
    manifest_allowed = bool(sequence_records) and not blockers
    training_ready = (
        manifest_allowed
        and base_manifest.get("training_ready") is True
        and episode_thresholds_met
    )
    manifest = {
        **base_manifest,
        "manifest_type": "real_environment_sequence_manifest_v1",
        "manifest_allowed": manifest_allowed,
        "training_ready": training_ready,
        "promotion_ready": training_ready,
        "episode_count": len(episodes),
        "episode_counts": episode_counts,
        "sequence_step_count": len(sequence_records),
        "episode_thresholds": {
            "min_train_episodes": min_train_episodes,
            "min_validation_episodes": min_validation_episodes,
            "min_test_episodes": min_test_episodes,
        },
        "step_thresholds": {
            "min_train_steps": min_train_steps,
            "min_validation_steps": min_validation_steps,
            "min_test_steps": min_test_steps,
        },
        "split_policy": "episode_level_no_cross_split_leakage",
        "source_kind": "real_environment_sequence_v1",
        "blockers": blockers,
        "next_action": (
            "train_real_environment_candidate"
            if training_ready
            else "collect_more_real_environment_episodes"
        ),
    }
    manifest["manifest_hash"] = _stable_hash(
        {
            "base_manifest_hash": base_manifest.get("manifest_hash"),
            "episode_counts": episode_counts,
            "episode_ids": sorted(episodes),
            "blockers": blockers,
        }
    )
    return manifest


def write_environment_manifest(path: Path, manifest: dict[str, object]) -> None:
    if manifest.get("manifest_allowed") is not True:
        raise ValueError("environment sequence manifest is not allowed")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _validate_episode_inputs(
    *,
    frames_dir: Path,
    actions_jsonl: Path,
    domain: str,
    episode_id: str,
    split: str,
    encoder_descriptor: dict[str, object],
    operator_approved: bool,
) -> list[str]:
    blockers: list[str] = []
    if not operator_approved:
        blockers.append("operator_approval_required")
    if not frames_dir.resolve().is_dir():
        blockers.append("frames_directory_missing")
    if not actions_jsonl.resolve().is_file():
        blockers.append("actions_jsonl_missing")
    if not _SAFE_ID.fullmatch(domain):
        blockers.append("domain_invalid")
    if not _SAFE_ID.fullmatch(episode_id):
        blockers.append("episode_id_invalid")
    if split not in _ALLOWED_SPLITS:
        blockers.append("split_invalid")
    if encoder_descriptor.get("descriptor_allowed") is not True:
        blockers.append("encoder_descriptor_not_allowed")
    return blockers


def _validate_action_sequence(actions: list[dict[str, object]]) -> list[str]:
    blockers: list[str] = []
    schema_hashes: set[str] = set()
    for index, action in enumerate(actions):
        if action.get("step_index") != index:
            blockers.append(f"action_step_index_invalid:{index}")
        action_id = action.get("action_id")
        if not isinstance(action_id, str) or not _SAFE_ID.fullmatch(action_id):
            blockers.append(f"action_id_invalid:{index}")
        values = action.get("action_values")
        schema = action.get("action_schema")
        if not isinstance(values, list) or not values:
            blockers.append(f"action_values_missing:{index}")
            continue
        if not isinstance(schema, list) or len(schema) != len(values):
            blockers.append(f"action_schema_dimension_mismatch:{index}")
            continue
        if not all(isinstance(name, str) and name.strip() for name in schema):
            blockers.append(f"action_schema_invalid:{index}")
        schema_hashes.add(_stable_hash(schema))
        for value in values:
            if not isinstance(value, int | float) or not math.isfinite(float(value)):
                blockers.append(f"action_value_invalid:{index}")
                break
            if abs(float(value)) > 1.0:
                blockers.append(f"action_value_out_of_range:{index}")
                break
        for flag in ("terminated", "truncated"):
            if flag in action and not isinstance(action[flag], bool):
                blockers.append(f"{flag}_invalid:{index}")
        if "reward" in action and action["reward"] is not None:
            reward = action["reward"]
            if not isinstance(reward, int | float) or not math.isfinite(float(reward)):
                blockers.append(f"reward_invalid:{index}")
    if len(schema_hashes) > 1:
        blockers.append("mixed_action_schemas_within_episode")
    return sorted(set(blockers))


def _list_frames(frames_dir: Path) -> list[Path]:
    return sorted(
        (
            path.resolve()
            for path in frames_dir.resolve().iterdir()
            if path.is_file() and path.suffix.lower() in _ALLOWED_IMAGE_SUFFIXES
        ),
        key=lambda path: path.name,
    )


def _copy_frames(frames: list[Path], episode_root: Path) -> list[Path]:
    managed: list[Path] = []
    for index, source in enumerate(frames):
        target = episode_root / f"frame-{index:06d}{source.suffix.lower()}"
        if not target.exists() or _file_hash(target) != _file_hash(source):
            shutil.copy2(source, target)
        managed.append(target.resolve())
    return managed


def _episode_timestamp_blocker(records: list[dict[str, object]]) -> str | None:
    previous: datetime | None = None
    for record in records:
        observed = _parse_timestamp(record.get("observed_at"))
        next_observed = _parse_timestamp(record.get("next_observed_at"))
        if observed is None and record.get("observed_at") is not None:
            return "observed_timestamp_invalid"
        if next_observed is None and record.get("next_observed_at") is not None:
            return "next_observed_timestamp_invalid"
        if observed is not None and next_observed is not None and next_observed <= observed:
            return "non_positive_transition_duration"
        if previous is not None and observed is not None and observed < previous:
            return "episode_timestamps_not_monotonic"
        previous = next_observed or observed or previous
    return None


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _blocked_ingest(blockers: list[str], *, completed_steps: int = 0) -> dict[str, object]:
    return {
        "receipt_type": "real_environment_episode_ingest_v1",
        "status": "blocked",
        "completed_steps": completed_steps,
        "training_performed": False,
        "execution_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_environment_episode_inputs",
    }


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
