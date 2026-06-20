from pathlib import Path

from hex_cortex.memory.cortex_cognitive_memory import project_adapter_registry
from hex_cortex.memory.cortex_cognitive_memory import register_adapter_candidate
from hex_cortex.memory.cortex_cognitive_memory import transition_adapter_status


def test_promoted_adapter_can_be_revoked_with_operator_approval(tmp_path: Path) -> None:
    ledger = tmp_path / "adapters.jsonl"
    register_adapter_candidate(
        ledger,
        adapter_id="adapter-a",
        base_model_id="base-model",
        skill_id="skill-a",
        plan_hash="a" * 64,
        checkpoint_hash="b" * 64,
        reversible=True,
    )
    transition_adapter_status(
        ledger,
        adapter_id="adapter-a",
        new_status="evaluated",
        evaluation_hash="c" * 64,
        operator_approved=False,
    )
    transition_adapter_status(
        ledger,
        adapter_id="adapter-a",
        new_status="promoted",
        evaluation_hash="d" * 64,
        operator_approved=True,
    )
    transition_adapter_status(
        ledger,
        adapter_id="adapter-a",
        new_status="revoked",
        evaluation_hash="e" * 64,
        operator_approved=True,
    )

    payload = project_adapter_registry(ledger)
    assert payload["revoked_adapter_ids"] == ["adapter-a"]
    assert payload["base_model_immutable"] is True
