from pathlib import Path

from hex_cortex.memory.cortex_cognitive_residuals import append_cognitive_residual


def test_residual_ledger_never_persists_raw_state_or_outcome_refs(tmp_path: Path) -> None:
    ledger = tmp_path / "residuals.jsonl"
    payload = append_cognitive_residual(
        ledger,
        model_id="private-model",
        model_family="local",
        domain="hex-cortex",
        context_signature="private-context",
        state_embedding_ref="private-state-ref",
        predicted_outcome_ref="private-predicted-ref",
        observed_outcome_ref="private-observed-ref",
        failure_class="logic_error",
        residual_magnitude=0.1,
        profile_set=["scientist"],
        tool_set=["pytest"],
    )

    text = ledger.read_text(encoding="utf-8")
    assert payload["raw_state_persisted"] is False
    assert payload["raw_outcome_persisted"] is False
    assert "private-context" not in text
    assert "private-state-ref" not in text
    assert "private-predicted-ref" not in text
    assert "private-observed-ref" not in text
