from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hex_cortex.memory.cortex_environment_sequence import build_environment_sequence_manifest
from hex_cortex.memory.cortex_environment_sequence import ingest_environment_episode
from hex_cortex.memory.cortex_environment_sequence import write_environment_manifest
from hex_cortex.memory.cortex_frozen_encoder import EncoderRunner
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records

_DOMAIN = "screen_lab_policy_v2"
_GRID_SIZE = 9
_CANVAS_SIZE = 224
_ACTION_SCHEMA = ["dx", "dy"]
_ACTIONS = {
    "move_left": (-1, 0),
    "move_right": (1, 0),
    "move_up": (0, -1),
    "move_down": (0, 1),
}
_CYCLES = (
    ("move_right", "move_down", "move_left", "move_up"),
    ("move_down", "move_left", "move_up", "move_right"),
    ("move_left", "move_up", "move_right", "move_down"),
    ("move_up", "move_right", "move_down", "move_left"),
    ("move_right", "move_up", "move_left", "move_down"),
    ("move_up", "move_left", "move_down", "move_right"),
    ("move_left", "move_down", "move_right", "move_up"),
    ("move_down", "move_right", "move_up", "move_left"),
)


def build_screen_lab_policy_v2_specs(
    *,
    train_episodes: int = 24,
    validation_episodes: int = 8,
    test_episodes: int = 8,
    steps_per_episode: int = 8,
    seed: int = 42,
) -> list[dict[str, object]]:
    if steps_per_episode < 4 or steps_per_episode % 4 != 0:
        raise ValueError("steps_per_episode must be a positive multiple of four")
    counts = {
        "train": train_episodes,
        "validation": validation_episodes,
        "test": test_episodes,
    }
    if any(value < 1 for value in counts.values()):
        raise ValueError("every split requires at least one episode")
    specs: list[dict[str, object]] = []
    global_index = 0
    for split, count in counts.items():
        for split_index in range(count):
            cycle = _CYCLES[(seed + global_index) % len(_CYCLES)]
            repeats = steps_per_episode // 4
            actions = tuple(cycle * repeats)
            x = 2 + ((seed + global_index * 3) % 5)
            y = 2 + ((seed * 2 + global_index * 5) % 5)
            specs.append(
                {
                    "episode_id": f"screen-v2-{split}-{split_index + 1:03d}",
                    "split": split,
                    "start": (x, y),
                    "actions": actions,
                }
            )
            global_index += 1
    return specs


