"""Read-only code analysis -> real local Harness -> grounded structured plan.

Code is read only after explicit approval. Only source metadata is used by
default; raw file text may enter a separately approved local model prompt,
never a persistent receipt. No shell, patch, git commit or tests executed.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_structured_code_plan import parse_structured_code_plan
from hex_cortex.memory.cortex_universal_sensing_v26 import observe_local_file

_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)


def review_local_code(
    *, project_root: Path, file_path: Path, model_id: str,
    brain: Callable[[str, Task], str] | None = None,
    approve_read: bool = False, approve_model: bool = False,
    approve_share_source: bool = False,
) -> dict[str, object]:
    if not approve_read:
        return {"status": "blocked", "reason": "code_read_not_approved",
                "model_calls": 0, "files_written": False}
    root = Path(project_root).resolve(strict=True)
    observed = observe_local_file(
        root=root, path=file_path, modality="code", approved=True
    )
    resolved = file_path.resolve(strict=True)
    relative = resolved.relative_to(root).as_posix()
    base = {
        "status": "static_inspection",
        "file": relative,
        "source_sha256": observed["source_sha256"],
        "features": observed["features"],
        "model_calls": 0,
        "source_sent_to_model": False,
        "files_written": False, "code_executed": False,
        "patch_applied": False,
    }
    if not approve_model:
        return base
    if brain is None or not model_id.strip():
        raise ValueError("code_brain_missing")
    source = ""
    if approve_share_source:
        if resolved.stat().st_size > 32_000:
            raise ValueError("code_sharing_file_over_budget")
        source = resolved.read_text(encoding="utf-8")
        if _SECRET_PATTERN.search(source):
            raise ValueError("potential_secret_in_source_model_sharing_denied")
    prompt = (
        "Respond with ONLY JSON matching a structured code-plan schema: "
        "summary, focus_areas, candidate_files, proposed_changes, tests, "
        "risks, unknowns. No code execution or file mutation. "
        "Review only the approved repository file.\n"
        f"File: {relative}\n"
        "Static Python AST observation: "
        + json.dumps(observed["features"], sort_keys=True)
    )
    if source:
        prompt += "\nOperator-approved ephemeral local file contents:\n" + source
    harness = LocalHarness(
        session=Session("code-review-v26", root),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )
    execution = run_clocked_local_task(
        harness,
        Task("code-review-v26", "coding", prompt),
        models=[model_id], brain=brain, approved=True,
    )
    reply = execution.get("output")
    graded = (
        parse_structured_code_plan(reply, allowed_paths={relative})
        if execution.get("status") == "complete" and isinstance(reply, str)
        else {"status": "invalid", "plan": None, "invalid_paths": []}
    )
    return {
        **base,
        "status": "reviewed" if graded["status"] == "valid" else "blocked",
        "model_calls": harness._model_calls,
        "source_sent_to_model": bool(source),
        "plan": graded.get("plan"),
        "plan_status": graded["status"],
        "invalid_paths": graded.get("invalid_paths", []),
        "raw_model_answer_sha256": hashlib.sha256(
            reply.encode()
        ).hexdigest() if isinstance(reply, str) else None,
        "harness_spine_verified": execution["canonical_spine_verified"],
        "harness_replay_verified": harness.verify_replay(),
        "receipt_sha256": (
            execution["receipt"]["sha256"]
            if isinstance(execution.get("receipt"), dict) else None
        ),
    }
