from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome import build_cr_jepa_v0_manifest


def test_cr_jepa_training_is_disabled_with_empty_ledger(tmp_path: Path) -> None:
    payload = build_cr_jepa_v0_manifest(tmp_path / "missing.jsonl")

    assert payload["training_allowed"] is False
    assert payload["residual_count"] == 0
    assert payload["next_action"] == "collect_residual_dataset"
