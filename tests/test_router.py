import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.router import ThalamicRouter
from hex_cortex.core.schemas import CellRole, CellSpec, CognitiveMode, Hypothesis, Task
from hex_cortex.core.workspace import GlobalWorkspace


def test_router_selects_deep_mode_for_high_pressure_task() -> None:
    router = ThalamicRouter()
    task = Task(
        content="Design a new modular AI architecture",
        domain_hints=["architecture", "reasoning"],
        novelty=0.9,
        risk=0.8,
        uncertainty=0.75,
    )
    cells = [
        CellSpec(
            cell_id="logic_cell",
            role=CellRole.LOGIC,
            domains=["reasoning", "architecture"],
            trust_score=0.9,
            latency_cost=0.2,
        ),
        CellSpec(
            cell_id="memory_cell",
            role=CellRole.MEMORY,
            domains=["memory"],
            trust_score=0.8,
            latency_cost=0.1,
        ),
        CellSpec(
            cell_id="slow_untrusted_cell",
            role=CellRole.ACTION,
            domains=["architecture"],
            trust_score=0.2,
            latency_cost=0.9,
            recent_error_penalty=0.5,
        ),
    ]

    decision = router.route(task, cells)

    assert decision.mode == CognitiveMode.DEEP
    assert decision.selected_cells[0] == "logic_cell"
    assert "slow_untrusted_cell" in decision.selected_cells
    assert decision.budget.max_cells == 7


def test_router_selects_reflex_mode_for_low_pressure_task() -> None:
    router = ThalamicRouter()
    task = Task(
        content="Classify this short text",
        domain_hints=["intent"],
        novelty=0.1,
        risk=0.1,
        uncertainty=0.1,
        latency_budget_ms=500,
    )
    cells = [
        CellSpec(cell_id="intent_cell", role=CellRole.INTENT, domains=["intent"]),
        CellSpec(cell_id="critic_cell", role=CellRole.CRITIC, domains=["review"]),
        CellSpec(cell_id="memory_cell", role=CellRole.MEMORY, domains=["memory"]),
    ]

    decision = router.route(task, cells)

    assert decision.mode == CognitiveMode.REFLEX
    assert len(decision.selected_cells) == 2
    assert decision.selected_cells[0] == "intent_cell"


def test_router_uses_registry_health_and_excludes_quarantined_cells() -> None:
    router = ThalamicRouter()
    task = Task(
        content="Design safe memory routing",
        domain_hints=["architecture"],
        novelty=0.7,
        risk=0.7,
        uncertainty=0.6,
    )
    registry = CellRegistry(
        [
            CellSpec(
                cell_id="logic_cell",
                role=CellRole.LOGIC,
                domains=["architecture"],
                trust_score=0.8,
            ),
            CellSpec(
                cell_id="unstable_cell",
                role=CellRole.ACTION,
                domains=["architecture"],
                trust_score=0.9,
            ),
        ]
    )
    registry.record_failure("unstable_cell", "failure 1")
    registry.record_failure("unstable_cell", "failure 2")
    registry.record_failure("unstable_cell", "failure 3")

    decision = router.route_registered(task, registry)

    assert decision.selected_cells == ["logic_cell"]
    assert "healthy cells" in decision.rationale


def test_router_rejects_registry_with_only_quarantined_cells() -> None:
    router = ThalamicRouter()
    task = Task(content="Route safely", domain_hints=["action"])
    registry = CellRegistry(
        [
            CellSpec(
                cell_id="unstable_cell",
                role=CellRole.ACTION,
                domains=["action"],
            )
        ]
    )
    registry.record_failure("unstable_cell", "failure 1")
    registry.record_failure("unstable_cell", "failure 2")
    registry.record_failure("unstable_cell", "failure 3")

    with pytest.raises(ValueError, match="registered cells"):
        router.route_registered(task, registry)


def test_global_workspace_updates_confidence() -> None:
    workspace = GlobalWorkspace(
        task_id="task_test",
        goal="verify workspace",
        mode=CognitiveMode.WORKING,
        active_cells=["logic_cell"],
    )

    workspace.add_hypothesis(
        Hypothesis(
            claim="typed state is easier to replay",
            source_cell_id="logic_cell",
            confidence=0.8,
        )
    )
    snapshot = workspace.snapshot()

    assert snapshot.confidence == 0.8
    assert snapshot.hypotheses[0].claim == "typed state is easier to replay"

    workspace.add_issue("missing memory proof")
    assert workspace.snapshot().confidence == 0.7
