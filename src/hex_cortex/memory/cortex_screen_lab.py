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

_SCREEN_LAB_DOMAIN = "screen_lab_v1"
_GRID_SIZE = 9
_CANVAS_SIZE = 224
_ACTION_SCHEMA = ["dx", "dy"]
_ACTIONS = {
    "move_left": (-1, 0),
    "move_right": (1, 0),
    "move_up": (0, -1),
    "move_down": (0, 1),
}
_EPISODE_SPECS = (
    {
        "episode_id": "screen-train-001",
        "split": "train",
        "start": (2, 2),
        "actions": (
            "move_right",
            "move_right",
            "move_down",
            "move_down",
            "move_left",
            "move_down",
            "move_right",
            "move_right",
        ),
    },
    {
        "episode_id": "screen-train-002",
        "split": "train",
        "start": (6, 6),
        "actions": (
            "move_left",
            "move_left",
            "move_up",
            "move_up",
            "move_right",
            "move_up",
            "move_left",
            "move_left",
        ),
    },
    {
        "episode_id": "screen-validation-001",
        "split": "validation",
        "start": (2, 3),
        "actions": ("move_right", "move_down", "move_right", "move_down"),
    },
    {
        "episode_id": "screen-test-001",
        "split": "test",
        "start": (6, 3),
        "actions": ("move_left", "move_down", "move_left", "move_down"),
    },
)


