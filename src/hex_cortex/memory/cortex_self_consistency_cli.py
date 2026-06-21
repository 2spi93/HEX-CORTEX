"""CLI for the self-consistency verification layer.

Cold-mode operable: it reads *pre-collected* samples (or skeptic verdicts) from
a JSON file and produces a consensus / verification receipt. It performs no
model call itself — sampling is the caller's responsibility (autonomy ladder
step 4+). This keeps the tool usable for dry-run contracts and replay.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_self_consistency import aggregate_verification_votes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-self-consistency")
    commands = parser.add_subparsers(dest="command", required=True)

    vote = commands.add_parser("vote", help="majority-vote over a JSON array of answer samples")
    vote.add_argument("--samples", required=True, help="path to a JSON array of answer strings")
    vote.add_argument("--mode", choices=("text", "numeric"), default="text")
    vote.add_argument("--agreement-threshold", type=float, default=0.5)
    vote.add_argument(
        "--weights",
        default=None,
        help="optional path to a JSON array of per-sample weights (e.g. brain reliability)",
    )
    vote.add_argument("--receipt", default=None)

    verify = commands.add_parser("verify", help="aggregate a JSON array of skeptic verdicts")
    verify.add_argument("--verdicts", required=True, help="path to a JSON array of {refuted, lens}")
    verify.add_argument("--refute-threshold", type=float, default=0.5)
    verify.add_argument("--receipt", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _dispatch(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        payload = {
            "status": "blocked",
            "error_type": type(exc).__name__,
            "blockers": [str(exc)],
        }
        print(json.dumps(payload, sort_keys=True, indent=2))
        return 2
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") in {"verified", "survived"} else 1


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    receipt = Path(args.receipt) if args.receipt else None
    if args.command == "vote":
        samples = _load_json_array(Path(args.samples))
        weights = None
        if args.weights:
            weights = [float(item) for item in _load_json_array(Path(args.weights))]
        return aggregate_self_consistency(
            [str(item) for item in samples],
            mode=args.mode,
            agreement_threshold=args.agreement_threshold,
            sample_weights=weights,
            receipt_path=receipt,
        )
    if args.command == "verify":
        verdicts = _load_json_array(Path(args.verdicts))
        return aggregate_verification_votes(
            [dict(item) for item in verdicts],
            refute_threshold=args.refute_threshold,
            receipt_path=receipt,
        )
    raise ValueError("unknown self-consistency command")


def _load_json_array(path: Path) -> list[object]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("input file must contain a JSON array")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
