import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.schemas import CellRole, CellSpec
from hex_cortex.evolver.schemas import CellHealth


def make_cell(
    cell_id: str,
    role: CellRole,
    domains: list[str] | None = None,
) -> CellSpec:
    return CellSpec(
        cell_id=cell_id,
        role=role,
        domains=domains or [],
        trust_score=0.75,
        latency_cost=0.2,
    )


def test_cell_registry_registers_and_gets_cells() -> None:
    registry = CellRegistry()
    cell = make_cell("logic_cell", CellRole.LOGIC, ["architecture"])

    registered = registry.register(cell)

    assert registered.cell_id == "logic_cell"
    assert registry.get("logic_cell") is not None
    assert registry.get("missing") is None


def test_cell_registry_rejects_duplicate_registration() -> None:
    registry = CellRegistry([make_cell("logic_cell", CellRole.LOGIC)])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(make_cell("logic_cell", CellRole.LOGIC))


def test_cell_registry_filters_by_role_and_domain() -> None:
    registry = CellRegistry(
        [
            make_cell("logic_cell", CellRole.LOGIC, ["architecture"]),
            make_cell("memory_cell", CellRole.MEMORY, ["memory"]),
            make_cell("critic_cell", CellRole.CRITIC, ["architecture", "safety"]),
        ]
    )

    assert [cell.cell_id for cell in registry.by_role(CellRole.LOGIC)] == ["logic_cell"]
    assert [cell.cell_id for cell in registry.matching_domains(["memory"])] == [
        "memory_cell"
    ]
    assert {cell.cell_id for cell in registry.matching_domains(["architecture"])} == {
        "logic_cell",
        "critic_cell",
    }


def test_cell_registry_updates_trust_after_success_and_failure() -> None:
    registry = CellRegistry([make_cell("logic_cell", CellRole.LOGIC)])

    success = registry.record_success("logic_cell")
    failure = registry.record_failure("logic_cell", "bad reasoning")
    updated_cell = registry.get("logic_cell")

    assert success.success_count == 1
    assert failure.failure_count == 1
    assert failure.requires_double_check is True
    assert updated_cell is not None
    assert updated_cell.recent_error_penalty == 0.15


def test_cell_registry_quarantines_repeated_failures() -> None:
    registry = CellRegistry([make_cell("unstable_cell", CellRole.ACTION)])

    registry.record_failure("unstable_cell", "failure 1")
    registry.record_failure("unstable_cell", "failure 2")
    health = registry.record_failure("unstable_cell", "failure 3")
    cell = registry.get("unstable_cell")

    assert health.quarantine is True
    assert cell is not None
    assert cell.trust_score == 0.0
    assert cell.recent_error_penalty == 1.0
    assert registry.available() == []


def test_cell_registry_applies_external_health_record() -> None:
    registry = CellRegistry([make_cell("critic_cell", CellRole.CRITIC)])
    health = CellHealth(
        cell_id="critic_cell",
        trust_score=0.2,
        failure_count=4,
        quarantine=True,
        last_issue="unstable critique",
    )

    updated = registry.update_health(health)

    assert updated is not None
    assert updated.trust_score == 0.0
    assert registry.health_records[0].last_issue == "unstable critique"


def test_cell_registry_unknown_failure_raises_key_error() -> None:
    registry = CellRegistry()

    with pytest.raises(KeyError, match="unknown cell"):
        registry.record_failure("missing", "no such cell")
