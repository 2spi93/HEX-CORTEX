from pathlib import Path

from hex_cortex.memory.cortex_cognitive_memory import project_skill_graph


def test_empty_skill_graph_is_valid_before_evidence_collection(tmp_path: Path) -> None:
    payload = project_skill_graph(tmp_path / "missing.jsonl")

    assert payload["graph_valid"] is True
    assert payload["node_count"] == 0
