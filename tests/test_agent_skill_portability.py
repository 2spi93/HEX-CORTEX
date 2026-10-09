from __future__ import annotations

from pathlib import Path

import pytest

from hex_cortex.evolver.agent_skill_portability import (
    export_active_skills,
    render_agent_skill,
    slugify,
)
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore


def _skill(name: str, status: SkillStatus = SkillStatus.ACTIVE) -> SkillRecord:
    return SkillRecord(
        name=name,
        description="Review and verify Python patches when fixing a repository issue.",
        workflow_steps=["Inspect the failing test", "Make a small patch", "Run pytest"],
        status=status,
    )


def test_render_agent_skill_emits_valid_name_and_description() -> None:
    rendered = render_agent_skill(_skill("Code Review"))
    assert rendered.startswith("---\nname: \"code-review\"\n")
    assert "description: " in rendered
    assert "# Code Review" in rendered
    assert "1. Inspect the failing test" in rendered


def test_candidate_cannot_be_exported() -> None:
    with pytest.raises(ValueError, match="only active"):
        render_agent_skill(_skill("Draft", SkillStatus.CANDIDATE))


def test_slugs_cannot_escape_directory() -> None:
    assert slugify("../Danger/Skill") == "danger-skill"
    with pytest.raises(ValueError):
        slugify("...///")


def test_export_only_active_with_no_skill_execution(tmp_path: Path) -> None:
    registry = tmp_path / "skills.jsonl"
    SkillJsonlStore(registry).save(
        [_skill("Code Review"), _skill("Unapproved", SkillStatus.CANDIDATE)]
    )
    destination = tmp_path / "portable"
    paths = export_active_skills(registry, destination)
    assert paths == [destination / "code-review" / "SKILL.md"]
    assert "Run pytest" in paths[0].read_text(encoding="utf-8")
    assert not (destination / "unapproved").exists()


def test_export_does_not_overwrite_existing_skill(tmp_path: Path) -> None:
    registry = tmp_path / "skills.jsonl"
    SkillJsonlStore(registry).save([_skill("Code Review")])
    destination = tmp_path / "portable"
    export_active_skills(registry, destination)
    with pytest.raises(FileExistsError):
        export_active_skills(registry, destination)


def test_colliding_names_are_rejected_before_writes(tmp_path: Path) -> None:
    registry = tmp_path / "skills.jsonl"
    SkillJsonlStore(registry).save([_skill("Code Review"), _skill("code_review")])
    destination = tmp_path / "portable"
    with pytest.raises(ValueError, match="collide"):
        export_active_skills(registry, destination)
    assert not destination.exists()
