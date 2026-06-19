from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_comfyui_operational import bind_workflow
from hex_cortex.memory.cortex_comfyui_operational import import_workflow_bundle
from hex_cortex.memory.cortex_comfyui_operational import load_workflow_bundle
from hex_cortex.memory.cortex_comfyui_operational import probe_comfyui
from hex_cortex.memory.cortex_comfyui_operational import submit_and_wait
from hex_cortex.memory.cortex_comfyui_operational import validate_api_workflow
from hex_cortex.memory.cortex_frozen_encoder import build_encoder_plan
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.cortex_frozen_encoder import probe_frozen_encoder_runtime
from hex_cortex.memory.cortex_operational_media_audit import audit_operational_media_encoder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-operational")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--project-root", default=".")

    probe = subparsers.add_parser("comfyui-probe")
    probe.add_argument("--endpoint", default="http://127.0.0.1:8188")

    validate = subparsers.add_parser("workflow-validate")
    validate.add_argument("workflow_path")
    validate.add_argument("--allow-placeholders", action="store_true")

    workflow_import = subparsers.add_parser("workflow-import")
    workflow_import.add_argument("workflow_path")
    workflow_import.add_argument("profile_path")
    workflow_import.add_argument("--registry-root", default=".hex-cortex/comfyui-workflows")
    workflow_import.add_argument("--operator-approved", action="store_true")

    workflow_run = subparsers.add_parser("workflow-run")
    workflow_run.add_argument("workflow_id")
    workflow_run.add_argument("values_json")
    workflow_run.add_argument("--registry-root", default=".hex-cortex/comfyui-workflows")
    workflow_run.add_argument("--endpoint", default="http://127.0.0.1:8188")
    workflow_run.add_argument("--timeout-seconds", type=float, default=120.0)
    workflow_run.add_argument("--operator-approved", action="store_true")

    encoder_plan = subparsers.add_parser("encoder-plan")
    encoder_plan.add_argument("image_path")
    _add_encoder_options(encoder_plan)

    encoder_probe = subparsers.add_parser("encoder-probe")
    _add_encoder_options(encoder_probe, include_image=False)
    encoder_probe.add_argument(
        "--model-cache-present",
        choices=("true", "false", "unknown"),
        default="unknown",
    )

    encoder_run = subparsers.add_parser("encoder-run")
    encoder_run.add_argument("image_path")
    _add_encoder_options(encoder_run)
    encoder_run.add_argument("--allow-model-download", action="store_true")
    encoder_run.add_argument("--operator-approved", action="store_true")
    encoder_run.add_argument("--include-vector", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        payload = audit_operational_media_encoder(Path(args.project_root))
        _emit(payload)
        return 0 if payload["architecture_ready"] is True else 2
    if args.command == "comfyui-probe":
        payload = probe_comfyui(args.endpoint)
        _emit(payload)
        return 0 if payload["healthy"] is True else 2
    if args.command == "workflow-validate":
        workflow = _read_json_object(Path(args.workflow_path), "workflow")
        if workflow is None:
            return 2
        payload = validate_api_workflow(
            workflow,
            allow_placeholders=args.allow_placeholders,
        )
        _emit(payload)
        return 0 if payload["workflow_valid"] is True else 2
    if args.command == "workflow-import":
        profile = _read_json_object(Path(args.profile_path), "profile")
        if profile is None:
            return 2
        bindings = profile.get("bindings")
        if not isinstance(bindings, dict):
            _emit({"status": "blocked", "blockers": ["profile_bindings_invalid"]})
            return 2
        payload = import_workflow_bundle(
            source_path=Path(args.workflow_path),
            registry_root=Path(args.registry_root),
            workflow_id=str(profile.get("workflow_id", "")),
            capability=str(profile.get("capability", "")),
            bindings=bindings,
            allow_placeholders=profile.get("template_mode") is True,
            operator_approved=args.operator_approved,
        )
        _emit(payload)
        return 0 if payload["imported"] is True else 2
    if args.command == "workflow-run":
        values = _parse_json_object(args.values_json, "values")
        if values is None:
            return 2
        try:
            workflow, manifest = load_workflow_bundle(
                Path(args.registry_root),
                args.workflow_id,
            )
            bound = bind_workflow(workflow, manifest, values)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _emit(
                {
                    "status": "blocked",
                    "blockers": [type(exc).__name__],
                    "next_action": "repair_workflow_bundle_or_bindings",
                }
            )
            return 2
        payload = submit_and_wait(
            endpoint=args.endpoint,
            workflow=bound,
            operator_approved=args.operator_approved,
            timeout_seconds=args.timeout_seconds,
        )
        _emit(payload)
        return 0 if payload["status"] == "completed" else 2
    if args.command in {"encoder-plan", "encoder-probe", "encoder-run"}:
        descriptor = build_frozen_encoder_descriptor(
            model_ref=args.model_ref,
            pooling=args.pooling,
            device=args.device,
        )
        if args.command == "encoder-plan":
            payload = build_encoder_plan(
                descriptor=descriptor,
                image_path=Path(args.image_path),
            )
            _emit(payload)
            return 0 if payload["plan_allowed"] is True else 2
        if args.command == "encoder-probe":
            cache_state = {
                "true": True,
                "false": False,
                "unknown": None,
            }[args.model_cache_present]
            payload = probe_frozen_encoder_runtime(
                descriptor,
                model_cache_present=cache_state,
            )
            _emit(payload)
            return 0 if payload["runtime_ready"] is True else 2
        payload = encode_image_to_latent(
            descriptor=descriptor,
            image_path=Path(args.image_path),
            allow_model_download=args.allow_model_download,
            operator_approved=args.operator_approved,
            include_vector=args.include_vector,
        )
        _emit(payload)
        return 0 if payload.get("encoded") is True else 2
    _emit({"status": "blocked", "blockers": ["unknown_command"]})
    return 2


def _add_encoder_options(parser: argparse.ArgumentParser, *, include_image: bool = True) -> None:
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")


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


def _parse_json_object(raw: str, name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit({"status": "blocked", "blockers": [f"{name}_invalid_json"]})
        return None
    if not isinstance(payload, dict):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_object"]})
        return None
    return payload


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
