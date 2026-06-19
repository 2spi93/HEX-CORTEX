import json

from hex_cortex.memory.cortex_agent_runtime_cli import build_parser
from hex_cortex.memory.cortex_agent_runtime_cli import main


def test_agent_cli_parses_model_route() -> None:
    args = build_parser().parse_args(
        [
            "route-task",
            "routine_patch",
            "--context-sensitivity",
            "private",
            "--complexity",
            "medium",
        ]
    )

    assert args.command == "route-task"
    assert args.task_class == "routine_patch"


def test_agent_cli_emits_screen_v2_plan(capsys) -> None:
    code = main(["screen-v2-plan"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"
    assert payload["episode_count"] == 40
    assert payload["transition_count"] == 320
    assert payload["visual_split_identity_present"] is False


def test_agent_cli_correction_plan_is_non_mutating(capsys) -> None:
    code = main(
        [
            "correction-plan",
            "policy_gate_failed",
            "Use spatial patch pooling.",
            "main@abc123",
            "screen_lab_policy_gate",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"
    assert payload["merge_performed"] is False
    assert payload["threshold_reduction_allowed"] is False


def test_agent_cli_train_plan_parser() -> None:
    args = build_parser().parse_args(
        [
            "screen-v2-train-plan",
            "manifest.json",
            "--output",
            "plan.json",
        ]
    )

    assert args.command == "screen-v2-train-plan"
    assert args.minimum_top1_accuracy == 1.0
    assert args.ranking_weight == 1.0
