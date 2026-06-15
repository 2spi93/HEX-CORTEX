"""Minimal thalamic router for HEX-CORTEX."""

from __future__ import annotations

from dataclasses import dataclass

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.schemas import (
    CellSpec,
    CognitiveBudget,
    CognitiveMode,
    RoutingDecision,
    Task,
)


@dataclass(frozen=True)
class RouterWeights:
    """Weights used by the deterministic v0 router."""

    domain_match: float = 0.35
    trust: float = 0.25
    novelty_affinity: float = 0.15
    latency_cost: float = 0.15
    recent_error_penalty: float = 0.10


class ThalamicRouter:
    """Selects thinking mode and active cells.

    v0 is deterministic by design. No LLM router yet.
    """

    def __init__(self, weights: RouterWeights | None = None) -> None:
        self.weights = weights or RouterWeights()

    def build_budget(self, task: Task) -> CognitiveBudget:
        """Convert task risk/novelty/uncertainty into a cognitive budget."""

        cognitive_pressure = (task.risk + task.novelty + task.uncertainty) / 3

        if cognitive_pressure >= 0.72:
            return CognitiveBudget(
                mode=CognitiveMode.DEEP,
                max_ticks=6,
                max_cells=7,
                latency_budget_ms=max(task.latency_budget_ms, 8_000),
                confidence_threshold=0.82,
            )

        if cognitive_pressure >= 0.38:
            return CognitiveBudget(
                mode=CognitiveMode.WORKING,
                max_ticks=4,
                max_cells=5,
                latency_budget_ms=max(task.latency_budget_ms, 2_000),
                confidence_threshold=0.72,
            )

        return CognitiveBudget(
            mode=CognitiveMode.REFLEX,
            max_ticks=2,
            max_cells=2,
            latency_budget_ms=min(task.latency_budget_ms, 800),
            confidence_threshold=0.62,
        )

    def route(self, task: Task, cells: list[CellSpec]) -> RoutingDecision:
        """Route a task to the best cells under a bounded cognitive budget."""

        if not cells:
            raise ValueError("cannot route without registered cells")

        budget = self.build_budget(task)
        routable_cells = [cell for cell in cells if cell.trust_score > 0.0]
        if not routable_cells:
            raise ValueError("cannot route without healthy cells")

        scored_cells = sorted(
            ((cell, self._score_cell(task, cell)) for cell in routable_cells),
            key=lambda item: item[1],
            reverse=True,
        )
        selected = [cell.cell_id for cell, _score in scored_cells[: budget.max_cells]]

        return RoutingDecision(
            task_id=task.task_id,
            mode=budget.mode,
            selected_cells=selected,
            budget=budget,
            rationale=(
                f"selected {len(selected)} cells in {budget.mode.value} mode "
                f"from {len(routable_cells)} healthy cells"
            ),
        )

    def route_registered(self, task: Task, registry: CellRegistry) -> RoutingDecision:
        """Route a task through a health-aware cell registry."""

        return self.route(task, registry.available())

    def _score_cell(self, task: Task, cell: CellSpec) -> float:
        domain_match = self._domain_match(task, cell)
        novelty_affinity = 1.0 - abs(task.novelty - cell.trust_score)

        score = (
            domain_match * self.weights.domain_match
            + cell.trust_score * self.weights.trust
            + novelty_affinity * self.weights.novelty_affinity
            - cell.latency_cost * self.weights.latency_cost
            - cell.recent_error_penalty * self.weights.recent_error_penalty
        )
        return max(0.0, min(score, 1.0))

    @staticmethod
    def _domain_match(task: Task, cell: CellSpec) -> float:
        if not task.domain_hints or not cell.domains:
            return 0.5

        task_domains = {domain.lower() for domain in task.domain_hints}
        cell_domains = {domain.lower() for domain in cell.domains}
        overlap = task_domains.intersection(cell_domains)
        return len(overlap) / max(len(task_domains), 1)
