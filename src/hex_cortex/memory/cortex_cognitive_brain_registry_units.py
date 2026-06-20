from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_brain_registry import project_brain_registry
from hex_cortex.memory.cortex_cognitive_brain_registry import select_cognitive_brain


def build_cognitive_brain_registry() -> dict[str, CortexUnit]:
    return {
        "brain.phenotype.append": CortexUnit(
            name="brain.phenotype.append",
            unit=append_brain_phenotype,
            description="Append a measured interchangeable-brain phenotype.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "brain.registry.project": CortexUnit(
            name="brain.registry.project",
            unit=project_brain_registry,
            description="Project current local, private-remote, and metered brain phenotypes.",
        ),
        "brain.select": CortexUnit(
            name="brain.select",
            unit=select_cognitive_brain,
            description="Select a brain from measured competence, reliability, latency, privacy, and cost.",
        ),
    }
