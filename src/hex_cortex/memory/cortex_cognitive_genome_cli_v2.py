from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_cognitive_genome import build_cr_jepa_v0_manifest
from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision
from hex_cortex.memory.cortex_cognitive_genome import build_mutation_plan
from hex_cortex.memory.cortex_cognitive_genome import build_profile_council
from hex_cortex.memory.cortex_cognitive_genome import build_skill_candidate
from hex_cortex.memory.cortex_cognitive_genome import evaluate_mutation_candidate
from hex_cortex.memory.cortex_cognitive_residuals import append_cognitive_residual
from hex_cortex.memory.cortex_cognitive_residuals import project_residual_topology

_DEFAULT_GENOME = "config/cognitive_genome_v1.json"
_DEFAULT_LEDGER = ".hex-cortex/cognitive/residual-ledger.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-genome")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit")
    audit.add_argument("--genome", default=_DEFAULT_GENOME)

    residual = commands.add_parser("residual")
    residual.add_argument("--ledger", default=_DEFAULT_LEDGER)
    residual.add_argument("--model-id", required=True)
    residual.add_argument("--model-family", required=True)
    residual.add_argument("--domain", required=True)
    residual.add_argument("--context-signature", required=True)
    residual.add_argument("--state-ref", required=True)
    residual.add_argument("--predicted-ref", required=True)
    residual.add_argument("--observed-ref", required=True)
    residual.add_argument("--failure-class", required=True)
    residual.add_argument("--residual-magnitude", type=float, required=True)
    residual.add_argument("--profiles", default="")
    residual.add_argument("--tools", default="")
    residual.add_argument("--correction-ref")
    residual.add_argument("--correction-verified", action="store_true")
    residual.add_argument("--causal-intervention-verified", action="store_true")
    residual.add_argument("--best-corrective-intervention")

    topology = commands.add_parser("topology")
    topology.add_argument("--ledger", default=_DEFAULT_LEDGER)

    skill = commands.add_parser("skill-candidate")
    skill.add_argument("--topology-json", required=True)
    skill.add_argument("--residual-signature", required=True)
    skill.add_argument("--skill-id", required=True)
    skill.add_argument("--domain", required=True)

    council = commands.add_parser("council")
    council.add_argument("--failure-class", required=True)
    council.add_argument("--novelty", type=float, required=True)
    council.add_argument("--uncertainty", type=float, required=True)
    council.add_argument("--mutation-requested", action="store_true")

    homeostasis = commands.add_parser("homeostasis")
    homeostasis.add_argument("--uncertainty", type=float, required=True)
    homeostasis.add_argument("--recurrence-count", type=int, required=True)
    homeostasis.add_argument("--deterministic-verification-available", action="store_true")
    homeostasis.add_argument("--local-verification-failed", action="store_true")
    homeostasis.add_argument("--cost-pressure", type=float, required=True)
    homeostasis.add_argument("--regression-risk", type=float, required=True)

    mutation = commands.add_parser("mutation-plan")
    mutation.add_argument("--skill-candidate-hash", required=True)
    mutation.add_argument("--mutation-level", required=True)
    mutation.add_argument("--baseline-ref", required=True)
    mutation.add_argument("--evaluator-ref", required=True)
    mutation.add_argument("--revocation-ref", required=True)

    evaluation = commands.add_parser("mutation-evaluate")
    evaluation.add_argument("--plan-hash", required=True)
    evaluation.add_argument("--critical-deltas-json", default="{}")
    evaluation.add_argument("--noncritical-deltas-json", default="{}")
    evaluation.add_argument("--target-skill-delta", type=float, required=True)
    evaluation.add_argument("--heldout-passed", action="store_true")
    evaluation.add_argument("--reversible", action="store_true")
    evaluation.add_argument("--evaluator-changed", action="store_true")
    evaluation.add_argument("--threshold-lowered", action="store_true")

    manifest = commands.add_parser("cr-jepa-manifest")
    manifest.add_argument("--ledger", default=_DEFAULT_LEDGER)
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
    return 0 if _successful(payload) else 2


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "audit":
        return audit_cognitive_genome(Path(args.genome))
    if args.command == "residual":
        return append_cognitive_residual(
            Path(args.ledger),
            model_id=args.model_id,
            model_family=args.model_family,
            domain=args.domain,
            context_signature=args.context_signature,
            state_embedding_ref=args.state_ref,
            predicted_outcome_ref=args.predicted_ref,
            observed_outcome_ref=args.observed_ref,
            failure_class=args.failure_class,
            residual_magnitude=args.residual_magnitude,
            profile_set=_csv(args.profiles),
            tool_set=_csv(args.tools),
            correction_ref=args.correction_ref,
            correction_verified=args.correction_verified,
            causal_intervention_verified=args.causal_intervention_verified,
            best_corrective_intervention=args.best_corrective_intervention,
        )
    if args.command == "topology":
        return project_residual_topology(Path(args.ledger))
    if args.command == "skill-candidate":
        topology = _read_json_object(Path(args.topology_json))
        return build_skill_candidate(
            topology,
            residual_signature=args.residual_signature,
            skill_id=args.skill_id,
            domain=args.domain,
        )
    if args.command == "council":
        return build_profile_council(
            failure_class=args.failure_class,
            novelty=args.novelty,
            uncertainty=args.uncertainty,
            mutation_requested=args.mutation_requested,
        )
    if args.command == "homeostasis":
        return build_homeostasis_decision(
            uncertainty=args.uncertainty,
            recurrence_count=args.recurrence_count,
            deterministic_verification_available=args.deterministic_verification_available,
            local_verification_failed=args.local_verification_failed,
            cost_pressure=args.cost_pressure,
            regression_risk=args.regression_risk,
        )
    if args.command == "mutation-plan":
        return build_mutation_plan(
            skill_candidate_hash=args.skill_candidate_hash,
            mutation_level=args.mutation_level,
            baseline_ref=args.baseline_ref,
            evaluator_ref=args.evaluator_ref,
            revocation_ref=args.revocation_ref,
        )
    if args.command == "mutation-evaluate":
        return evaluate_mutation_candidate(
            plan_hash=args.plan_hash,
            critical_competency_deltas=_float_mapping(args.critical_deltas_json),
            noncritical_competency_deltas=_float_mapping(args.noncritical_deltas_json),
            target_skill_delta=args.target_skill_delta,
            heldout_passed=args.heldout_passed,
            reversible=args.reversible,
            evaluator_changed=args.evaluator_changed,
            threshold_lowered=args.threshold_lowered,
        )
    if args.command == "cr-jepa-manifest":
        return build_cr_jepa_v0_manifest(Path(args.ledger))
    raise ValueError("unknown cognitive genome command")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _float_mapping(raw: str) -> dict[str, float]:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, int | float)
        for key, value in payload.items()
    ):
        raise ValueError("metric deltas must be a numeric JSON object")
    return {key: float(value) for key, value in payload.items()}


def _successful(payload: dict[str, object]) -> bool:
    if payload.get("status") in {"blocked", "rejected"}:
        return False
    if payload.get("genome_ready") is False:
        return False
    if payload.get("promotion_allowed") is False and payload.get("evaluation_type"):
        return False
    return not payload.get("blockers")


if __name__ == "__main__":
    raise SystemExit(main())
