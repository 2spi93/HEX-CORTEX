from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_latent_experiment import build_latent_experiment_receipt
from hex_cortex.memory.cortex_latent_lab import build_latent_lab_spec
from hex_cortex.memory.cortex_media_runtime import orchestrate_media_runtime
from hex_cortex.memory.cortex_next_wave_audit import audit_next_wave
from hex_cortex.memory.cortex_world_model_eval import evaluate_world_model_candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-wave")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--project-root", default=".")

    media = subparsers.add_parser("media-plan")
    media.add_argument("output_id", choices=(
        "generate_image",
        "generate_video",
        "generate_3d_scene",
        "render_3d_asset",
    ))
    media.add_argument("prompt")
    media.add_argument("--network", action="store_true")
    media.add_argument("--operator-approved", action="store_true")
    media.add_argument("--workflow-json", default="{}")

    latent = subparsers.add_parser("latent-spec")
    latent.add_argument("--latent-dim", type=int, default=8)
    latent.add_argument("--action-dim", type=int, default=4)
    latent.add_argument("--horizons", default="1,4,16")

    experiment = subparsers.add_parser("latent-demo")
    experiment.add_argument("--latent-dim", type=int, default=2)
    experiment.add_argument("--action-dim", type=int, default=1)

    evaluation = subparsers.add_parser("evaluate-candidate")
    evaluation.add_argument("baseline_json")
    evaluation.add_argument("candidate_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit":
        payload = audit_next_wave(Path(args.project_root))
        _emit(payload)
        return 0 if payload["architecture_ready"] is True else 2
    if args.command == "media-plan":
        workflow = _json_object(args.workflow_json, "workflow_json")
        if workflow is None:
            return 2
        payload = orchestrate_media_runtime(
            output_id=args.output_id,
            prompt=args.prompt,
            execute_network=args.network,
            operator_approved=args.operator_approved,
            workflow=workflow,
        )
        _emit(payload)
        return 0 if payload["status"] in {"planned", "submitted"} else 2
    if args.command == "latent-spec":
        try:
            horizons = [int(value.strip()) for value in args.horizons.split(",") if value.strip()]
        except ValueError:
            _emit({"status": "blocked", "blockers": ["horizons_invalid"]})
            return 2
        payload = build_latent_lab_spec(
            latent_dim=args.latent_dim,
            action_dim=args.action_dim,
            horizons=horizons,
        )
        _emit(payload)
        return 0 if payload["spec_allowed"] is True else 2
    if args.command == "latent-demo":
        spec = build_latent_lab_spec(
            latent_dim=args.latent_dim,
            action_dim=args.action_dim,
            horizons=[1],
        )
        initial = [0.0] * args.latent_dim
        action = [1.0] * args.action_dim
        weights = [
            [0.1 * (row_index + 1) for _ in range(args.action_dim)]
            for row_index in range(args.latent_dim)
        ]
        observed = [sum(row) for row in weights]
        payload = build_latent_experiment_receipt(
            spec=spec,
            initial_state=initial,
            actions=[action],
            weights=weights,
            observed_final_state=observed,
        )
        _emit(payload)
        return 0 if payload["experiment_allowed"] is True else 2
    if args.command == "evaluate-candidate":
        baseline = _numeric_object(args.baseline_json, "baseline_json")
        candidate = _numeric_object(args.candidate_json, "candidate_json")
        if baseline is None or candidate is None:
            return 2
        payload = evaluate_world_model_candidate(
            baseline=baseline,
            candidate=candidate,
        )
        _emit(payload)
        return 0 if payload["evaluation_allowed"] is True else 2
    _emit({"status": "blocked", "blockers": ["unknown_command"]})
    return 2


def _json_object(raw: str, name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit({"status": "blocked", "blockers": [f"{name}_invalid"]})
        return None
    if not isinstance(payload, dict):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_object"]})
        return None
    return payload


def _numeric_object(raw: str, name: str) -> dict[str, float] | None:
    payload = _json_object(raw, name)
    if payload is None:
        return None
    if not all(isinstance(key, str) and isinstance(value, int | float) for key, value in payload.items()):
        _emit({"status": "blocked", "blockers": [f"{name}_must_be_numeric_object"]})
        return None
    return {key: float(value) for key, value in payload.items()}


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
