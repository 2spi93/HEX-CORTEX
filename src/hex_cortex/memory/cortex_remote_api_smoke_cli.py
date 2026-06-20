from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_coding_model_executor import JsonTransport
from hex_cortex.memory.cortex_coding_model_executor import execute_coding_model_task
from hex_cortex.memory.cortex_evidence_reconciliation import append_canonical_evidence

_EXPECTED_TOKEN = "HEX-CORTEX-REMOTE-SMOKE-OK"
_INSTRUCTION = (
    "This is a bounded connectivity smoke test. Return only the exact token requested by "
    "the user. Do not add punctuation, Markdown, or explanation."
)
_TASK_PROMPT = f"Return exactly: {_EXPECTED_TOKEN}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-remote-smoke")
    parser.add_argument("--model", default="gpt-5.2")
    parser.add_argument("--api-key-ref", default="env:OPENAI_API_KEY")
    parser.add_argument(
        "--output",
        default=".hex-cortex/receipts/remote-api-smoke.json",
    )
    parser.add_argument(
        "--evidence-jsonl",
        default=".hex-cortex/receipts/00-canonical-evidence.jsonl",
    )
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--operator-approved", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_remote_api_smoke(
        model=args.model,
        api_key_ref=args.api_key_ref,
        output_path=Path(args.output),
        evidence_jsonl=Path(args.evidence_jsonl),
        timeout_seconds=args.timeout_seconds,
        operator_approved=args.operator_approved,
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "completed" else 2


def run_remote_api_smoke(
    *,
    model: str,
    api_key_ref: str,
    output_path: Path,
    evidence_jsonl: Path,
    timeout_seconds: float = 60.0,
    operator_approved: bool = False,
    transport: JsonTransport | None = None,
) -> dict[str, object]:
    execution = execute_coding_model_task(
        provider_id="remote_api",
        model=model,
        instruction=_INSTRUCTION,
        task_prompt=_TASK_PROMPT,
        bounded_context="",
        context_sensitivity="public",
        remote_api_key_ref=api_key_ref,
        max_output_tokens=32,
        timeout_seconds=timeout_seconds,
        operator_approved=operator_approved,
        transport=transport,
    )
    volatile_result = execution.get("volatile_result_text")
    exact_match = (
        execution.get("status") == "completed"
        and isinstance(volatile_result, str)
        and volatile_result.strip() == _EXPECTED_TOKEN
    )
    sanitized = {
        key: value
        for key, value in execution.items()
        if key not in {"volatile_result_text", "receipt_hash"}
    }
    sanitized.update(
        {
            "status": "completed" if exact_match else _failed_status(execution),
            "smoke_contract": "exact_token_v1",
            "smoke_contract_passed": exact_match,
            "expected_token_hash": hashlib.sha256(_EXPECTED_TOKEN.encode("utf-8")).hexdigest(),
            "result_persisted": False,
            "prompt_persisted": False,
            "raw_response_persisted": False,
            "raw_secret_persisted": False,
            "blockers": [] if exact_match else _smoke_blockers(execution),
            "next_action": "retain_remote_api_smoke_receipt" if exact_match else "repair_model_provider",
        }
    )
    sanitized["receipt_hash"] = _stable_hash(sanitized)

    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sanitized, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    evidence_append = None
    if exact_match:
        evidence_append = append_canonical_evidence(
            output_path=evidence_jsonl,
            record=sanitized,
        )
    payload = {
        **sanitized,
        "receipt_path": str(target),
        "canonical_evidence_append": evidence_append,
    }
    return payload


def _failed_status(execution: dict[str, object]) -> str:
    return "blocked" if execution.get("status") == "blocked" else "failed"


def _smoke_blockers(execution: dict[str, object]) -> list[str]:
    blockers = execution.get("blockers")
    values = [str(item) for item in blockers] if isinstance(blockers, list) else []
    if execution.get("status") == "completed":
        values.append("smoke_contract_mismatch")
    return sorted(set(values or ["remote_api_smoke_failed"]))


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
