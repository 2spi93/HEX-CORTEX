"""Cross-domain validated scientific memory; reject hash-consistent forgeries."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_verified_science_memory_v23 import (
    append_verified_science_fact,
    verify_science_fact_task,
)
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore

_PHYSICS = json.dumps({
    "law": "force",
    "inputs": {
        "mass": {"value": "2", "unit": "kg"},
        "acceleration": {"value": "3", "unit": "m/s^2"},
    },
})
_CHEMISTRY = json.dumps({
    "reactants": ["H2", "O2"], "products": ["H2O"]
})


@pytest.mark.parametrize(("domain", "request_text", "needle"), [
    ("physics", _PHYSICS, "6/1 N"),
    ("chemistry", _CHEMISTRY, '"coefficient":2'),
])
def test_true_scientific_fact_promote_checkpoint_and_restore(
    tmp_path: Path, domain: str, request_text: str, needle: str,
) -> None:
    spine = CanonicalSpine()
    fact = append_verified_science_fact(
        spine, domain=domain, task_id="verified-source",
        request_text=request_text, approved=True,
    )
    assert fact["status"] == "verified_science_fact_recorded"
    assert fact["model_called"] is False
    assert verify_science_fact_task(spine, "verified-source")
    learning = VerifiedLearningLoop(spine=spine)
    out = learning.run(
        task_id="verified-source",
        query=RetrievalQuery(query="Verified idealized"),
        approve_promotion=True,
    )
    assert out.promotion is not None
    assert out.promotion.status.value == "promoted"
    assert needle in out.context.context_text
    assert len(learning.index.entries) == 1
    CanonicalSpineJsonlStore(tmp_path / "science-spine.jsonl").save(spine)
    learning.save_checkpoint(
        project_root=tmp_path,
        relative_path=Path("science-checkpoint.jsonl"),
        approved=True,
    )
    loaded_spine = CanonicalSpineJsonlStore(tmp_path / "science-spine.jsonl").load()
    restored = VerifiedLearningLoop.restore_checkpoint(
        project_root=tmp_path,
        relative_path=Path("science-checkpoint.jsonl"),
        spine=loaded_spine,
    )
    assert len(restored.index.entries) == 1
    assert len(restored.checkpoint_records) == 1


@pytest.mark.parametrize(("domain", "request_text"), [
    ("physics", _PHYSICS),
    ("chemistry", _CHEMISTRY),
])
def test_false_claim_in_valid_hash_chain_is_rejected_before_index_mutation(
    domain: str, request_text: str,
) -> None:
    authentic = CanonicalSpine()
    append_verified_science_fact(
        authentic, domain=domain, task_id="source",
        request_text=request_text, approved=True,
    )
    payload = dict(authentic.events[0].payload)
    payload["observations"] = ["Verified idealized false fact = 99999"]
    false = CanonicalSpine()
    false.append(
        event_type="science.verified_domain_fact", task_id="source",
        source="VerifiedScienceCircuit", payload=payload, confidence=1.0,
    )
    false.append(
        event_type="clock.completed", task_id="source",
        source="VerifiedScienceMemory", payload={"completed": True}, confidence=1.0,
    )
    assert false.verify_integrity().ok
    assert not verify_science_fact_task(false, "source")
    learning = VerifiedLearningLoop(spine=false)
    attempted = learning.run(
        task_id="source", query=RetrievalQuery(query="Verified"),
        approve_promotion=True,
    )
    assert attempted.promotion is not None
    assert attempted.promotion.status.value == "rejected"
    assert attempted.promotion.details["reason"] == "science_fact_source_not_verified"
    assert len(learning.index.entries) == 0
    assert not learning.checkpoint_records


def test_unapproved_science_fact_creates_no_events() -> None:
    spine = CanonicalSpine()
    with pytest.raises(PermissionError, match="science_fact_operator_approval_required"):
        append_verified_science_fact(
            spine, domain="physics", task_id="test", request_text=_PHYSICS
        )
    assert not spine.events


def test_unsupported_domain_or_invalid_input_refused_without_events() -> None:
    spine = CanonicalSpine()
    with pytest.raises(ValueError, match="unsupported_science_fact_domain"):
        append_verified_science_fact(
            spine, domain="robotics", task_id="source",
            request_text="{}", approved=True,
        )
    with pytest.raises(ValueError, match="science_fact_not_verified"):
        append_verified_science_fact(
            spine, domain="chemistry", task_id="source",
            request_text='{"danger":"unknown"}', approved=True,
        )
    assert spine.events == []
