from pathlib import Path

from hex_cortex.memory.cortex_cognitive_memory import append_competency_baseline
from hex_cortex.memory.cortex_cognitive_memory import project_adapter_registry


def test_empty_adapter_registry_preserves_base_model_immutability(tmp_path: Path) -> None:
    payload = project_adapter_registry(tmp_path / "missing.jsonl")

    assert payload["adapter_count"] == 0
    assert payload["base_model_immutable"] is True


def test_baseline_keeps_model_identity_hashed(tmp_path: Path) -> None:
    ledger = tmp_path / "baseline.jsonl"
    payload = append_competency_baseline(
        ledger,
        model_id="model-private-id",
        suite_ref="suite-private-ref",
        metrics={"critical": 1.0},
        critical_competencies=["critical"],
    )

    assert payload["raw_model_identifier_persisted"] is False
    assert "model-private-id" not in ledger.read_text(encoding="utf-8")
