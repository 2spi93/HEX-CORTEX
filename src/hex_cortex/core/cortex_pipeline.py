"""Cortex pipeline orchestration for HEX-CORTEX."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_clock import CognitiveClock, RegisteredTick, TickName
from hex_cortex.core.router import ThalamicRouter
from hex_cortex.core.schemas import CellRole, CellSpec, RoutingDecision, Task
from hex_cortex.evolver.pruning import PruningBatchReport, PruningEngine
from hex_cortex.evolver.schemas import SkillRecord
from hex_cortex.evolver.skill_library import SkillLibrary
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.retrieval_router import RetrievalRouter
from hex_cortex.memory.schemas import ContextPacket, RetrievalQuery
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayReport
from hex_cortex.spine.canonical_spine import CanonicalSpine


class CortexPipelineResult(BaseModel):
    """Result of one local cortex pipeline pass."""

    task_id: str
    context_packet: ContextPacket
    matched_skills: list[SkillRecord] = Field(default_factory=list)
    routing_decision: RoutingDecision
    replay_report: ReplayReport
    pruning_report: PruningBatchReport
    clock_completed: bool


class CortexPipeline:
    """Local facade that connects the HEX-CORTEX foundation modules."""

    def __init__(
        self,
        *,
        spine: CanonicalSpine | None = None,
        index: LocalKnowledgeIndex | None = None,
        skill_library: SkillLibrary | None = None,
        cell_registry: CellRegistry | None = None,
        router: ThalamicRouter | None = None,
        pruning_engine: PruningEngine | None = None,
    ) -> None:
        self.spine = spine or CanonicalSpine()
        self.index = index or LocalKnowledgeIndex()
        self.retrieval_router = RetrievalRouter(self.index)
        self.skill_library = skill_library or SkillLibrary()
        self.cell_registry = cell_registry or CellRegistry(self.default_cells())
        self.router = router or ThalamicRouter()
        self.replay_engine = ReplayEngine(spine=self.spine)
        self.pruning_engine = pruning_engine or PruningEngine()

    def run(self, task: Task) -> CortexPipelineResult:
        self._append_task_received(task)
        context_packet = self._retrieve(task)
        matched_skills = self._match_skills(task)
        routing_decision = self.router.route_registered(task, self.cell_registry)
        self._append_routing_decision(routing_decision)

        clock = CognitiveClock(
            spine=self.spine,
            max_ticks=routing_decision.budget.max_ticks,
            max_latency_ms=routing_decision.budget.latency_budget_ms,
        )
        clock_report = clock.run(
            task=task,
            mode=routing_decision.mode,
            ticks=self._ticks(context_packet, matched_skills, routing_decision),
        )

        replay_report = self.replay_engine.replay_task(task.task_id)
        self._append_replay_report(replay_report)

        memories = [replay_report.memory] if replay_report.memory is not None else []
        pruning_report = self.pruning_engine.decide_batch(
            memories=memories,
            skills=matched_skills,
            cells=self.cell_registry.health_records,
        )
        self._append_pruning_report(task.task_id, pruning_report)

        return CortexPipelineResult(
            task_id=task.task_id,
            context_packet=context_packet,
            matched_skills=matched_skills,
            routing_decision=routing_decision,
            replay_report=replay_report,
            pruning_report=pruning_report,
            clock_completed=clock_report.completed,
        )

    @staticmethod
    def default_cells() -> list[CellSpec]:
        return [
            CellSpec(cell_id="intent_cell", role=CellRole.INTENT, domains=["intent"]),
            CellSpec(cell_id="memory_cell", role=CellRole.MEMORY, domains=["memory"]),
            CellSpec(cell_id="logic_cell", role=CellRole.LOGIC, domains=["logic"]),
            CellSpec(cell_id="critic_cell", role=CellRole.CRITIC, domains=["safety"]),
            CellSpec(cell_id="action_cell", role=CellRole.ACTION, domains=["action"]),
        ]
