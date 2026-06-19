import json
from pathlib import Path

from hex_cortex.memory.cortex_screen_lab_policy_evaluation import evaluate_screen_lab_policy


ACTIONS = [
    {"action_id": "move_left", "action_values": [-1.0, 0.0]},
    {"action_id": "move_right", "action_values": [1.0, 0.0]},
    {"action_id": "move_up", "action_values": [0.0, -1.0]},
    {"action_id": "move_down", "action_values": [0.0, 1.0]},
]


def _write_dataset(tmp_path: Path, actual_actions: list[str]) -> tuple[Path, Path]:
    environment_root = tmp_path / "environment"
    output = environment_root / "output" / "screen_lab_v1" / "episode-test"
    output.mkdir(parents=True)
    rows = []
    for index, action_id in enumerate(actual_actions):
        current = output / f"frame-{index:06d}.png"
        next_image = output / f"frame-{index + 1:06d}.png"
        current.write_bytes(f"current-{index}".encode())
        next_image.write_bytes(f"next-{index}".encode())
        rows.append(
            {
                "sample_id": f"sample-{index}",
                "source_kind": "real_environment_sequence_v1",
                "domain": "screen_lab_v1",
                "split": "test",
                "episode_id": "episode-test",
                "step_index": index,
                "action_id": action_id,
                "current_image_ref": current.relative_to(environment_root / "output").as_posix(),
                "next_image_ref": next_image.relative_to(environment_root / "output").as_posix(),
            }
        )
    dataset = environment_root / "transitions.jsonl"
    dataset.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return environment_root, dataset


def _router_with_wrong_index(wrong_index: int | None = None):
    call_index = 0

    def router(**kwargs):
        nonlocal call_index
        actual = ["move_left", "move_down", "move_right", "move_up"][call_index]
        chosen = "move_up" if call_index == wrong_index else actual
        rankings = []
        rank = 1
        for action in ACTIONS:
            action_id = action["action_id"]
            if action_id == chosen:
                continue
            rankings.append(
                {
                    "action_id": action_id,
                    "rank": rank + 1,
                    "decision_score": 0.4 - rank * 0.05,
                    "improvement_fraction": -0.01,
                }
            )
            rank += 1
        rankings.insert(
            0,
            {
                "action_id": chosen,
                "rank": 1,
                "decision_score": 0.8,
                "improvement_fraction": 0.1,
            },
        )
        if chosen != actual:
            for position, row in enumerate(rankings, start=1):
                row["rank"] = position
            actual_row = next(row for row in rankings if row["action_id"] == actual)
            actual_row["improvement_fraction"] = -0.02
        call_index += 1
        return {
            "status": "advisory_ready",
            "candidate_rankings": rankings,
            "recommended_action_id": chosen,
            "route_hash": f"route-{call_index}",
            "blockers": [],
        }

    return router


def test_policy_gate_passes_only_when_every_test_action_is_top1(tmp_path: Path) -> None:
    actual_actions = ["move_left", "move_down", "move_right", "move_up"]
    environment_root, dataset = _write_dataset(tmp_path, actual_actions)

    receipt = evaluate_screen_lab_policy(
        active_registry_path=tmp_path / "active.json",
        environment_root=environment_root,
        dataset_jsonl=dataset,
        environment_domain="screen_lab_v1",
        action_candidates=ACTIONS,
        encoder_descriptor={"descriptor_hash": "encoder"},
        decision_router=_router_with_wrong_index(),
    )

    assert receipt["status"] == "policy_ready"
    assert receipt["policy_ready"] is True
    assert receipt["planner_advice_allowed"] is True
    assert receipt["metrics"]["top1_action_accuracy"] == 1.0
    assert receipt["metrics"]["positive_improvement_rate"] == 1.0
    assert receipt["execution_allowed"] is False


def test_policy_gate_blocks_wrong_top1_action(tmp_path: Path) -> None:
    actual_actions = ["move_left", "move_down", "move_right", "move_up"]
    environment_root, dataset = _write_dataset(tmp_path, actual_actions)

    receipt = evaluate_screen_lab_policy(
        active_registry_path=tmp_path / "active.json",
        environment_root=environment_root,
        dataset_jsonl=dataset,
        environment_domain="screen_lab_v1",
        action_candidates=ACTIONS,
        encoder_descriptor={"descriptor_hash": "encoder"},
        decision_router=_router_with_wrong_index(0),
    )

    assert receipt["status"] == "policy_blocked"
    assert receipt["policy_ready"] is False
    assert receipt["metrics"]["top1_action_accuracy"] == 0.75
    assert "top1_action_accuracy_below_threshold" in receipt["blockers"]
    assert "positive_improvement_rate_below_threshold" in receipt["blockers"]
    assert "correct_action_not_strictly_preferred" in receipt["blockers"]


def test_policy_gate_requires_minimum_sample_count(tmp_path: Path) -> None:
    environment_root, dataset = _write_dataset(tmp_path, ["move_left"])

    receipt = evaluate_screen_lab_policy(
        active_registry_path=tmp_path / "active.json",
        environment_root=environment_root,
        dataset_jsonl=dataset,
        environment_domain="screen_lab_v1",
        action_candidates=ACTIONS,
        encoder_descriptor={"descriptor_hash": "encoder"},
        minimum_samples=4,
        decision_router=_router_with_wrong_index(),
    )

    assert receipt["status"] == "blocked"
    assert receipt["sample_count"] == 1
    assert receipt["blockers"] == ["insufficient_policy_evaluation_samples"]
