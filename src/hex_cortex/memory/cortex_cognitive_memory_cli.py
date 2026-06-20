from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_memory import append_causal_intervention
from hex_cortex.memory.cortex_cognitive_memory import append_competency_baseline
from hex_cortex.memory.cortex_cognitive_memory import append_skill_graph_node
from hex_cortex.memory.cortex_cognitive_memory import project_adapter_registry
from hex_cortex.memory.cortex_cognitive_memory import project_skill_graph
from hex_cortex.memory.cortex_cognitive_memory import register_adapter_candidate
from hex_cortex.memory.cortex_cognitive_memory import transition_adapter_status

_BASELINE_LEDGER = ".hex-cortex/cognitive/competency-baselines.jsonl"
_INTERVENTION_LEDGER = ".hex-cortex/cognitive/causal-interventions.jsonl"
_SKILL_LEDGER = ".hex-cortex/cognitive/skill-graph.jsonl"
_ADAPTER_LEDGER = ".hex-cortex/cognitive/adapter-registry.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-memory")
    commands = parser.add_subparsers(dest="command", required=True)

    baseline = commands.add_parser("baseline")
    baseline.add_argument("--ledger", default=_BASELINE_LEDGER)
    baseline.add_argument("--model-id", required=True)
    baseline.add_argument("--suite-ref", required=True)
    baseline.add_argument("--metrics-json", required=True)
    baseline.add_argument("--critical", default="")

    intervention = commands.add_parser("intervention")
    intervention.add_argument("--ledger", default=_INTERVENTION_LEDGER)
    intervention.add_argument("--residual-signature", required=True)
    intervention.add_argument("--intervention-id", required=True)
    intervention.add_argument("--control-ref", required=True)
    intervention.add_argument("--treatment-ref", required=True)
    intervention.add_argument("--verifier-ref", required=True)
    intervention.add_argument("--outcome-delta", type=float, required=True)
    intervention.add_argument("--verified", action="store_true")

    skill = commands.add_parser("skill-add")
    skill.add_argument("--ledger", default=_SKILL_LEDGER)
    skill.add_argument("--skill-id", required=True)
    skill.add_argument("--domain", required=True)
    skill.add_argument("--source-residual-signature", required=True)
    skill.add_argument("--dependencies", default="")
    skill.add_argument("--verification-ref", required=True)
    skill.add_argument("--status", choices=("candidate", "active", "revoked"), default="candidate")

    skill_graph = commands.add_parser("skill-graph")
    skill_graph.add_argument("--ledger", default=_SKILL_LEDGER)

    adapter = commands.add_parser("adapter-register")
    adapter.add_argument("--ledger", default=_ADAPTER_LEDGER)
    adapter.add_argument("--adapter-id", required=True)
    adapter.add_argument("--base-model-id", required=True)
    adapter.add_argument("--skill-id", required=True)
    adapter.add_argument("--plan-hash", required=True)
    adapter.add_argument("--checkpoint-hash", required=True)
    adapter.add_argument("--reversible", action="store_true")

    transition = commands.add_parser("adapter-transition")
    transition.add_argument("--ledger", default=_ADAPTER_LEDGER)
    transition.add_argument("--adapter-id", required=True)
    transition.add_argument("--new-status", required=True)
    transition.add_argument("--evaluation-hash", required=True)
    transition.add_argument("--operator-approved", action="store_true")

    adapter_graph = commands.add_parser("adapter-registry")
    adapter_graph.add_argument("--ledger", default=_ADAPTER_LEDGER)
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
    return 0 if payload.get("status") not in {"blocked", "rejected"} else 2


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "baseline":
        return append_competency_baseline(
            Path(args.ledger),
            model_id=args.model_id,
            suite_ref=args.suite_ref,
            metrics=_numeric_mapping(args.metrics_json),
            critical_competencies=_csv(args.critical),
        )
    if args.command == "intervention":
        return append_causal_intervention(
            Path(args.ledger),
            residual_signature=args.residual_signature,
            intervention_id=args.intervention_id,
            control_ref=args.control_ref,
            treatment_ref=args.treatment_ref,
            verifier_ref=args.verifier_ref,
            outcome_delta=args.outcome_delta,
            verified=args.verified,
        )
    if args.command == "skill-add":
        return append_skill_graph_node(
            Path(args.ledger),
            skill_id=args.skill_id,
            domain=args.domain,
            source_residual_signature=args.source_residual_signature,
            dependencies=_csv(args.dependencies),
            verification_ref=args.verification_ref,
            status=args.status,
        )
    if args.command == "skill-graph":
        return project_skill_graph(Path(args.ledger))
    if args.command == "adapter-register":
        return register_adapter_candidate(
            Path(args.ledger),
            adapter_id=args.adapter_id,
            base_model_id=args.base_model_id,
            skill_id=args.skill_id,
            plan_hash=args.plan_hash,
            checkpoint_hash=args.checkpoint_hash,
            reversible=args.reversible,
        )
    if args.command == "adapter-transition":
        return transition_adapter_status(
            Path(args.ledger),
            adapter_id=args.adapter_id,
            new_status=args.new_status,
            evaluation_hash=args.evaluation_hash,
            operator_approved=args.operator_approved,
        )
    if args.command == "adapter-registry":
        return project_adapter_registry(Path(args.ledger))
    raise ValueError("unknown cognitive memory command")


def _numeric_mapping(raw: str) -> dict[str, float]:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, int | float)
        for key, value in payload.items()
    ):
        raise ValueError("metrics_json must be a numeric JSON object")
    return {key: float(value) for key, value in payload.items()}


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
