from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan
from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_verification_policy import decide_verification_action
from hex_cortex.memory.cortex_verified_execution_runtime import execute_verified_local_loop

_DEFAULT_LEDGER = ".hex-cortex/cognitive/brain-registry.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-loop")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan")
    plan.add_argument("--ledger", default=_DEFAULT_LEDGER)
    plan.add_argument("--gpu-snapshot", required=True)
    plan.add_argument("--task-domain", required=True)
    plan.add_argument(
        "--context-sensitivity",
        choices=("public", "private", "secret"),
        required=True,
    )
    plan.add_argument(
        "--difficulty",
        choices=("low", "medium", "high", "critical"),
        default="medium",
    )
    plan.add_argument("--risk", choices=("low", "medium", "high", "critical"), default="low")
    plan.add_argument("--prior-confidence", type=float)
    plan.add_argument("--maximum-latency-ms", type=float, default=5000.0)
    plan.add_argument("--cost-pressure", type=float, default=0.5)
    plan.add_argument("--target-confidence", type=float, default=0.7)
    plan.add_argument("--remote-allowed", action="store_true")
    plan.add_argument("--benchmark", action="store_true")
    plan.add_argument("--receipt")
    plan.add_argument("--output")

    execute = commands.add_parser("execute-local")
    execute.add_argument("plan_json")
    execute.add_argument("--ledger", default=_DEFAULT_LEDGER)
    execute.add_argument("--gpu-snapshot", required=True)
    execute.add_argument("--instruction-file", required=True)
    execute.add_argument("--prompt-file", required=True)
    execute.add_argument("--context-file")
    execute.add_argument("--model", required=True)
    execute.add_argument("--local-endpoint", default="http://127.0.0.1:11434")
    execute.add_argument("--max-output-tokens", type=int, default=2048)
    execute.add_argument("--timeout-seconds", type=float, default=120.0)
    execute.add_argument("--sample-temperature", type=float, default=0.2)
    execute.add_argument("--ollama-keep-alive", default="2m")
    execute.add_argument("--expected-numeric", type=float)
    execute.add_argument("--receipt")
    execute.add_argument("--operator-approved", action="store_true")
    execute.add_argument("--confirm", default="")

    consensus = commands.add_parser("consensus")
    consensus.add_argument("--samples", required=True)
    consensus.add_argument("--weights")
    consensus.add_argument("--mode", choices=("text", "numeric"), default="text")
    consensus.add_argument("--agreement-threshold", type=float, default=0.5)

    verify = commands.add_parser("verify-next")
    verify.add_argument("--consensus", required=True)
    verify.add_argument("--target-confidence", type=float, default=0.7)
    verify.add_argument("--max-samples", type=int, default=16)
    verify.add_argument("--stronger-brain-available", action="store_true")
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
    return 0 if payload.get("status") not in {"blocked", "failed", "refused"} else 2


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "plan":
        snapshot = _read_object(Path(args.gpu_snapshot))
        receipt = Path(args.receipt) if args.receipt else None
        payload = build_cognitive_loop_plan(
            Path(args.ledger),
            snapshot,
            task_domain=args.task_domain,
            context_sensitivity=args.context_sensitivity,
            difficulty=args.difficulty,
            risk=args.risk,
            prior_confidence=args.prior_confidence,
            maximum_latency_ms=args.maximum_latency_ms,
            cost_pressure=args.cost_pressure,
            remote_allowed=args.remote_allowed,
            target_confidence=args.target_confidence,
            is_benchmark=args.benchmark,
            receipt_path=receipt,
        )
        if args.output:
            _write_json(Path(args.output), payload)
        return payload
    if args.command == "execute-local":
        plan = _read_object(Path(args.plan_json))
        snapshot = _read_object(Path(args.gpu_snapshot))
        instruction = _read_text(Path(args.instruction_file))
        prompt = _read_text(Path(args.prompt_file))
        context = "" if args.context_file is None else _read_text(Path(args.context_file))
        receipt = Path(args.receipt) if args.receipt else None
        return execute_verified_local_loop(
            plan,
            ledger=Path(args.ledger),
            gpu_snapshot=snapshot,
            model=args.model,
            instruction=instruction,
            task_prompt=prompt,
            bounded_context=context,
            local_endpoint=args.local_endpoint,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
            sample_temperature=args.sample_temperature,
            ollama_keep_alive=args.ollama_keep_alive,
            expected_numeric=args.expected_numeric,
            operator_approved=args.operator_approved,
            confirmation=args.confirm,
            receipt_path=receipt,
        )
    if args.command == "consensus":
        samples = _read_list(Path(args.samples), expected=str)
        weights = None
        if args.weights:
            weights = [float(value) for value in _read_list(Path(args.weights))]
        return aggregate_self_consistency(
            samples,
            mode=args.mode,
            agreement_threshold=args.agreement_threshold,
            sample_weights=weights,
        )
    if args.command == "verify-next":
        consensus = _read_object(Path(args.consensus))
        return decide_verification_action(
            consensus,
            target_confidence=args.target_confidence,
            max_samples=args.max_samples,
            stronger_brain_available=args.stronger_brain_available,
        )
    raise ValueError("unknown cognitive loop command")


def _read_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _read_list(path: Path, *, expected: type | None = None) -> list[object]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("JSON payload must be a list")
    if expected is not None and not all(isinstance(item, expected) for item in payload):
        raise ValueError("JSON list contains invalid item types")
    return payload


def _read_text(path: Path) -> str:
    return path.resolve().read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
