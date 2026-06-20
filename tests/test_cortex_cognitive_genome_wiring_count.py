from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring


def test_cognitive_wiring_counts_are_complete() -> None:
    payload = audit_cortex_wiring(build_cortex_bundle())
    stages = {row["stage"]: row for row in payload["stage_rows"]}

    assert stages["cognitive_genome"]["present_count"] == 9
    assert stages["cognitive_memory_and_mutation"]["present_count"] == 7
    assert payload["architecture_ready"] is True
