from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_coding_model_executor import execute_coding_model_task
from hex_cortex.memory.cortex_research_hypothesis_ledger import append_research_hypothesis
from hex_cortex.memory.cortex_research_hypothesis_ledger import append_research_outcome
from hex_cortex.memory.cortex_research_hypothesis_ledger import project_research_frontier
from hex_cortex.memory.cortex_worktree_executor import apply_reviewable_patch
from hex_cortex.memory.cortex_worktree_executor import build_worktree_plan
from hex_cortex.memory.cortex_worktree_executor import create_isolated_worktree
from hex_cortex.memory.cortex_worktree_executor import run_allowlisted_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-code")
    commands = parser.add_subparsers(dest="command", required=True)

    execute = commands.add_parser("execute")
    execute.add_argument("provider_id", choices=("local_open_weight", "remote_api"))
    execute.add_argument("prompt_file")
    execute.add_argument("--instruction-file", required=True)
    execute.add_argument("--context-file")
    execute.add_argument("--model", required=True)
    execute.add_argument("--context-sensitivity", choices=("public", "private", "secret"), default="private")
    execute.add_argument("--local-endpoint", default="http://127.0.0.1:8080")
    execute.add_argument("--remote-api-key-ref", default="env:OPENAI_API_KEY")
    execute.add_argument("--max-output-tokens", type=int, default=4096)
    execute.add_argument("--timeout-seconds", type=float, default=120.0)
    execute.add_argument("--operator-approved", action="store_true")

    worktree_plan = commands.add_parser("worktree-plan")
    worktree_plan.add_argument("repository_root")
    worktree_plan.add_argument("worktree_root")
    worktree_plan.add_argument("candidate_id")
    worktree_plan.add_argument("base_ref")
    worktree_plan.add_argument("--check", dest="checks", action="append")
    worktree_plan.add_argument("--output", required=True)

    worktree_create = commands.add_parser("worktree-create")
    worktree_create.add_argument("plan_json")
    worktree_create.add_argument("--timeout-seconds", type=float, default=120.0)
    worktree_create.add_argument("--operator-approved", action="store_true")

    patch_apply = commands.add_parser("patch-apply")
    patch_apply.add_argument("worktree_path")
    patch_apply.add_argument("patch_path")
    patch_apply.add_argument("expected_patch_hash")
    patch_apply.add_argument("--timeout-seconds", type=float, default=120.0)
    patch_apply.add_argument("--operator-approved", action="store_true")

    check = commands.add_parser("worktree-check")
    check.add_argument("worktree_path")
    check.add_argument("--check", dest="checks", action="append", required=True)
    check.add_argument("--timeout-seconds", type=float, default=1800.0)
    check.add_argument("--operator-approved", action="store_true")

    hypothesis_add = commands.add_parser("hypothesis-add")
    hypothesis_add.add_argument("tree_jsonl")
    hypothesis_add.add_argument("statement")
    hypothesis_add.add_argument("baseline_ref")
    hypothesis_add.add_argument("evaluator_ref")
    hypothesis_add.add_argument("--created-by", default="hex-cortex")
    hypothesis_add.add_argument("--parent-id")
    hypothesis_add.add_argument("--budget-units", type=int, default=1)

    hypothesis_outcome = commands.add_parser("hypothesis-outcome")
    hypothesis_outcome.add_argument("tree_jsonl")
    hypothesis_outcome.add_argument("hypothesis_id")
    hypothesis_outcome.add_argument("status", choices=("running", "validated", "rejected", "pruned"))
    hypothesis_outcome.add_argument("--candidate-ref")
    hypothesis_outcome.add_argument("--metric-delta", type=float)
    hypothesis_outcome.add_argument("--heldout-passed", choices=("true", "false", "unknown"), default="unknown")
    hypothesis_outcome.add_argument("--insight-ref")

    hypothesis_frontier = commands.add_parser("hypothesis-frontier")
    hypothesis_frontier.add_argument("tree_jsonl")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "execute":
        instruction = _read_text(Path(args.instruction_file), "instruction")
        prompt = _read_text(Path(args.prompt_file), "prompt")
        context = "" if args.context_file is None else _read_text(Path(args.context_file), "context")
        if instruction is None or prompt is None or context is None:
            return 2
        try:
            payload = execute_coding_model_task(
                provider_id=args.provider_id,
                model=args.model,
                instruction=instruction,
                task_prompt=prompt,
                bounded_context=context,
                context_sensitivity=args.context_sensitivity,
                local_endpoint=args.local_endpoint,
                remote_api_key_ref=args.remote_api_key_ref,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                operator_approved=args.operator_approved,
            )
        except ValueError as exc:
            payload = {"status": "blocked", "blockers": [str(exc)]}
        _emit(payload)
        return 0 if payload.get("status") == "completed" else 2
    if args.command == "worktree-plan":
        payload = build_worktree_plan(
            repository_root=Path(args.repository_root),
            worktree_root=Path(args.worktree_root),
            candidate_id=args.candidate_id,
            base_ref=args.base_ref,
            check_ids=args.checks,
        )
        if payload.get("status") == "ready":
            _write_json(Path(args.output), payload)
        _emit(payload)
        return 0 if payload.get("status") == "ready" else 2
    if args.command == "worktree-create":
        plan = _read_json_object(Path(args.plan_json), "worktree_plan")
        if plan is None:
            return 2
        payload = create_isolated_worktree(
            plan,
            operator_approved=args.operator_approved,
            timeout_seconds=args.timeout_seconds,
        )
        _emit(payload)
        return 0 if payload.get("status") == "created" else 2
    if args.command == "patch-apply":
        payload = apply_reviewable_patch(
            worktree_path=Path(args.worktree_path),
            patch_path=Path(args.patch_path),
            expected_patch_hash=args.expected_patch_hash,
            operator_approved=args.operator_approved,
            timeout_seconds=args.timeout_seconds,
        )
        _emit(payload)
        return 0 if payload.get("status") == "applied" else 2
    if args.command == "worktree-check":
        payload = run_allowlisted_checks(
            worktree_path=Path(args.worktree_path),
            check_ids=args.checks,
            operator_approved=args.operator_approved,
            timeout_seconds=args.timeout_seconds,
        )
        _emit(payload)
        return 0 if payload.get("status") == "passed" else 2
    if args.command == "hypothesis-add":
        try:
            payload = append_research_hypothesis(
                Path(args.tree_jsonl),
                statement=args.statement,
                baseline_ref=args.baseline_ref,
                evaluator_ref=args.evaluator_ref,
                created_by=args.created_by,
                parent_id=args.parent_id,
                budget_units=args.budget_units,
            )
        except ValueError as exc:
            payload = {"status": "blocked", "blockers": [str(exc)]}
        _emit(payload)
        return 0 if payload.get("record_type") == "research_hypothesis_node_v1" else 2
    if args.command == "hypothesis-outcome":
        heldout = {"true": True, "false": False, "unknown": None}[args.heldout_passed]
        try:
            payload = append_research_outcome(
                Path(args.tree_jsonl),
                hypothesis_id=args.hypothesis_id,
                status=args.status,
                candidate_ref=args.candidate_ref,
                metric_delta=args.metric_delta,
                heldout_passed=heldout,
                insight_ref=args.insight_ref,
            )
        except ValueError as exc:
            payload = {"status": "blocked", "blockers": [str(exc)]}
        _emit(payload)
        return 0 if payload.get("record_type") == "research_hypothesis_outcome_v1" else 2
    try:
        payload = project_research_frontier(Path(args.tree_jsonl))
    except ValueError as exc:
        payload = {"status": "blocked", "blockers": [str(exc)]}
    _emit(payload)
    return 0 if payload.get("projection_type") == "research_hypothesis_frontier_v1" else 2


def _read_text(path: Path, name: str) -> str | None:
    try:
        return path.resolve().read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _emit({"status": "blocked", "blockers": [f"{name}_file_invalid"]})
        return None


def _read_json_object(path: Path, name: str) -> dict[str, object] | None:
    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
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
