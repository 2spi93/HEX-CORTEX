from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome
from hex_cortex.memory.cortex_cognitive_genome import build_cr_jepa_v0_manifest
from hex_cortex.memory.cortex_cognitive_genome import build_homeostasis_decision
from hex_cortex.memory.cortex_cognitive_genome import build_mutation_plan
from hex_cortex.memory.cortex_cognitive_genome import build_profile_council
from hex_cortex.memory.cortex_cognitive_genome import build_skill_candidate
from hex_cortex.memory.cortex_cognitive_genome import evaluate_mutation_candidate
from hex_cortex.memory.cortex_cognitive_residuals import append_cognitive_residual
from hex_cortex.memory.cortex_cognitive_residuals import project_residual_topology


def build_cognitive_genome_registry() -> dict[str, CortexUnit]:
    return {
        "genome.audit": CortexUnit(
            name="genome.audit",
            unit=audit_cognitive_genome,
            description="Validate the immutable HEX-CORTEX cognitive genome contract.",
        ),
        "residual.append": CortexUnit(
            name="residual.append",
            unit=append_cognitive_residual,
            description="Append a hashed cognitive residual without raw reasoning persistence.",
            mutates_receipt=True,
        ),
        "residual.topology": CortexUnit(
            name="residual.topology",
            unit=project_residual_topology,
            description="Cluster recurring verified residuals across contexts and models.",
        ),
        "skill.candidate": CortexUnit(
            name="skill.candidate",
            unit=build_skill_candidate,
            description="Build a skill candidate only from recurrent verified residual evidence.",
        ),
        "profiles.council": CortexUnit(
            name="profiles.council",
            unit=build_profile_council,
            description="Select an evidence-weighted council of epistemic profiles.",
        ),
        "homeostasis.decide": CortexUnit(
            name="homeostasis.decide",
            unit=build_homeostasis_decision,
            description="Choose reversible cognitive regulation actions under uncertainty and cost.",
        ),
        "mutation.plan": CortexUnit(
            name="mutation.plan",
            unit=build_mutation_plan,
            description="Plan a reversible mutation with frozen base model and held-out gates.",
            requires_operator=True,
        ),
        "mutation.evaluate": CortexUnit(
            name="mutation.evaluate",
            unit=evaluate_mutation_candidate,
            description="Evaluate mutation improvement and catastrophic-forgetting regressions.",
            requires_operator=True,
        ),
        "cr_jepa.manifest": CortexUnit(
            name="cr_jepa.manifest",
            unit=build_cr_jepa_v0_manifest,
            description="Describe the Cognitive Residual JEPA V0 evidence dataset without training.",
        ),
    }
