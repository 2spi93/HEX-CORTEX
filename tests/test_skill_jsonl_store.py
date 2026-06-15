import pytest

from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore


def make_skill(name: str, status: SkillStatus = SkillStatus.ACTIVE) -> SkillRecord:
    return SkillRecord(
        name=name,
        description=f"Reusable workflow for {name}.",
        trigger_tags=[name, "workflow"],
        workflow_steps=["inspect", "act", "verify"],
        confidence=0.8,
        status=status,
    )


def test_skill_jsonl_store_loads_empty_list_when_missing(tmp_path) -> None:
    store = SkillJsonlStore(tmp_path / "missing.jsonl")

    assert store.load() == []
    assert store.active() == []


def test_skill_jsonl_store_saves_and_loads_records(tmp_path) -> None:
    path = tmp_path / "skills.jsonl"
    records = [make_skill("memory"), make_skill("logic")]
    store = SkillJsonlStore(path)

    written = store.save(records)
    loaded = store.load()

    assert written == 2
    assert [skill.skill_id for skill in loaded] == [
        records[0].skill_id,
        records[1].skill_id,
    ]


def test_skill_jsonl_store_appends_record_and_returns_count(tmp_path) -> None:
    path = tmp_path / "skills.jsonl"
    store = SkillJsonlStore(path)

    first_count = store.append(make_skill("memory"))
    second_count = store.append(make_skill("logic"))

    assert first_count == 1
    assert second_count == 2
    assert len(store.load()) == 2


def test_skill_jsonl_store_returns_active_skills_only(tmp_path) -> None:
    active = make_skill("active", SkillStatus.ACTIVE)
    candidate = make_skill("candidate", SkillStatus.CANDIDATE)
    archived = make_skill("archived", SkillStatus.ARCHIVED)
    store = SkillJsonlStore(tmp_path / "skills.jsonl")

    store.save([active, candidate, archived])

    assert [skill.skill_id for skill in store.active()] == [active.skill_id]


def test_skill_jsonl_store_rejects_invalid_json_line(tmp_path) -> None:
    path = tmp_path / "skills.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    store = SkillJsonlStore(path)

    with pytest.raises(ValueError, match="invalid JSONL skill record"):
        store.load()
