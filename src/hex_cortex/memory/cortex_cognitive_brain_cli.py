from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_brain_registration_config import load_registration_config
from hex_cortex.memory.cortex_brain_registration_config import write_registration_template
from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry
from hex_cortex.memory.cortex_cognitive_brain_registry import select_cognitive_brain

_DEFAULT_LEDGER = ".hex-cortex/cognitive/brain-registry.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-brains")
    commands = parser.add_subparsers(dest="command", required=True)

    template = commands.add_parser("template")
    template.add_argument("--output", required=True)
    template.add_argument("--platform", choices=("windows", "kali", "linux"), required=True)
    template.add_argument("--overwrite", action="store_true")

    register_file = commands.add_parser("register-file")
    register_file.add_argument("--config", required=True)
    register_file.add_argument("--ledger", default=_DEFAULT_LEDGER)

    register = commands.add_parser("register")
    register.add_argument("--ledger", default=_DEFAULT_LEDGER)
    register.add_argument("--brain-id", required=True)
    register.add_argument("--model-id", required=True)
    register.add_argument("--model-family", required=True)
    register.add_argument("--runtime-id", required=True)
    register.add_argument("--node-id", required=True)
    register.add_argument(
        "--provider-scope",
        choices=("local", "private_remote", "metered_remote"),
        required=True,
    )
    register.add_argument("--domain-scores-json", required=True)
    register.add_argument("--reliability-score", type=float, required=True)
    register.add_argument("--latency-ms", type=float, required=True)
    register.add_argument("--normalized-cost", type=float, required=True)
    register.add_argument("--baseline-hash", required=True)
    register.add_argument("--parameter-class", default="unknown")
    register.add_argument("--quantization", default="unknown")
    register.add_argument("--unavailable", action="store_true")
    register.add_argument("--operator-approved", action="store_true")

    listing = commands.add_parser("list")
    listing.add_argument("--ledger", default=_DEFAULT_LEDGER)

    select = commands.add_parser("select")
    select.add_argument("--ledger", default=_DEFAULT_LEDGER)
    select.add_argument("--task-domain", required=True)
    select.add_argument(
        "--context-sensitivity",
        choices=("public", "private", "secret"),
        required=True,
    )
    select.add_argument("--maximum-latency-ms", type=float, required=True)
    select.add_argument("--cost-pressure", type=float, required=True)
    select.add_argument("--remote-allowed", action="store_true")
    select.add_argument("--minimum-acceptable-score", type=float, default=0.55)
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
    return 0 if payload.get("status") != "blocked" else 2


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "template":
        return write_registration_template(
            Path(args.output),
            platform_name=args.platform,
            overwrite=args.overwrite,
        )
    if args.command == "register-file":
        config = load_registration_config(Path(args.config))
        payload = append_brain_phenotype(
            Path(args.ledger),
            brain_id=str(config["brain_id"]),
            model_id=str(config["model_id"]),
            model_family=str(config["model_family"]),
            runtime_id=str(config["runtime_id"]),
            node_id=str(config["node_id"]),
            provider_scope=str(config["provider_scope"]),
            domain_scores={
                str(key): float(value)
                for key, value in dict(config["domain_scores"]).items()
            },
            reliability_score=float(config["reliability_score"]),
            latency_ms=float(config["latency_ms"]),
            normalized_cost=float(config["normalized_cost"]),
            baseline_hash=str(config["baseline_hash"]),
            parameter_class=str(config["parameter_class"]),
            quantization=str(config["quantization"]),
            available=config.get("available") is True,
        )
        payload["operator_approved"] = True
        payload["registration_source"] = "validated_config_file"
        return payload
    if args.command == "register":
        if not args.operator_approved:
            raise ValueError("operator approval required")
        payload = append_brain_phenotype(
            Path(args.ledger),
            brain_id=args.brain_id,
            model_id=args.model_id,
            model_family=args.model_family,
            runtime_id=args.runtime_id,
            node_id=args.node_id,
            provider_scope=args.provider_scope,
            domain_scores=_numeric_mapping(args.domain_scores_json),
            reliability_score=args.reliability_score,
            latency_ms=args.latency_ms,
            normalized_cost=args.normalized_cost,
            baseline_hash=args.baseline_hash,
            parameter_class=args.parameter_class,
            quantization=args.quantization,
            available=not args.unavailable,
        )
        payload["operator_approved"] = True
        return payload
    if args.command == "list":
        return project_brain_registry(Path(args.ledger))
    if args.command == "select":
        return select_cognitive_brain(
            Path(args.ledger),
            task_domain=args.task_domain,
            context_sensitivity=args.context_sensitivity,
            maximum_latency_ms=args.maximum_latency_ms,
            cost_pressure=args.cost_pressure,
            remote_allowed=args.remote_allowed,
            minimum_acceptable_score=args.minimum_acceptable_score,
        )
    raise ValueError("unknown brain registry command")


def _numeric_mapping(raw: str) -> dict[str, float]:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, int | float)
        for key, value in payload.items()
    ):
        raise ValueError("domain_scores_json must be a numeric JSON object")
    return {key: float(value) for key, value in payload.items()}


if __name__ == "__main__":
    raise SystemExit(main())
