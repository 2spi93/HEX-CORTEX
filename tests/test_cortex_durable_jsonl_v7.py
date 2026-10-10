"""Regression evidence: atomic JSONL replacement, locking, and idempotence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_durable_jsonl_v7 as durable
from hex_cortex.memory.cortex_learning_event import (
    CortexLearningEventJsonlStore,
    CortexLearningEventRecord,
)
from hex_cortex.memory.cortex_skill_candidate import (
    CortexSkillCandidateJsonlStore,
    CortexSkillCandidateRecord,
)
from hex_cortex.memory.cortex_skill_library import (
    CortexSkillLibraryJsonlStore,
    build_cortex_skill_library,
)
from hex_cortex.memory.cortex_skill_library_promotion_gate import (
    CortexSkillLibraryPromotionGateJsonlStore,
    build_cortex_skill_library_promotion_gate,
)


def _learning(profile: Path) -> CortexLearningEventRecord:
    return CortexLearningEventRecord(
        profile_path=str(profile), outcome="correction", domain="coding", scope="repo",
        source_ref="test-proof-1", problem="Incorrect limits in test",
        action_taken="Applied change in isolated tests",
        result="Observed corrected output with tests",
        lesson="Verify corrected boundaries with tests",
        reusable_rule="Always check limits with two independent tests",
        confidence=0.95, promote_to_skill=True,
        event_status="accepted", event_decision="learning_event_accepted",
        event_allowed=True, blockers=[], learning_hash="a" * 64, reasons=[],
    )


def _candidate(profile: Path) -> CortexSkillCandidateRecord:
    return CortexSkillCandidateRecord(
        profile_path=str(profile), skill_key="coding:abc", domain="coding",
        source_learning_ids=["event1"], source_learning_hashes=["a" * 64],
        reusable_rule="Always verify changed boundaries using tests",
        evidence_count=1, average_confidence=0.95,
        candidate_status="ready", candidate_decision="skill_candidate_ready",
        candidate_allowed=True, promote_to_library=True,
        blockers=[], next_action="prepare_skill_library_promotion",
        candidate_hash="b" * 64, reasons=["verified"],
    )


def test_atomic_replace_failure_keeps_previous_bytes_and_cleans_tmp(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_bytes(b'{"initial":true}\n')

    def replacement_fail(source, target):
        raise OSError("simulated crash at replace")

    monkeypatch.setattr(durable.os, "replace", replacement_fail)
    with pytest.raises(OSError, match="simulated crash"):
        with durable.exclusive_jsonl_writer(path):
            durable.atomic_jsonl_snapshot(path, ['{"updated":true}'])
    assert path.read_bytes() == b'{"initial":true}\n'
    assert not list(tmp_path.glob("*.write-lock"))
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_lock_blocks_writer_without_touching_content(tmp_path: Path) -> None:
    path = tmp_path / "memory.jsonl"
    path.write_text("original\n", encoding="utf-8")
    lock = tmp_path / "memory.jsonl.write-lock"
    lock.mkdir()
    with pytest.raises(ValueError, match="writer_already_active"):
        with durable.exclusive_jsonl_writer(path):
            durable.atomic_jsonl_snapshot(path, ["new"])
    assert path.read_text(encoding="utf-8") == "original\n"
    assert lock.exists()


def test_symlink_target_is_denied_when_supported(tmp_path: Path) -> None:
    target = tmp_path / "protected.jsonl"
    target.write_text("safe\n", encoding="utf-8")
    link = tmp_path / "redirect.jsonl"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("test host cannot create file symlink")
    with pytest.raises(ValueError, match="symlink"):
        with durable.exclusive_jsonl_writer(link):
            durable.atomic_jsonl_snapshot(link, ["unsafe"])
    assert target.read_text(encoding="utf-8") == "safe\n"


def test_invalid_jsonl_does_not_get_overwritten_when_appending(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"bad":', encoding="utf-8")
    before = path.read_bytes()
    store = CortexLearningEventJsonlStore(path)
    with pytest.raises(ValueError, match="invalid cortex learning event"):
        store.append(_learning(tmp_path))
    assert path.read_bytes() == before
    assert not (tmp_path / "events.jsonl.write-lock").exists()


def test_learning_retry_idempotent_by_event_id(tmp_path: Path) -> None:
    store = CortexLearningEventJsonlStore(tmp_path / "events.jsonl")
    event = _learning(tmp_path)
    assert store.append(event) == 1
    before = store.path.read_bytes()
    assert store.append(event) == 1
    assert store.path.read_bytes() == before
    assert store.load()[0].learning_id == event.learning_id


def test_candidate_retry_idempotent_by_evidence_hash(tmp_path: Path) -> None:
    store = CortexSkillCandidateJsonlStore(tmp_path / "candidates.jsonl")
    candidate = _candidate(tmp_path)
    assert store.append_many([candidate]) == 1
    assert store.append_many([candidate]) == 1
    assert len(store.load()) == 1


def test_library_and_gate_are_registered_once_without_activation(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    candidate = _candidate(profile)
    CortexSkillCandidateJsonlStore(
        profile / "cortex-skill-candidate.jsonl"
    ).append_many([candidate])
    first = build_cortex_skill_library(profile)
    second = build_cortex_skill_library(profile)
    assert first["library_count"] == second["library_count"] == 1
    registered = CortexSkillLibraryJsonlStore(
        profile / "cortex-skill-library.jsonl"
    ).load()
    assert registered[0].active is False
    assert registered[0].activation_status == "inactive_pending_gate"
    first_gate = build_cortex_skill_library_promotion_gate(profile)
    second_gate = build_cortex_skill_library_promotion_gate(profile)
    assert first_gate["gate_count"] == second_gate["gate_count"] == 1
    assert len(CortexSkillLibraryPromotionGateJsonlStore(
        profile / "cortex-skill-library-promotion-gate.jsonl"
    ).load()) == 1


def test_unicode_newline_stable_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "unicode.jsonl"
    items = [json.dumps({"text": "écart\ncontrôlé"}, ensure_ascii=False)]
    with durable.exclusive_jsonl_writer(path):
        durable.atomic_jsonl_snapshot(path, items)
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0]) == {
        "text": "écart\ncontrôlé"
    }
    assert path.read_bytes().endswith(b"\n")


def test_reject_literal_multiline_jsonl_without_destroying_old(tmp_path: Path) -> None:
    path = tmp_path / "safe.jsonl"
    path.write_text("unchanged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line_malformed"):
        with durable.exclusive_jsonl_writer(path):
            durable.atomic_jsonl_snapshot(path, ["a\nb"])
    assert path.read_text(encoding="utf-8") == "unchanged\n"
    assert not list(tmp_path.glob("*.tmp"))
