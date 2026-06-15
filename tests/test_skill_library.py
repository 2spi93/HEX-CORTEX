import pytest

from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_library import SkillLibrary


def make_skill(
    name: str,
    trigger_tags: list[str],
    confidence: float = 0.5,
    status: SkillStatus = SkillStatus.CANDIDATE,
) -> SkillRecord:
    return SkillRecord(
        name=name,
        description=f"Reusable workflow for {name}.",
        trigger_tags=trigger_tags,
        workflow_steps=["inspect", "act", "verify"],
        confidence=confidence,
        status=status,
    )


def test_skill_library_adds_and_gets_skill() -> None:
    library = SkillLibrary()
    skill = make_skill("memory compression", ["memory", "compression"])

    added = library.add(skill)

    assert added.skill_id == skill.skill_id
    assert library.get(skill.skill_id) is not None
    assert library.get("missing") is None


def test_skill_library_rejects_duplicate_skill() -> None:
    skill = make_skill("retrieval", ["memory"])
    library = SkillLibrary([skill])

    with pytest.raises(ValueError, match="already registered"):
        library.add(skill)


def test_skill_library_searches_active_skills_by_tag_and_confidence() -> None:
    high = make_skill("router repair", ["router"], confidence=0.9, status=SkillStatus.ACTIVE)
    low = make_skill("router draft", ["router"], confidence=0.6, status=SkillStatus.ACTIVE)
    candidate = make_skill("candidate", ["router"], confidence=0.95)
    unrelated = make_skill("memory", ["memory"], confidence=1.0, status=SkillStatus.ACTIVE)
    library = SkillLibrary([low, unrelated, high, candidate])

    matches = library.search(["router"])

    assert [skill.skill_id for skill in matches] == [high.skill_id, low.skill_id]


def test_skill_library_can_include_candidates_in_search() -> None:
    candidate = make_skill("candidate", ["router"], confidence=0.95)
    active = make_skill("active", ["router"], confidence=0.8, status=SkillStatus.ACTIVE)
    library = SkillLibrary([active, candidate])

    matches = library.search(["router"], include_candidates=True)

    assert [skill.skill_id for skill in matches] == [candidate.skill_id, active.skill_id]


def test_skill_library_records_success_and_activates_skill() -> None:
    skill = make_skill("compression", ["memory"])
    library = SkillLibrary([skill])

    updated = library.record_success(skill.skill_id)

    assert updated.success_count == 1
    assert updated.confidence == pytest.approx(2 / 3)
    assert updated.status == SkillStatus.ACTIVE


def test_skill_library_records_failure_and_degrades_skill() -> None:
    skill = make_skill(
        "fragile workflow",
        ["router"],
        confidence=0.8,
        status=SkillStatus.ACTIVE,
    )
    library = SkillLibrary([skill])

    updated = library.record_failure(skill.skill_id)

    assert updated.failure_count == 1
    assert updated.confidence == pytest.approx(1 / 3)
    assert updated.status == SkillStatus.ARCHIVED


def test_skill_library_manual_status_transitions() -> None:
    skill = make_skill("manual", ["ops"])
    library = SkillLibrary([skill])

    active = library.activate(skill.skill_id)
    degraded = library.degrade(skill.skill_id)
    archived = library.archive(skill.skill_id)

    assert active.status == SkillStatus.ACTIVE
    assert degraded.status == SkillStatus.DEGRADED
    assert archived.status == SkillStatus.ARCHIVED
    assert library.active() == []


def test_skill_library_unknown_skill_raises_key_error() -> None:
    library = SkillLibrary()

    with pytest.raises(KeyError, match="unknown skill"):
        library.record_success("missing")