def generate_screen_lab_policy_v2_suite(
    *,
    source_root: Path,
    seed: int = 42,
    replace_existing: bool = False,
    train_episodes: int = 24,
    validation_episodes: int = 8,
    test_episodes: int = 8,
    steps_per_episode: int = 8,
) -> dict[str, object]:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return _blocked("pillow_missing")
    try:
        specs = build_screen_lab_policy_v2_specs(
            train_episodes=train_episodes,
            validation_episodes=validation_episodes,
            test_episodes=test_episodes,
            steps_per_episode=steps_per_episode,
            seed=seed,
        )
    except ValueError as exc:
        return _blocked(str(exc))

    root = source_root.resolve()
    if root.exists() and replace_existing:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    episode_receipts: list[dict[str, object]] = []
    action_counts = {action_id: 0 for action_id in _ACTIONS}
    for episode_index, spec in enumerate(specs):
        episode_id = str(spec["episode_id"])
        split = str(spec["split"])
        start = tuple(spec["start"])
        actions = tuple(spec["actions"])
        positions = _build_positions(start, actions)
        if positions is None:
            return _blocked(f"invalid_episode_path:{episode_id}")
        episode_root = root / episode_id
        frames_root = episode_root / "frames"
        frames_root.mkdir(parents=True, exist_ok=True)
        goal = positions[-1]
        for frame_index, position in enumerate(positions):
            image = _render_frame(
                Image=Image,
                ImageDraw=ImageDraw,
                position=position,
                goal=goal,
                seed=seed,
                episode_index=episode_index,
            )
            image.save(frames_root / f"frame-{frame_index:06d}.png", format="PNG")
        base_time = datetime(2026, 2, 1, tzinfo=UTC) + timedelta(
            seconds=seed * 100 + episode_index * 1000
        )
        rows: list[dict[str, object]] = []
        for step_index, action_id in enumerate(actions):
            action_counts[action_id] += 1
            dx, dy = _ACTIONS[action_id]
            rows.append(
                {
                    "step_index": step_index,
                    "action_id": action_id,
                    "action_schema": list(_ACTION_SCHEMA),
                    "action_values": [float(dx), float(dy)],
                    "reward": -0.01,
                    "terminated": step_index == len(actions) - 1,
                    "truncated": False,
                    "observed_at": (base_time + timedelta(seconds=step_index)).isoformat(),
                    "next_observed_at": (base_time + timedelta(seconds=step_index + 1)).isoformat(),
                    "environment_metadata": {
                        "capture_provenance": "deterministic_screen_lab_policy_v2",
                        "physical_world": False,
                        "externally_observed": False,
                        "clock_source": "deterministic_simulated_clock_v1",
                        "grid_size": _GRID_SIZE,
                        "canvas_size": _CANVAS_SIZE,
                        "seed": seed,
                        "visual_split_identity_present": False,
                        "agent_position": list(positions[step_index]),
                        "next_agent_position": list(positions[step_index + 1]),
                        "goal_position": list(goal),
                    },
                }
            )
        actions_path = episode_root / "actions.jsonl"
        actions_path.write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
        episode_receipts.append(
            {
                "episode_id": episode_id,
                "split": split,
                "frames_dir": str(frames_root),
                "actions_jsonl": str(actions_path),
                "frame_count": len(positions),
                "transition_count": len(actions),
                "start_position": list(start),
                "goal_position": list(goal),
            }
        )

    split_counts = {
        split: sum(
            int(episode["transition_count"])
            for episode in episode_receipts
            if episode["split"] == split
        )
        for split in ("train", "validation", "test")
    }
    balanced = len(set(action_counts.values())) == 1
    suite = {
        "suite_type": "screen_lab_policy_v2_suite",
        "status": "generated" if balanced else "blocked",
        "domain": _DOMAIN,
        "seed": seed,
        "source_root": str(root),
        "episode_count": len(episode_receipts),
        "transition_count": sum(split_counts.values()),
        "split_transition_counts": split_counts,
        "action_counts": action_counts,
        "action_balance_exact": balanced,
        "visual_split_identity_present": False,
        "episodes": episode_receipts,
        "capture_provenance": "deterministic_screen_lab_policy_v2",
        "physical_world": False,
        "externally_observed": False,
        "blockers": [] if balanced else ["action_distribution_unbalanced"],
        "next_action": "ingest_screen_lab_policy_v2_suite" if balanced else "repair_v2_suite",
    }
    suite["suite_hash"] = _stable_hash(suite)
    (root / "suite.json").write_text(
        json.dumps(suite, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite


def bootstrap_screen_lab_policy_v2(
    *,
    workspace_root: Path,
    encoder_descriptor: dict[str, object],
    operator_approved: bool = False,
    seed: int = 42,
    replace_existing_source: bool = False,
    encoder_runner: EncoderRunner | None = None,
) -> dict[str, object]:
    if not operator_approved:
        return {
            "receipt_type": "screen_lab_policy_v2_bootstrap",
            "status": "blocked",
            "blockers": ["operator_approval_required"],
            "training_performed": False,
            "execution_performed": False,
            "next_action": "approve_v2_bootstrap",
        }
    workspace = workspace_root.resolve()
    source_root = workspace / "source" / _DOMAIN
    dataset = workspace / "transitions.jsonl"
    manifest_path = workspace / "manifest.json"
    suite = generate_screen_lab_policy_v2_suite(
        source_root=source_root,
        seed=seed,
        replace_existing=replace_existing_source,
    )
    if suite.get("status") != "generated":
        return {
            "receipt_type": "screen_lab_policy_v2_bootstrap",
            "status": "blocked",
            "suite": suite,
            "blockers": list(suite.get("blockers", ["suite_generation_failed"])),
            "training_performed": False,
            "execution_performed": False,
            "next_action": "repair_v2_generator",
        }
    ingest_receipts = []
    for episode in suite["episodes"]:
        receipt = ingest_environment_episode(
            frames_dir=Path(str(episode["frames_dir"])),
            actions_jsonl=Path(str(episode["actions_jsonl"])),
            workspace_root=workspace,
            dataset_jsonl=dataset,
            domain=_DOMAIN,
            episode_id=str(episode["episode_id"]),
            split=str(episode["split"]),
            encoder_descriptor=encoder_descriptor,
            operator_approved=True,
            encoder_runner=encoder_runner,
        )
        ingest_receipts.append(receipt)
        if receipt.get("status") != "completed":
            return {
                "receipt_type": "screen_lab_policy_v2_bootstrap",
                "status": "blocked",
                "suite_hash": suite.get("suite_hash"),
                "ingest_receipts": ingest_receipts,
                "blockers": list(receipt.get("blockers", ["episode_ingest_failed"])),
                "training_performed": False,
                "execution_performed": False,
                "next_action": "repair_v2_episode_ingest",
            }
    records = load_transition_records(dataset)
    manifest = build_environment_sequence_manifest(
        records,
        min_train_episodes=24,
        min_validation_episodes=8,
        min_test_episodes=8,
        min_train_steps=192,
        min_validation_steps=64,
        min_test_steps=64,
    )
    if manifest.get("manifest_allowed") is True:
        write_environment_manifest(manifest_path, manifest)
    ready = manifest.get("training_ready") is True
    receipt = {
        "receipt_type": "screen_lab_policy_v2_bootstrap",
        "status": "ready" if ready else "blocked",
        "domain": _DOMAIN,
        "workspace_root": str(workspace),
        "source_root": str(source_root),
        "dataset_jsonl": str(dataset),
        "manifest_path": str(manifest_path),
        "suite_hash": suite.get("suite_hash"),
        "episode_count": suite.get("episode_count"),
        "transition_count": suite.get("transition_count"),
        "split_transition_counts": suite.get("split_transition_counts"),
        "action_counts": suite.get("action_counts"),
        "action_balance_exact": suite.get("action_balance_exact"),
        "visual_split_identity_present": False,
        "manifest_allowed": manifest.get("manifest_allowed"),
        "training_ready": manifest.get("training_ready"),
        "promotion_ready": manifest.get("promotion_ready"),
        "training_performed": False,
        "execution_performed": False,
        "network_call_performed": any(bool(item.get("network_call_performed")) for item in ingest_receipts),
        "blockers": list(manifest.get("blockers", [])),
        "next_action": "train_action_discriminative_world_model" if ready else "repair_v2_dataset",
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def _build_positions(start: tuple[int, int], action_ids: tuple[str, ...]) -> list[tuple[int, int]] | None:
    positions = [start]
    x, y = start
    for action_id in action_ids:
        dx, dy = _ACTIONS[action_id]
        x += dx
        y += dy
        if not 0 <= x < _GRID_SIZE or not 0 <= y < _GRID_SIZE:
            return None
        positions.append((x, y))
    return positions


def _render_frame(*, Image, ImageDraw, position, goal, seed: int, episode_index: int):
    palette_shift = (seed + episode_index * 11) % 16
    background = (24 + palette_shift, 28 + palette_shift, 36 + palette_shift)
    grid_color = (62 + palette_shift, 68 + palette_shift, 80 + palette_shift)
    border_color = (96, 176, 255)
    image = Image.new("RGB", (_CANVAS_SIZE, _CANVAS_SIZE), background)
    draw = ImageDraw.Draw(image)
    margin = 22
    usable = _CANVAS_SIZE - margin * 2
    cell = usable / _GRID_SIZE
    for index in range(_GRID_SIZE + 1):
        coordinate = round(margin + index * cell)
        draw.line((margin, coordinate, _CANVAS_SIZE - margin, coordinate), fill=grid_color)
        draw.line((coordinate, margin, coordinate, _CANVAS_SIZE - margin), fill=grid_color)
    draw.rectangle(
        (margin - 2, margin - 2, _CANVAS_SIZE - margin + 2, _CANVAS_SIZE - margin + 2),
        outline=border_color,
        width=3,
    )
    draw.ellipse(_cell_box(goal, margin, cell, inset=0.22), fill=(90, 220, 130), outline=(220, 255, 225), width=3)
    draw.rectangle(_cell_box(position, margin, cell, inset=0.18), fill=(245, 90, 90), outline=(255, 225, 225), width=3)
    return image


def _cell_box(position, margin: int, cell: float, *, inset: float):
    x, y = position
    return (
        round(margin + x * cell + cell * inset),
        round(margin + y * cell + cell * inset),
        round(margin + (x + 1) * cell - cell * inset),
        round(margin + (y + 1) * cell - cell * inset),
    )


def _blocked(blocker: str) -> dict[str, object]:
    return {
        "suite_type": "screen_lab_policy_v2_suite",
        "status": "blocked",
        "blockers": [blocker],
        "next_action": "repair_screen_lab_policy_v2_generator",
    }


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
