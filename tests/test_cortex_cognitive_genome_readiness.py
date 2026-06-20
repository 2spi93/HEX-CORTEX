from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import audit_cognitive_genome


def test_genome_audit_is_deterministic() -> None:
    first = audit_cognitive_genome(Path("config/cognitive_genome_v1.json"))
    second = audit_cognitive_genome(Path("config/cognitive_genome_v1.json"))

    assert first["genome_ready"] is True
    assert first["audit_hash"] == second["audit_hash"]
