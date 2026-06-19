from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_environment_sequence import build_environment_sequence_manifest
from hex_cortex.memory.cortex_environment_sequence import ingest_environment_episode
from hex_cortex.memory.cortex_environment_sequence import write_environment_manifest
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records
from hex_cortex.memory.cortex_screen_lab import bootstrap_screen_lab
from hex_cortex.memory.cortex_screen_lab_policy_evaluation import evaluate_screen_lab_policy
from hex_cortex.memory.cortex_screen_lab_policy_evaluation import write_policy_evaluation
from hex_cortex.memory.cortex_world_model_decision_router import (
    WORLD_MODEL_ROUTE_FILENAME,
    bridge_world_model_route_to_planner,
)
from hex_cortex.memory.cortex_world_model_route_guard import route_world_model_decision_guarded


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-env-router")
    commands = parser.add_subparsers(dest="command", required=True)

    bootstrap = commands.add_parser("bootstrap-screen-lab")
    bootstrap.add_argument("--workspace-root", required=True)
    bootstrap.add_argument("--seed", type=int, default=42)
    bootstrap.add_argument("--replace-existing-source", action="store_true")
    bootstrap.add_argument("--operator-approved", action="store_true")
    _add_encoder_options(bootstrap)

    ingest = commands.add_parser("ingest-episode")
    ingest.add_argument("frames_dir")
    ingest.add_argument("actions_jsonl")
    ingest.add_argument("--workspace-root", required=True)
    ingest.add_argument("--dataset-jsonl", required=True)
    ingest.add_argument("--domain", required=True)
    ingest.add_argument("--episode-id", required=True)
    ingest.add_argument("--split", choices=("train", "validation", "test"), required=True)
    ingest.add_argument("--operator-approved", action="store_true")
    _add_encoder_options(ingest)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("dataset_jsonl")
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--min-train-episodes", type=int, default=2)
    manifest.add_argument("--min-validation-episodes", type=int, default=1)
    manifest.add_argument("--min-test-episodes", type=int, default=1)
    manifest.add_argument("--min-train-steps", type=int, default=16)
    manifest.add_argument("--min-validation-steps", type=int, default=4)
    manifest.add_argument("--min-test-steps", type=int, default=4)

    route = commands.add_parser("route")
    route.add_argument("active_registry")
    route.add_argument("current_image")
    route.add_argument("goal_image")
    route.add_argument("actions_json")
    route.add_argument("--environment-root", required=True)
    route.add_argument("--domain", required=True)
    route.add_argument("--profile")
    route.add_argument("--route-store")
    route.add_argument(
        "--output",
        help="Write the latest route as canonical UTF-8 JSON without relying on PowerShell piping.",
    )
    _add_encoder_options(route)

    policy = commands.add_parser("evaluate-policy")
    policy.add_argument("active_registry")
    policy.add_argument("dataset_jsonl")
    policy.add_argument("actions_json")
    policy.add_argument("--environment-root", required=True)
    policy.add_argument("--domain", required=True)
    policy.add_argument("--split", choices=("train", "validation", "test"), default="test")
    policy.add_argument("--minimum-samples", type=int, default=4)
    policy.add_argument("--minimum-top1-accuracy", type=float, default=1.0)
    policy.add_argument("--minimum-positive-improvement-rate", type=float, default=1.0)
    policy.add_argument("--output", required=True)
    _add_encoder_options(policy)

    bridge = commands.add_parser("bridge")
    bridge.add_argument("route_json")
    bridge.add_argument("--profile", required=True)
    bridge.add_argument("--enforce-action-match", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bootstrap-screen-lab":
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        payload = bootstrap_screen_lab(
            workspace_root=Path(args.workspace_root),
            encoder_descriptor=descriptor,
            operator_approved=args.operator_approved,
            seed=args.seed,
            replace_existing_source=args.replace_existing_source,
        )
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "ingest-episode":
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        payload = ingest_environment_episode(
            frames_dir=Path(args.frames_dir),
            actions_jsonl=Path(args.actions_jsonl),
            workspace_root=Path(args.workspace_root),
            dataset_jsonl=Path(args.dataset_jsonl),
            domain=args.domain,
            episode_id=args.episode_id,
            split=args.split,
            encoder_descriptor=descriptor,
            operator_approved=args.operator_approved,
        )
        _emit(payload)
        return 0 if payload.get("status") == "completed" else 2
    if args.command == "manifest":
        try:
            records = load_transition_records(Path(args.dataset_jsonl))
        except (OSError, ValueError) as exc:
            _emit({"status": "blocked", "blockers": [type(exc).__name__]})
            return 2
        payload = build_environment_sequence_manifest(
            records,
            min_train_episodes=args.min_train_episodes,
            min_validation_episodes=args.min_validation_episodes,
            min_test_episodes=args.min_test_episodes,
            min_train_steps=args.min_train_steps,
            min_validation_steps=args.min_validation_steps,
            min_test_steps=args.min_test_steps,
        )
        if payload.get("manifest_allowed") is True:
            write_environment_manifest(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("manifest_allowed") is True else 2
    if args.command == "route":
        candidates = _read_json_list(Path(args.actions_json), "actions")
        if candidates is None:
            return 2
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        profile = Path(args.profile) if args.profile else None
        route_store = Path(args.route_store) if args.route_store else None
        if route_store is None and profile is not None:
            route_store = profile / WORLD_MODEL_ROUTE_FILENAME
        payload = route_world_model_decision_guarded(
            active_registry_path=Path(args.active_registry),
            environment_root=Path(args.environment_root),
            current_image_path=Path(args.current_image),
            goal_image_path=Path(args.goal_image),
            environment_domain=args.domain,
            action_candidates=candidates,
            encoder_descriptor=descriptor,
            profile=profile,
            route_store_path=route_store,
        )
        if args.output:
            _write_json(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("status") == "advisory_ready" else 2
    if args.command == "evaluate-policy":
        candidates = _read_json_list(Path(args.actions_json), "actions")
        if candidates is None:
            return 2
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        payload = evaluate_screen_lab_policy(
            active_registry_path=Path(args.active_registry),
            environment_root=Path(args.environment_root),
            dataset_jsonl=Path(args.dataset_jsonl),
            environment_domain=args.domain,
            action_candidates=candidates,
            encoder_descriptor=descriptor,
            split=args.split,
            minimum_samples=args.minimum_samples,
            minimum_top1_accuracy=args.minimum_top1_accuracy,
            minimum_positive_improvement_rate=args.minimum_positive_improvement_rate,
            decision_router=route_world_model_decision_guarded,
        )
        write_policy_evaluation(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("status") == "policy_ready" else 2
    route_payload = _read_json_object(Path(args.route_json), "route")
    if route_payload is None:
        return 2
    payload = bridge_world_model_route_to_planner(
        profile=Path(args.profile),
        route=route_payload,
        enforce_action_match=args.enforce_action_match,
    )
    _emit(payload)
    return 0 if payload.get("status") == "attached_for_operator_review" else 2


def _add_encoder_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="cpu")


def _read_json_object(path: Path, name: str) -> dict[str, object] | None:
    payload = _read_json_document(path, name)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_object"]})
        return None
    return payload


def _read_json_list(path: Path, name: str) -> list[dict[str, object]] | None:
    payload = _read_json_document(path, name)
    if payload is None:
        return None
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_object_list"]})
        return None
    return payload


def _read_json_document(path: Path, name: str) -> object | None:
    try:
        raw = path.resolve().read_bytes()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        elif raw.startswith(b"\xef\xbb\xbf"):
            text = raw.decode("utf-8-sig")
        else:
            text = raw.decode("utf-8")
        return json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _emit({"status": "blocked", "blockers": [f"{name}_invalid_json"]})
        return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
