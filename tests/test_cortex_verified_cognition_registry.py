from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_verified_cognition_registry import (
    build_verified_cognition_registry,
)


def test_verified_cognition_registry_exposes_cold_operational_organs() -> None:
    registry = build_verified_cognition_registry()

    assert set(registry) == {
        "compute.strategy",
        "gpu.admission",
        "verification.consensus",
        "verification.adversarial",
        "verification.next",
        "inference.plan",
        "cognitive.loop.plan",
        "repo.graph.build",
        "repo.module.contract",
        "patch.tournament",
        "competence.rule.candidate",
        "pot.grade",
    }
    assert registry["cognitive.loop.plan"].requires_operator is False
    assert registry["competence.rule.candidate"].requires_operator is True


def test_verified_cognition_registry_is_part_of_canonical_bundle() -> None:
    bundle = build_cortex_bundle()

    assert "cognitive.loop.plan" in bundle
    assert "verification.consensus" in bundle
    assert "repo.graph.build" in bundle
    assert "patch.tournament" in bundle
    assert "pot.grade" in bundle
