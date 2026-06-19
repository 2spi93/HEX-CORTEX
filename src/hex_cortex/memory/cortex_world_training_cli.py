from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_compact_world_model import build_compact_predictor_plan
from hex_cortex.memory.cortex_compact_world_model import predict_with_active_compact_model
from hex_cortex.memory.cortex_compact_world_model import promote_compact_predictor
from hex_cortex.memory.cortex_compact_world_model import train_compact_predictor
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import append_transition_jsonl
from hex_cortex.memory.cortex_observed_transition_dataset import build_transition_dataset_manifest
from hex_cortex.memory.cortex_observed_transition_dataset import capture_observed_transition
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records
from hex_cortex.memory.cortex_observed_transition_dataset import write_transition_manifest
from hex_cortex.memory.cortex_world_model_completion_audit import audit_world_model_completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-world-train")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit")
    audit.add_argument("--project-root", default=".")
    audit.add_argument("--state-root")

    capture = commands.add_parser("capture")
    capture.add_argument("current_image")
    capture.add_argument("next_image")
    capture.add_argument("--comfy-root", required=True)
    capture.add_argument("--action", required=True)
    capture.add_argument("--action-schema", default="brightness,contrast,translate_x,translate_y")
    capture.add_argument("--split", choices=("auto", "train", "validation", "test"), default="auto")
    capture.add_argument("--domain", default="observed_visual_transition_v1")
    capture.add_argument("--dataset-jsonl", required=True)
    _add_encoder_options(capture)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("dataset_jsonl")
    manifest.add_argument("--output", required=True)
    manifest.add_argument("--min-train", type=int, default=8)
    manifest.add_argument("--min-validation", type=int, default=2)
    manifest.add_argument("--min-test", type=int, default=2)

    plan = commands.add_parser("plan")
    plan.add_argument("manifest_path")
    plan.add_argument("--hidden-dim", type=int, default=128)
    plan.add_argument("--epochs", type=int, default=40)
    plan.add_argument("--batch-size", type=int, default=8)
    plan.add_argument("--learning-rate", type=float, default=0.001)
    plan.add_argument("--weight-decay", type=float, default=0.0001)
    plan.add_argument("--seed", type=int, default=42)
    plan.add_argument("--device", default="cpu")
    plan.add_argument("--max-seconds", type=float, default=900.0)
    plan.add_argument("--output", required=True)

    train = commands.add_parser("train")
    train.add_argument("manifest_path")
    train.add_argument("plan_path")
    train.add_argument("--comfy-root", required=True)
    train.add_argument("--output-dir", required=True)
    train.add_argument("--operator-approved", action="store_true")
    _add_encoder_options(train)

    promote = commands.add_parser("promote")
    promote.add_argument("candidate_manifest")
    promote.add_argument("--registry-dir", required=True)
    promote.add_argument("--operator-approved", action="store_true")

    predict = commands.add_parser("predict")
    predict.add_argument("active_registry")
    predict.add_argument("image_path")
    predict.add_argument("--comfy-root", required=True)
    action_group = predict.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--action",
        help="Comma-separated vector. Use --action=-1,0 when the first value is negative.",
    )
    action_group.add_argument(
        "--action-values",
        nargs="+",
        type=float,
        help="Space-separated numeric vector, including negative values: --action-values -1 0",
    )
    _add_encoder_options(predict)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        payload = audit_world_model_completion(
            Path(args.project_root),
            state_root=Path(args.state_root) if args.state_root else None,
        )
        _emit(payload)
        return 0 if payload["architecture_ready"] is True else 2
    if args.command == "capture":
        action = _parse_float_csv(args.action, "action")
        schema = _parse_string_csv(args.action_schema, "action_schema")
        if action is None or schema is None:
            return 2
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        record = capture_observed_transition(
            comfy_root=Path(args.comfy_root),
            current_image_path=Path(args.current_image),
            next_image_path=Path(args.next_image),
            action=action,
            action_schema=schema,
            split=args.split,
            domain=args.domain,
            encoder_descriptor=descriptor,
        )
        if record.get("blockers"):
            _emit(record)
            return 2
        append = append_transition_jsonl(Path(args.dataset_jsonl), record)
        _emit({"record": record, "append": append})
        return 0
    if args.command == "manifest":
        try:
            records = load_transition_records(Path(args.dataset_jsonl))
        except (OSError, ValueError) as exc:
            _emit({"status": "blocked", "blockers": [type(exc).__name__]})
            return 2
        payload = build_transition_dataset_manifest(
            records,
            min_train=args.min_train,
            min_validation=args.min_validation,
            min_test=args.min_test,
        )
        if payload.get("manifest_allowed") is True:
            write_transition_manifest(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("manifest_allowed") is True else 2
    if args.command == "plan":
        manifest = _read_json_object(Path(args.manifest_path), "manifest")
        if manifest is None:
            return 2
        payload = build_compact_predictor_plan(
            manifest=manifest,
            hidden_dim=args.hidden_dim,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            seed=args.seed,
            device=args.device,
            max_seconds=args.max_seconds,
        )
        if payload.get("plan_allowed") is True:
            _write_json(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("plan_allowed") is True else 2
    if args.command == "train":
        manifest = _read_json_object(Path(args.manifest_path), "manifest")
        plan = _read_json_object(Path(args.plan_path), "plan")
        if manifest is None or plan is None:
            return 2
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        payload = train_compact_predictor(
            plan=plan,
            manifest=manifest,
            comfy_root=Path(args.comfy_root),
            encoder_descriptor=descriptor,
            output_dir=Path(args.output_dir),
            operator_approved=args.operator_approved,
        )
        _emit(payload)
        return 0 if payload.get("status") == "trained" else 2
    if args.command == "promote":
        payload = promote_compact_predictor(
            candidate_manifest_path=Path(args.candidate_manifest),
            registry_dir=Path(args.registry_dir),
            operator_approved=args.operator_approved,
        )
        _emit(payload)
        return 0 if payload.get("status") == "promoted" else 2
    if args.action_values is not None:
        action = [float(value) for value in args.action_values]
    else:
        action = _parse_float_csv(args.action, "action")
        if action is None:
            return 2
    descriptor = build_frozen_encoder_descriptor(
        model_ref=args.model_ref,
        pooling=args.pooling,
        device=args.device,
    )
    payload = predict_with_active_compact_model(
        active_registry_path=Path(args.active_registry),
        comfy_root=Path(args.comfy_root),
        image_path=Path(args.image_path),
        action=action,
        encoder_descriptor=descriptor,
    )
    _emit(payload)
    return 0 if payload.get("status") == "predicted" else 2


def _add_encoder_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="cpu")


def _parse_float_csv(raw: str, name: str) -> list[float] | None:
    try:
        values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError:
        _emit({"status": "blocked", "blockers": [f"{name}_invalid_csv"]})
        return None
    if not values:
        _emit({"status": "blocked", "blockers": [f"{name}_empty"]})
        return None
    return values


def _parse_string_csv(raw: str, name: str) -> list[str] | None:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        _emit({"status": "blocked", "blockers": [f"{name}_empty"]})
        return None
    return values


def _read_json_object(path: Path, name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
