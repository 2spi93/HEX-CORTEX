from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_action_discriminative_world_model import (
    build_action_discriminative_plan,
)
from hex_cortex.memory.cortex_action_discriminative_world_model import (
    train_action_discriminative_model,
)
from hex_cortex.memory.cortex_coding_model_router import build_coding_model_catalog
from hex_cortex.memory.cortex_coding_model_router import route_coding_task
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_screen_lab_policy_v2 import bootstrap_screen_lab_policy_v2
from hex_cortex.memory.cortex_screen_lab_policy_v2 import build_screen_lab_policy_v2_specs
from hex_cortex.memory.cortex_self_correction import RepairBudget
from hex_cortex.memory.cortex_self_correction import build_self_correction_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-agent")
    commands = parser.add_subparsers(dest="command", required=True)

    catalog = commands.add_parser("model-catalog")
    catalog.add_argument("--local-endpoint", default="http://127.0.0.1:8080")
    catalog.add_argument("--local-model", default="Qwen3-Coder-30B-A3B-Instruct")
    catalog.add_argument("--remote-provider", default="openai")
    catalog.add_argument("--remote-model", default="gpt-5.5")
    catalog.add_argument("--remote-api-key-ref", default="env:OPENAI_API_KEY")

    route = commands.add_parser("route-task")
    route.add_argument("task_class")
    route.add_argument("--context-sensitivity", choices=("public", "private", "secret"), default="private")
    route.add_argument("--complexity", choices=("low", "medium", "high"), default="medium")
    route.add_argument("--local-unavailable", action="store_true")
    route.add_argument("--remote-available", action="store_true")
    route.add_argument("--operator-allows-remote", action="store_true")

    correction = commands.add_parser("correction-plan")
    correction.add_argument("failure_class")
    correction.add_argument("hypothesis")
    correction.add_argument("baseline_ref")
    correction.add_argument("evaluator_ref")
    correction.add_argument("--max-attempts", type=int, default=2)
    correction.add_argument("--max-files-changed", type=int, default=12)
    correction.add_argument("--max-runtime-seconds", type=int, default=1800)

    v2_plan = commands.add_parser("screen-v2-plan")
    v2_plan.add_argument("--train-episodes", type=int, default=24)
    v2_plan.add_argument("--validation-episodes", type=int, default=8)
    v2_plan.add_argument("--test-episodes", type=int, default=8)
    v2_plan.add_argument("--steps-per-episode", type=int, default=8)
    v2_plan.add_argument("--seed", type=int, default=42)

    v2_bootstrap = commands.add_parser("screen-v2-bootstrap")
    v2_bootstrap.add_argument("--workspace-root", required=True)
    v2_bootstrap.add_argument("--seed", type=int, default=42)
    v2_bootstrap.add_argument("--replace-existing-source", action="store_true")
    v2_bootstrap.add_argument("--operator-approved", action="store_true")
    _add_encoder_options(v2_bootstrap)

    v2_train_plan = commands.add_parser("screen-v2-train-plan")
    v2_train_plan.add_argument("manifest_json")
    v2_train_plan.add_argument("--output", required=True)
    v2_train_plan.add_argument("--hidden-dim", type=int, default=128)
    v2_train_plan.add_argument("--epochs", type=int, default=100)
    v2_train_plan.add_argument("--batch-size", type=int, default=16)
    v2_train_plan.add_argument("--learning-rate", type=float, default=0.001)
    v2_train_plan.add_argument("--weight-decay", type=float, default=0.0001)
    v2_train_plan.add_argument("--ranking-margin", type=float, default=0.0001)
    v2_train_plan.add_argument("--ranking-weight", type=float, default=1.0)
    v2_train_plan.add_argument("--minimum-top1-accuracy", type=float, default=1.0)
    v2_train_plan.add_argument("--seed", type=int, default=42)
    v2_train_plan.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="cpu")
    v2_train_plan.add_argument("--max-seconds", type=float, default=1800.0)

    v2_train = commands.add_parser("screen-v2-train")
    v2_train.add_argument("manifest_json")
    v2_train.add_argument("plan_json")
    v2_train.add_argument("--environment-root", required=True)
    v2_train.add_argument("--output-dir", required=True)
    v2_train.add_argument("--operator-approved", action="store_true")
    _add_encoder_options(v2_train)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "model-catalog":
        try:
            payload = build_coding_model_catalog(
                local_endpoint=args.local_endpoint,
                local_model=args.local_model,
                remote_provider=args.remote_provider,
                remote_model=args.remote_model,
                remote_api_key_ref=args.remote_api_key_ref,
            )
        except ValueError as exc:
            payload = {"status": "blocked", "blockers": [str(exc)]}
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "route-task":
        payload = route_coding_task(
            task_class=args.task_class,
            context_sensitivity=args.context_sensitivity,
            complexity=args.complexity,
            local_available=not args.local_unavailable,
            remote_available=args.remote_available,
            operator_allows_remote=args.operator_allows_remote,
        )
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "correction-plan":
        payload = build_self_correction_plan(
            failure_class=args.failure_class,
            hypothesis=args.hypothesis,
            baseline_ref=args.baseline_ref,
            evaluator_ref=args.evaluator_ref,
            budget=RepairBudget(
                max_attempts=args.max_attempts,
                max_files_changed=args.max_files_changed,
                max_runtime_seconds=args.max_runtime_seconds,
            ),
        )
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "screen-v2-plan":
        try:
            specs = build_screen_lab_policy_v2_specs(
                train_episodes=args.train_episodes,
                validation_episodes=args.validation_episodes,
                test_episodes=args.test_episodes,
                steps_per_episode=args.steps_per_episode,
                seed=args.seed,
            )
            payload = {
                "plan_type": "screen_lab_policy_v2_data_plan",
                "status": "ready",
                "episode_count": len(specs),
                "transition_count": sum(len(row["actions"]) for row in specs),
                "split_episode_counts": {
                    split: sum(row["split"] == split for row in specs)
                    for split in ("train", "validation", "test")
                },
                "action_balance_by_construction": True,
                "visual_split_identity_present": False,
                "generation_performed": False,
                "next_action": "bootstrap_screen_lab_policy_v2",
            }
        except ValueError as exc:
            payload = {"status": "blocked", "blockers": [str(exc)]}
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "screen-v2-bootstrap":
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        payload = bootstrap_screen_lab_policy_v2(
            workspace_root=Path(args.workspace_root),
            encoder_descriptor=descriptor,
            operator_approved=args.operator_approved,
            seed=args.seed,
            replace_existing_source=args.replace_existing_source,
        )
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "screen-v2-train-plan":
        manifest = _read_json_object(Path(args.manifest_json), "manifest")
        if manifest is None:
            return 2
        payload = build_action_discriminative_plan(
            manifest=manifest,
            hidden_dim=args.hidden_dim,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            ranking_margin=args.ranking_margin,
            ranking_weight=args.ranking_weight,
            minimum_top1_accuracy=args.minimum_top1_accuracy,
            seed=args.seed,
            device=args.device,
            max_seconds=args.max_seconds,
        )
        if payload.get("plan_allowed") is True:
            _write_json(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("plan_allowed") is True else 2
    manifest = _read_json_object(Path(args.manifest_json), "manifest")
    plan = _read_json_object(Path(args.plan_json), "plan")
    if manifest is None or plan is None:
        return 2
    descriptor = build_frozen_encoder_descriptor(
        model_ref=args.model_ref,
        pooling=args.pooling,
        device=args.device,
    )
    payload = train_action_discriminative_model(
        plan=plan,
        manifest=manifest,
        environment_root=Path(args.environment_root),
        encoder_descriptor=descriptor,
        output_dir=Path(args.output_dir),
        operator_approved=args.operator_approved,
    )
    _emit(payload)
    return 0 if payload.get("status") == "trained" else 2


def _add_encoder_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="cpu")


def _read_json_object(path: Path, name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _emit({"status": "blocked", "blockers": [f"{name}_invalid_json"]})
        return None
    if not isinstance(payload, dict):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_object"]})
        return None
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
