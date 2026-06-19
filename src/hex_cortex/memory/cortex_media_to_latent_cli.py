from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_media_to_latent_pipeline import append_receipt_jsonl
from hex_cortex.memory.cortex_media_to_latent_pipeline import build_existing_output_receipt
from hex_cortex.memory.cortex_media_to_latent_pipeline import run_media_to_latent_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-media-latent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_image = subparsers.add_parser("from-image")
    from_image.add_argument("image_path")
    from_image.add_argument("--comfy-root", required=True)
    from_image.add_argument("--source-receipt-hash")
    _add_pipeline_options(from_image)

    from_receipt = subparsers.add_parser("from-receipt")
    from_receipt.add_argument("execution_receipt_path")
    from_receipt.add_argument("--comfy-root", required=True)
    from_receipt.add_argument("--output-index", type=int, default=0)
    _add_pipeline_options(from_receipt)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "from-image":
        source_receipt = build_existing_output_receipt(
            comfy_root=Path(args.comfy_root),
            image_path=Path(args.image_path),
            source_receipt_hash=args.source_receipt_hash,
        )
        output_index = 0
    else:
        source_receipt = _read_json_object(Path(args.execution_receipt_path))
        if source_receipt is None:
            return 2
        output_index = args.output_index
    action = _parse_action(args.action)
    if action is None:
        return 2
    descriptor = build_frozen_encoder_descriptor(
        model_ref=args.model_ref,
        pooling=args.pooling,
        device=args.device,
    )
    receipt = run_media_to_latent_pipeline(
        source_receipt=source_receipt,
        comfy_root=Path(args.comfy_root),
        encoder_descriptor=descriptor,
        action=action,
        observed_image_path=(Path(args.observed_image) if args.observed_image else None),
        surprise_threshold=args.surprise_threshold,
        baseline_scale=args.baseline_scale,
        allow_model_download=args.allow_model_download,
        operator_approved=args.operator_approved,
        output_index=output_index,
    )
    if args.receipt_jsonl and receipt.get("pipeline_completed") is True:
        append_receipt_jsonl(Path(args.receipt_jsonl), receipt)
    _emit(receipt, pretty=args.pretty)
    return 0 if receipt.get("pipeline_completed") is True else 2


def _add_pipeline_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--action", default="0,0,0,0")
    parser.add_argument("--observed-image")
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    parser.add_argument("--surprise-threshold", type=float, default=0.25)
    parser.add_argument("--baseline-scale", type=float, default=0.01)
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--receipt-jsonl")
    parser.add_argument("--pretty", action="store_true")


def _parse_action(raw: str) -> list[float] | None:
    try:
        values = [float(value.strip()) for value in raw.split(",") if value.strip()]
    except ValueError:
        _emit(
            {
                "status": "blocked",
                "blockers": ["action_invalid_csv"],
                "next_action": "provide_comma_separated_action_values",
            }
        )
        return None
    if not values:
        _emit(
            {
                "status": "blocked",
                "blockers": ["action_empty"],
                "next_action": "provide_comma_separated_action_values",
            }
        )
        return None
    return values


def _read_json_object(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _emit(
            {
                "status": "blocked",
                "blockers": ["execution_receipt_invalid_json"],
                "next_action": "repair_execution_receipt_file",
            }
        )
        return None
    if not isinstance(payload, dict):
        _emit(
            {
                "status": "blocked",
                "blockers": ["execution_receipt_must_be_object"],
                "next_action": "repair_execution_receipt_file",
            }
        )
        return None
    return payload


def _emit(payload: dict[str, object], *, pretty: bool = False) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2 if pretty else None))


if __name__ == "__main__":
    raise SystemExit(main())
