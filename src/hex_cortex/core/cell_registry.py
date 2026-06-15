"""Cell registry for HEX-CORTEX.

The registry is the living inventory of available cognitive cells. It bridges
static CellSpec records with dynamic CellHealth from HEX-EVOLVER.
"""

from __future__ import annotations

from collections.abc import Iterable

from hex_cortex.core.schemas import CellRole, CellSpec
from hex_cortex.evolver.schemas import CellHealth


class CellRegistry:
    """Registry of available cognitive cells and their runtime health."""

    def __init__(self, cells: Iterable[CellSpec] | None = None) -> None:
        self._cells: dict[str, CellSpec] = {}
        self._health: dict[str, CellHealth] = {}

        for cell in cells or []:
            self.register(cell)

    @property
    def cells(self) -> list[CellSpec]:
        """Return active cell specs with runtime health applied."""

        return [self._apply_health(cell) for cell in self._cells.values()]

    @property
    def health_records(self) -> list[CellHealth]:
        """Return health records for known cells."""

        return [record.model_copy(deep=True) for record in self._health.values()]

    def register(self, cell: CellSpec, health: CellHealth | None = None) -> CellSpec:
        """Register or replace a cell."""

        if cell.cell_id in self._cells:
            raise ValueError(f"cell already registered: {cell.cell_id}")

        self._cells[cell.cell_id] = cell
        self._health[cell.cell_id] = health or CellHealth(
            cell_id=cell.cell_id,
            trust_score=cell.trust_score,
        )
        return self._apply_health(cell)

    def unregister(self, cell_id: str) -> None:
        """Remove a cell and its health record."""

        self._cells.pop(cell_id, None)
        self._health.pop(cell_id, None)

    def get(self, cell_id: str) -> CellSpec | None:
        """Return one cell spec with health applied."""

        cell = self._cells.get(cell_id)
        if cell is None:
            return None
        return self._apply_health(cell)

    def by_role(self, role: CellRole) -> list[CellSpec]:
        """Return all non-quarantined cells for a role."""

        return [cell for cell in self.cells if cell.role == role]

    def matching_domains(self, domains: list[str]) -> list[CellSpec]:
        """Return cells matching at least one requested domain.

        Empty domain requests return all available cells.
        """

        if not domains:
            return self.cells

        requested = {domain.lower() for domain in domains}
        return [
            cell
            for cell in self.cells
            if requested.intersection({domain.lower() for domain in cell.domains})
        ]

    def update_health(self, health: CellHealth) -> CellSpec | None:
        """Update health for a registered cell."""

        if health.cell_id not in self._cells:
            return None
        self._health[health.cell_id] = health
        return self._apply_health(self._cells[health.cell_id])

    def record_success(self, cell_id: str) -> CellHealth:
        """Record a successful cell execution and raise trust conservatively."""

        health = self._health_for(cell_id)
        success_count = health.success_count + 1
        failure_count = health.failure_count
        trust_score = self._trust_from_counts(success_count, failure_count)
        updated = health.model_copy(
            update={
                "success_count": success_count,
                "trust_score": trust_score,
                "quarantine": False,
                "requires_double_check": False,
                "last_issue": None,
            }
        )
        self._health[cell_id] = updated
        return updated

    def record_failure(self, cell_id: str, issue: str) -> CellHealth:
        """Record a failed cell execution and degrade trust."""

        health = self._health_for(cell_id)
        success_count = health.success_count
        failure_count = health.failure_count + 1
        trust_score = self._trust_from_counts(success_count, failure_count)
        quarantine = failure_count >= 3 and trust_score < 0.45
        updated = health.model_copy(
            update={
                "failure_count": failure_count,
                "trust_score": trust_score,
                "requires_double_check": trust_score < 0.65,
                "quarantine": quarantine,
                "last_issue": issue,
            }
        )
        self._health[cell_id] = updated
        return updated

    def available(self) -> list[CellSpec]:
        """Return cells that are not quarantined."""

        return [
            cell
            for cell in self._cells.values()
            if not self._health_for(cell.cell_id).quarantine
        ]

    def _apply_health(self, cell: CellSpec) -> CellSpec:
        health = self._health_for(cell.cell_id)
        if health.quarantine:
            return cell.model_copy(
                update={
                    "trust_score": 0.0,
                    "recent_error_penalty": 1.0,
                }
            )

        penalty = min(1.0, health.failure_count * 0.15)
        return cell.model_copy(
            update={
                "trust_score": health.trust_score,
                "recent_error_penalty": penalty,
            }
        )

    def _health_for(self, cell_id: str) -> CellHealth:
        if cell_id not in self._cells:
            raise KeyError(f"unknown cell: {cell_id}")
        if cell_id not in self._health:
            self._health[cell_id] = CellHealth(cell_id=cell_id)
        return self._health[cell_id]

    @staticmethod
    def _trust_from_counts(success_count: int, failure_count: int) -> float:
        total = success_count + failure_count
        if total == 0:
            return 0.75
        # Conservative smoothing: one virtual success and one virtual failure.
        return round((success_count + 1) / (total + 2), 10)
