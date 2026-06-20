from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_cognitive_memory import append_causal_intervention
from hex_cortex.memory.cortex_cognitive_memory import append_competency_baseline
from hex_cortex.memory.cortex_cognitive_memory import append_skill_graph_node
from hex_cortex.memory.cortex_cognitive_memory import project_adapter_registry
from hex_cortex.memory.cortex_cognitive_memory import project_skill_graph
from hex_cortex.memory.cortex_cognitive_memory import register_adapter_candidate
from hex_cortex.memory.cortex_cognitive_memory import transition_adapter_status


def build_cognitive_memory_registry() -> dict[str, CortexUnit]:
    return {
        "competency.baseline": CortexUnit(
            name="competency.baseline",
            unit=append_competency_baseline,
            description="Append a hashed baseline of preserved model competencies.",
            mutates_receipt=True,
        ),
        "causal.intervention": CortexUnit(
            name="causal.intervention",
            unit=append_causal_intervention,
            description="Record a verified control-versus-treatment cognitive intervention.",
            mutates_receipt=True,
        ),
        "skill.graph.append": CortexUnit(
            name="skill.graph.append",
            unit=append_skill_graph_node,
            description="Append a verified skill node with explicit dependencies.",
            mutates_receipt=True,
        ),
        "skill.graph.project": CortexUnit(
            name="skill.graph.project",
            unit=project_skill_graph,
            description="Project and validate the persistent cognitive skill graph.",
        ),
        "adapter.register": CortexUnit(
            name="adapter.register",
            unit=register_adapter_candidate,
            description="Register a reversible isolated adapter against an immutable base model.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "adapter.transition": CortexUnit(
            name="adapter.transition",
            unit=transition_adapter_status,
            description="Apply an append-only evaluated adapter lifecycle transition.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "adapter.project": CortexUnit(
            name="adapter.project",
            unit=project_adapter_registry,
            description="Project active, rejected, promoted, and revoked adapters.",
        ),
    }