def generate_screen_lab_suite(
    *,
    source_root: Path,
    seed: int = 42,
    replace_existing: bool = False,
) -> dict[str, object]:
    if not 0 <= seed <= 2**31 - 1:
        return _blocked("seed_out_of_range")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return _blocked("pillow_missing")

    root = source_root.resolve()
    if root.exists() and replace_existing:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    episode_receipts: list[dict[str, object]] = []
    for episode_index, spec in enumerate(_EPISODE_SPECS):
        episode_id = str(spec["episode_id"])
        split = str(spec["split"])
        start = tuple(spec["start"])
        actions = tuple(spec["actions"])
        positions = _build_positions(start, actions)
        if positions is None:
            return _blocked(f"invalid_episode_path:{episode_id}")
        goal = positions[-1]
        episode_root = root / episode_id
        frames_root = episode_root / "frames"
        frames_root.mkdir(parents=True, exist_ok=True)
        action_rows: list[dict[str, object]] = []
        for frame_index, position in enumerate(positions):
            image = _render_frame(
                Image=Image,
                ImageDraw=ImageDraw,
                position=position,
                goal=goal,
                split=split,
                seed=seed,
                episode_index=episode_index,
            )
            image.save(frames_root / f"frame-{frame_index:06d}.png", format="PNG")
        base_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(
            seconds=seed * 100 + episode_index * 1000
        )
        for step_index, action_id in enumerate(actions):
            dx, dy = _ACTIONS[action_id]
            current = positions[step_index]
            next_position = positions[step_index + 1]
            terminal = step_index == len(actions) - 1
            action_rows.append(
                {
                    "step_index": step_index,
                    "action_id": action_id,
                    "action_schema": list(_ACTION_SCHEMA),
                    "action_values": [float(dx), float(dy)],
                    "reward": 1.0 if terminal else -0.01,
                    "terminated": terminal,
                    "truncated": False,
                    "observed_at": (base_time + timedelta(seconds=step_index)).isoformat(),
                    "next_observed_at": (
                        base_time + timedelta(seconds=step_index + 1)
                    ).isoformat(),
                    "environment_metadata": {
                        "capture_provenance": "deterministic_screen_lab_simulator_v1",
                        "physical_world": False,
                        "externally_observed": False,
                        "clock_source": "deterministic_simulated_clock_v1",
                        "grid_size": _GRID_SIZE,
                        "canvas_size": _CANVAS_SIZE,
                        "seed": seed,
                        "agent_position": list(current),
                        "next_agent_position": list(next_position),
                        "goal_position": list(goal),
                    },
                }
            )
        actions_path = episode_root / "actions.jsonl"
        actions_path.write_text(
            "".join(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                for row in action_rows
            ),
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

    suite = {
        "suite_type": "screen_lab_suite_v1",
        "status": "generated",
        "domain": _SCREEN_LAB_DOMAIN,
        "seed": seed,
        "source_root": str(root),
        "episode_count": len(episode_receipts),
        "transition_count": sum(
            int(episode["transition_count"]) for episode in episode_receipts
        ),
        "split_transition_counts": {
            split: sum(
                int(episode["transition_count"])
                for episode in episode_receipts
                if episode["split"] == split
            )
            for split in ("train", "validation", "test")
        },
        "episodes": episode_receipts,
        "capture_provenance": "deterministic_screen_lab_simulator_v1",
        "physical_world": False,
        "externally_observed": False,
        "blockers": [],
        "next_action": "ingest_screen_lab_suite",
    }
    suite["suite_hash"] = _stable_hash(suite)
    (root / "suite.json").write_text(
        json.dumps(suite, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite


def bootstrap_screen_lab(
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
            "receipt_type": "screen_lab_bootstrap_v1",
            "status": "blocked",
            "blockers": ["operator_approval_required"],
            "training_performed": False,
            "execution_performed": False,
            "next_action": "approve_screen_lab_bootstrap",
        }
    workspace = workspace_root.resolve()
    source_root = workspace / "source" / _SCREEN_LAB_DOMAIN
    dataset = workspace / "transitions.jsonl"
    manifest_path = workspace / "manifest.json"
    suite = generate_screen_lab_suite(
        source_root=source_root,
        seed=seed,
        replace_existing=replace_existing_source,
    )
    if suite.get("status") != "generated":
        return {
            "receipt_type": "screen_lab_bootstrap_v1",
            "status": "blocked",
            "suite": suite,
            "blockers": list(suite.get("blockers", ["suite_generation_failed"])),
            "training_performed": False,
            "execution_performed": False,
            "next_action": "repair_screen_lab_generator",
        }

    ingest_receipts: list[dict[str, object]] = []
    for episode in suite["episodes"]:
        receipt = ingest_environment_episode(
            frames_dir=Path(str(episode["frames_dir"])),
            actions_jsonl=Path(str(episode["actions_jsonl"])),
            workspace_root=workspace,
            dataset_jsonl=dataset,
            domain=_SCREEN_LAB_DOMAIN,
            episode_id=str(episode["episode_id"]),
            split=str(episode["split"]),
            encoder_descriptor=encoder_descriptor,
            operator_approved=True,
            encoder_runner=encoder_runner,
        )
        ingest_receipts.append(receipt)
        if receipt.get("status") != "completed":
            return {
                "receipt_type": "screen_lab_bootstrap_v1",
                "status": "blocked",
                "suite_hash": suite.get("suite_hash"),
                "ingest_receipts": ingest_receipts,
                "blockers": list(receipt.get("blockers", ["episode_ingest_failed"])),
                "training_performed": False,
                "execution_performed": False,
                "next_action": "repair_screen_lab_episode_ingest",
            }

    records = load_transition_records(dataset)
    manifest = build_environment_sequence_manifest(
        records,
        min_train_episodes=2,
        min_validation_episodes=1,
        min_test_episodes=1,
        min_train_steps=16,
        min_validation_steps=4,
        min_test_steps=4,
    )
    if manifest.get("manifest_allowed") is True:
        write_environment_manifest(manifest_path, manifest)
    status = "ready" if manifest.get("training_ready") is True else "blocked"
    blockers = list(manifest.get("blockers", []))
    receipt = {
        "receipt_type": "screen_lab_bootstrap_v1",
        "status": status,
        "domain": _SCREEN_LAB_DOMAIN,
        "workspace_root": str(workspace),
        "source_root": str(source_root),
        "dataset_jsonl": str(dataset),
        "manifest_path": str(manifest_path),
        "suite_hash": suite.get("suite_hash"),
        "episode_count": suite.get("episode_count"),
        "transition_count": suite.get("transition_count"),
        "split_transition_counts": suite.get("split_transition_counts"),
        "appended_count": sum(
            int(item.get("appended_count", 0)) for item in ingest_receipts
        ),
        "duplicate_count": sum(
            int(item.get("duplicate_count", 0)) for item in ingest_receipts
        ),
        "manifest_allowed": manifest.get("manifest_allowed"),
        "training_ready": manifest.get("training_ready"),
        "promotion_ready": manifest.get("promotion_ready"),
        "capture_provenance": "deterministic_screen_lab_simulator_v1",
        "physical_world": False,
        "externally_observed": False,
        "network_call_performed": any(
            bool(item.get("network_call_performed")) for item in ingest_receipts
        ),
        "training_performed": False,
        "execution_performed": False,
        "blockers": blockers,
        "next_action": (
            "plan_screen_lab_training"
            if status == "ready"
            else "collect_or_repair_screen_lab_sequences"
        ),
    }
    receipt["receipt_hash"] = _stable_hash(receipt)
    return receipt


def _build_positions(
    start: tuple[int, int],
    action_ids: tuple[str, ...],
) -> list[tuple[int, int]] | None:
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


def _render_frame(
    *,
    Image,
    ImageDraw,
    position: tuple[int, int],
    goal: tuple[int, int],
    split: str,
    seed: int,
    episode_index: int,
):
    palette_shift = (seed + episode_index * 17) % 24
    background = (20 + palette_shift, 24 + palette_shift, 32 + palette_shift)
    grid_color = (58 + palette_shift, 64 + palette_shift, 76 + palette_shift)
    border_color = {
        "train": (80, 160, 255),
        "validation": (255, 190, 80),
        "test": (210, 110, 255),
    }[split]
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
    goal_box = _cell_box(goal, margin, cell, inset=0.22)
    draw.ellipse(goal_box, fill=(90, 220, 130), outline=(220, 255, 225), width=3)
    agent_box = _cell_box(position, margin, cell, inset=0.18)
    draw.rectangle(agent_box, fill=(245, 90, 90), outline=(255, 225, 225), width=3)
    return image


def _cell_box(
    position: tuple[int, int],
    margin: int,
    cell: float,
    *,
    inset: float,
) -> tuple[int, int, int, int]:
    x, y = position
    x0 = margin + x * cell + cell * inset
    y0 = margin + y * cell + cell * inset
    x1 = margin + (x + 1) * cell - cell * inset
    y1 = margin + (y + 1) * cell - cell * inset
    return round(x0), round(y0), round(x1), round(y1)


def _blocked(blocker: str) -> dict[str, object]:
    return {
        "suite_type": "screen_lab_suite_v1",
        "status": "blocked",
        "blockers": [blocker],
        "next_action": "repair_screen_lab_generator",
    }


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
