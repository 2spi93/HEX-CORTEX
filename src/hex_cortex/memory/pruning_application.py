"""Apply pruning decisions to local memory records conservatively."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hex_cortex.evolver.pruning import PruningAction, PruningBatchReport
from hex_cortex.memory.schemas import MemoryRecord


class MemoryPruningChange(BaseModel):
    """One proposed or applied memory pruning change."""

    memory_id: str
    action: PruningAction
    reason: str
    changed: bool
    before_visible: bool
    after_visible: bool
    dry_run: bool


class MemoryPruningApplicationReport(BaseModel):
    """Result of applying memory pruning decisions."""

    dry_run: bool
    total_memory_count: int
    decision_count: int
    changed_count: int
    visible_before: int
    visible_after: int
    changes: list[MemoryPruningChange] = Field(default_factory=list)
    memories: list[MemoryRecord] = Field(default_factory=list)


class MemoryPruningApplication:
    """Conservative memory-only pruning decision applier."""

    def __init__(self, memories: list[MemoryRecord]) -> None:
        self.memories = memories

    def apply(
        self,
        report: PruningBatchReport,
        *,
        dry_run: bool = True,
    ) -> MemoryPruningApplicationReport:
        """Apply archive decisions to memory visibility.

        In v0.1, only memory archive decisions can mutate state, and only when
        dry_run is false. Degrade decisions are reported but not mutated.
        """

        by_id = {memory.memory_id: memory for memory in self.memories}
        next_memories = [memory.model_copy(deep=True) for memory in self.memories]
        next_by_id = {memory.memory_id: memory for memory in next_memories}
        changes = []

        for decision in report.decisions:
            if decision.target_type != "memory":
                continue
            memory = by_id.get(decision.target_id)
            next_memory = next_by_id.get(decision.target_id)
            if memory is None or next_memory is None:
                continue
            after_visible = self._after_visible(memory, decision.action)
            changed = memory.visible != after_visible
            if changed and not dry_run:
                replacement = next_memory.model_copy(update={"visible": after_visible})
                next_by_id[decision.target_id] = replacement
                index = next(
                    idx for idx, item in enumerate(next_memories) if item.memory_id == decision.target_id
                )
                next_memories[index] = replacement
            changes.append(
                MemoryPruningChange(
                    memory_id=memory.memory_id,
                    action=decision.action,
                    reason=decision.reason,
                    changed=changed,
                    before_visible=memory.visible,
                    after_visible=after_visible,
                    dry_run=dry_run,
                )
            )

        visible_before = sum(1 for memory in self.memories if memory.visible)
        visible_after = sum(1 for memory in next_memories if memory.visible)
        return MemoryPruningApplicationReport(
            dry_run=dry_run,
            total_memory_count=len(self.memories),
            decision_count=len(report.decisions),
            changed_count=sum(1 for change in changes if change.changed),
            visible_before=visible_before,
            visible_after=visible_after,
            changes=changes,
            memories=next_memories,
        )

    @staticmethod
    def _after_visible(memory: MemoryRecord, action: PruningAction) -> bool:
        if action == PruningAction.ARCHIVE and memory.deletable:
            return False
        return memory.visible
