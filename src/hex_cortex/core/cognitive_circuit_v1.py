"""Deterministic, model-free integration of original HEX-CORTEX cognitive pillars.

A trusted host supplies the cell computation and an independent verifier.
The circuit coordinates the pre-existing ThalamicRouter, CellRegistry,
GlobalWorkspace, CognitiveClock and CanonicalSpine; no LLM, network, file
mutation or model benchmark is required.

It cannot guarantee injected callbacks are side-effect free. Such permissions
must be enforced by the host gateway, never by instructions to a model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_clock import (
    CognitiveClock,
    RegisteredTick,
    TickName,
    TickResult,
    TickStatus,
)
from hex_cortex.core.router import ThalamicRouter
from hex_cortex.core.schemas import CellResult, CognitiveMode, Task
from hex_cortex.core.workspace import GlobalWorkspace
from hex_cortex.spine.canonical_spine import CanonicalSpine

CellHandler = Callable[[str, Task], CellResult]
IndependentVerifier = Callable[[CellResult], bool]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass
class CognitiveCircuit:
    registry: CellRegistry
    router: ThalamicRouter = field(default_factory=ThalamicRouter)
    spine: CanonicalSpine = field(default_factory=CanonicalSpine)
    _used_task_ids: set[str] = field(default_factory=set)

    def run(
        self,
        task: Task,
        *,
        cell_handler: CellHandler,
        verify_evidence: IndependentVerifier | None = None,
        secondary_verifier: IndependentVerifier | None = None,
        approved: bool = False,
    ) -> dict[str, object]:
        """Run only the selected healthy cells; report bounded, redacted evidence."""
        if task.task_id in self._used_task_ids:
            return self._blocked(task.task_id, "duplicate_task_id")
        if not approved:
            return self._blocked(task.task_id, "operator_approval_required")
        if verify_evidence is None:
            return self._blocked(task.task_id, "independent_verifier_required")
        if not callable(cell_handler) or not callable(verify_evidence):
            return self._blocked(task.task_id, "invalid_callback")
        try:
            route = self.router.route_registered(task, self.registry)
        except ValueError:
            return self._blocked(task.task_id, "no_healthy_cells")
        self._used_task_ids.add(task.task_id)
        selected = route.selected_cells
        if not selected or len(selected) > route.budget.max_cells:
            return self._blocked(task.task_id, "invalid_route")
        # The raw goal is never stored in workspace or spine.
        goal_hash = _digest(task.content)
        workspace = GlobalWorkspace(
            task_id=task.task_id,
            goal="sha256:" + goal_hash,
            mode=route.mode,
            active_cells=list(selected),
        )
        outcomes: list[dict[str, object]] = []
        failures: set[str] = set()

        def _action(_context) -> TickResult:
            for cell_id in selected:
                if self.registry.get(cell_id) is None:
                    failures.add(cell_id)
                    break
                try:
                    proposed = cell_handler(cell_id, task)
                    if not isinstance(proposed, CellResult):
                        raise ValueError("cell result is not typed")
                    if proposed.task_id != task.task_id or proposed.cell_id != cell_id:
                        raise ValueError("cell result identity mismatch")
                    if not proposed.evidence_refs or len(proposed.evidence_refs) > 16:
                        raise ValueError("missing or excessive evidence refs")
                    if len(json.dumps(proposed.model_dump(mode="json"))) > 12_000:
                        raise ValueError("cell result budget exceeded")
                    if not verify_evidence(proposed):
                        raise ValueError("independent verification rejected")
                    health = next(
                        (row for row in self.registry.health_records if row.cell_id == cell_id),
                        None,
                    )
                    if health is not None and health.requires_double_check:
                        if (secondary_verifier is None
                                or secondary_verifier is verify_evidence
                                or not secondary_verifier(proposed)):
                            raise ValueError("independent double verification missing")
                except Exception:  # noqa: BLE001 - confidential input/errors must not enter spine
                    failures.add(cell_id)
                    self.registry.record_failure(cell_id, "verification_failed")
                    outcomes.append({
                        "cell_id": cell_id, "status": "rejected",
                        "reason": "verification_failed",
                    })
                    break
                self.registry.record_success(cell_id)
                outcomes.append({
                    "cell_id": cell_id,
                    "status": "verified",
                    "receipt_sha256": _digest(proposed.model_dump(mode="json")),
                    "evidence_count": len(proposed.evidence_refs),
                })
            if failures:
                workspace.add_issue("independent_verification_failed")
            workspace.set_next_action("review" if failures else "verified_no_mutation")
            return TickResult(
                tick_name=TickName.ACTION,
                status=TickStatus.FAILED if failures else TickStatus.SUCCESS,
                payload={
                    "verified_count": sum(row["status"] == "verified" for row in outcomes),
                    "rejected_count": len(failures),
                    "workspace_sha256": _digest(workspace.snapshot().model_dump(mode="json")),
                },
                error="cell_evidence_rejected" if failures else None,
            )

        def _critic(_context) -> TickResult:
            ok = not failures and len(outcomes) == len(selected) and all(
                row["status"] == "verified" for row in outcomes
            )
            return TickResult(
                tick_name=TickName.CRITIC,
                status=TickStatus.SUCCESS if ok else TickStatus.FAILED,
                payload={"verified": ok, "selected_count": len(selected)},
                error=None if ok else "independent_critic_rejected",
            )

        tick_names = [
            RegisteredTick(TickName.ACTION, _action),
            RegisteredTick(TickName.CRITIC, _critic),
        ]
        if route.mode != CognitiveMode.REFLEX:
            tick_names.insert(0, RegisteredTick(
                TickName.WORKSPACE,
                lambda _: {
                    "workspace_sha256": _digest(workspace.snapshot().model_dump(mode="json")),
                    "selected_count": len(selected),
                },
            ))
        clock = CognitiveClock(
            spine=self.spine, max_ticks=route.budget.max_ticks,
            max_latency_ms=route.budget.latency_budget_ms,
        )
        # Use an entirely redacted Task envelope in the scheduler.
        envelope = task.model_copy(update={
            "content": "sha256:" + goal_hash,
            "domain_hints": ["redacted"],
        })
        report = clock.run(task=envelope, mode=route.mode, ticks=tick_names)
        integrity_ok = self.spine.verify_integrity().ok
        completed = (
            report.completed and integrity_ok and not failures
            and len(outcomes) == len(selected)
        )
        return {
            "report_type": "hex_cortex_cognitive_circuit_v1",
            "status": "verified" if completed else "blocked",
            "reason": "ok" if completed else (report.stopped_reason or "verification_failed"),
            "task_id": task.task_id,
            "mode": route.mode.value,
            "selected_cells": list(selected),
            "selected_cell_count": len(selected),
            "verified_cell_count": sum(row["status"] == "verified" for row in outcomes),
            "outcomes": outcomes,
            "workspace_goal_sha256": goal_hash,
            "workspace_confidence": workspace.snapshot().confidence,
            "next_action": workspace.snapshot().next_action,
            "spine_verified": integrity_ok,
            "spine_event_count": len(self.spine.events),
            "model_used": False,
            "model_benchmark_required": False,
            "automatic_skill_promotion": False,
            "checkout_modified": False,
        }

    def _blocked(self, task_id: str, reason: str) -> dict[str, object]:
        return {
            "report_type": "hex_cortex_cognitive_circuit_v1",
            "task_id": task_id,
            "status": "blocked",
            "reason": reason,
            "model_used": False,
            "checkout_modified": False,
        }
