"""Local-first HEX-CORTEX Harness V2: bounded decisions, tools and replay.

A host injects the Brain adapter. This module never instantiates an external
model, launches a process, writes a file, or grants permissions implicitly.
All receipts are content-addressed, redacted to summaries, and replayable.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from hex_cortex.memory.cortex_bandit_router import empty_routing_stats, rank_models
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


class Capability(StrEnum):
    READ_REPO = "read_repo"
    CALL_MODEL = "call_model"
    APPLY_PATCH = "apply_patch"
    RUN_TEST = "run_test"


@dataclass(frozen=True)
class Session:
    session_id: str
    project_root: Path
    project_id: str = "HEX-CORTEX"

    def __post_init__(self) -> None:
        if not self.session_id.strip() or self.project_id != "HEX-CORTEX":
            raise ValueError("invalid HEX-CORTEX session identity")
        if not self.project_root.is_dir():
            raise ValueError("project_root must be an existing directory")


@dataclass(frozen=True)
class Budget:
    max_model_calls: int = 1
    max_tool_calls: int = 0
    max_response_chars: int = 12_000

    def __post_init__(self) -> None:
        if self.max_model_calls < 0 or self.max_tool_calls < 0:
            raise ValueError("budgets cannot be negative")
        if self.max_response_chars <= 0:
            raise ValueError("response budget must be positive")


@dataclass(frozen=True)
class Task:
    task_id: str
    domain: str
    instruction: str
    requested_tool: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.domain.strip() or not self.instruction.strip():
            raise ValueError("task identity and instruction are required")


@dataclass(frozen=True)
class Tool:
    name: str
    capability: Capability
    handler: Callable[[Session, Task], Mapping[str, object]]
    modifies_files: bool = False


@dataclass
class LocalHarness:
    session: Session
    grants: frozenset[Capability] = field(default_factory=frozenset)
    budget: Budget = field(default_factory=Budget)
    tools: dict[str, Tool] = field(default_factory=dict)
    receipts: list[dict[str, object]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=empty_routing_stats)
    priors: dict[str, float] = field(default_factory=dict)
    spine: CanonicalSpine = field(default_factory=CanonicalSpine)
    _model_calls: int = 0
    _tool_calls: int = 0

    def _receipt(self, payload: dict[str, object]) -> dict[str, object]:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        result = {"receipt_type": "local_harness_v2", **payload, "sha256": digest}
        self.receipts.append(result)
        self.spine.append(
            event_type="harness.receipt",
            task_id=str(payload["task_id"]),
            source="LocalHarness",
            payload={
                "sha256": digest,
                "status": payload["status"],
                "reason": payload["reason"],
                "model_used": payload.get("model_used"),
                "tool_used": payload.get("tool_used"),
                "project_id": self.session.project_id,
            },
            correlation_keys={"session_id": self.session.session_id},
        )
        return result

    def execute(
        self,
        task: Task,
        *,
        models: list[str] | None = None,
        brain: Callable[[str, Task], str] | None = None,
        approved: bool = False,
    ) -> dict[str, object]:
        """Execute strictly granted operations; otherwise return blocked evidence.

        No prompt or model output is copied into durable receipts. A caller may
        access the ephemeral output through the normal return value.
        """
        if any(row.get("task_id") == task.task_id for row in self.receipts):
            return self._receipt({
                "task_id": task.task_id,
                "status": "blocked",
                "reason": "duplicate_task_id",
                "model_used": None,
                "tool_used": None,
            })

        selected: str | None = None
        text = ""
        tool_result: dict[str, object] | None = None
        reason = "ok"
        if brain is not None:
            if Capability.CALL_MODEL not in self.grants or not approved:
                reason = "model_call_not_authorized"
            elif self._model_calls >= self.budget.max_model_calls:
                reason = "model_call_budget_exhausted"
            elif not models:
                reason = "no_candidates"
            else:
                decision = rank_models(
                    self.stats, domain=task.domain, candidates=models,
                    benchmark_priors=self.priors, exploration_weight=0.0,
                )
                selected = str(decision["selected_model"])
                self._model_calls += 1
                try:
                    text = brain(selected, task)
                    if not isinstance(text, str) or len(text) > self.budget.max_response_chars:
                        reason = "model_response_invalid_or_over_budget"
                except Exception:  # noqa: BLE001 - no provider exceptions in receipts
                    reason = "brain_adapter_failed"

        if reason == "ok" and task.requested_tool is not None:
            tool = self.tools.get(task.requested_tool)
            if tool is None:
                reason = "tool_not_allowlisted"
            elif not approved or tool.capability not in self.grants:
                reason = "tool_not_authorized"
            elif self._tool_calls >= self.budget.max_tool_calls:
                reason = "tool_budget_exhausted"
            elif tool.modifies_files:
                reason = "mutating_tools_not_supported_in_local_kernel"
            else:
                self._tool_calls += 1
                try:
                    tool_result = dict(tool.handler(self.session, task))
                    # The tool adapter owns its data; avoid recording it in receipts.
                except Exception:  # noqa: BLE001
                    reason = "tool_adapter_failed"

        status = "complete" if reason == "ok" else "blocked"
        receipt = self._receipt({
            "session_id": self.session.session_id,
            "project_id": self.session.project_id,
            "task_id": task.task_id,
            "domain": task.domain,
            "status": status,
            "reason": reason,
            "model_used": selected,
            "tool_used": task.requested_tool if tool_result is not None else None,
            "model_calls_used": self._model_calls,
            "tool_calls_used": self._tool_calls,
            "response_chars": len(text) if status == "complete" else 0,
        })
        return {
            "status": status,
            "reason": reason,
            "output": text if status == "complete" else None,
            "tool_result": tool_result if status == "complete" else None,
            "receipt": receipt,
        }

    def verify_replay(self) -> bool:
        """Recheck content hashes and absence of duplicate completed task IDs."""
        seen: set[str] = set()
        for row in self.receipts:
            payload = {
                key: value for key, value in row.items()
                if key not in {"receipt_type", "sha256"}
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(canonical.encode()).hexdigest() != row.get("sha256"):
                return False
            if row["status"] == "complete" and row["task_id"] in seen:
                return False
            seen.add(str(row["task_id"]))
        if not self.spine.verify_integrity().ok:
            return False
        spine_receipts = [
            event for event in self.spine.events if event.event_type == "harness.receipt"
        ]
        return (
            len(spine_receipts) == len(self.receipts)
            and all(
                event.payload.get("sha256") == receipt["sha256"]
                for event, receipt in zip(spine_receipts, self.receipts, strict=True)
            )
        )

    def save_spine(self, path: Path, *, approved: bool = False) -> int:
        """Opt-in persisted canonical events, never overwriting existing files."""
        if not approved:
            raise PermissionError("explicit local receipt persistence approval required")
        root = self.session.project_root.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or target.is_symlink() or target.exists():
            raise ValueError("spine path must be a new file inside the project root")
        if not self.verify_replay():
            raise ValueError("canonical receipt integrity failed")
        return CanonicalSpineJsonlStore(target).save(self.spine)


def read_repo_manifest(session: Session, task: Task) -> Mapping[str, object]:
    """Safe local inventory of one checkout. Never follows symlinks or reads content."""
    del task
    root = session.project_root.resolve()
    selected: list[str] = []
    for name in ("pyproject.toml", "README.md", "AGENTS.md", "CLAUDE.md"):
        path = root / name
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root):
            selected.append(name)
    return {"project_id": session.project_id, "manifest": selected}


def build_readonly_harness(project_root: Path, *, session_id: str = "local") -> LocalHarness:
    """Provide the safest runnable configuration with one read-only tool."""
    return LocalHarness(
        session=Session(session_id=session_id, project_root=project_root.resolve()),
        grants=frozenset({Capability.READ_REPO}),
        budget=Budget(max_model_calls=0, max_tool_calls=1),
        tools={"repo_manifest": Tool("repo_manifest", Capability.READ_REPO, read_repo_manifest)},
    )
