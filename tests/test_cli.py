import json

import pytest

from hex_cortex.cli import main, summarize_result
from hex_cortex.core.cortex_pipeline import CortexPipeline
from hex_cortex.core.schemas import Task
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord


def test_cli_outputs_stable_json(capsys) -> None:
    exit_code = main(
        [
            "Classify this local task",
            "--domain",
            "intent",
            "--novelty",
            "0.2",
            "--risk",
            "0.2",
            "--uncertainty",
            "0.2",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["mode"] == "reflex"
    assert "intent_cell" in payload["selected_cells"]
    assert payload["retrieval_method"] == "empty"
    assert payload["matched_skill_count"] == 0
    assert payload["replay_status"] == "consolidated"
    assert payload["clock_completed"] is True


def test_cli_pretty_prints_json(capsys) -> None:
    exit_code = main(["Trace local task", "--pretty"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("{\n")
    assert json.loads(output)["clock_completed"] is True


def test_cli_can_select_working_mode(capsys) -> None:
    main(
        [
            "Analyze this bounded task",
            "--novelty",
            "0.5",
            "--risk",
            "0.5",
            "--uncertainty",
            "0.5",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "working"


def test_cli_persists_spine_jsonl_between_runs(tmp_path, capsys) -> None:
    spine_path = tmp_path / "spine.jsonl"

    main(["First local task", "--spine-jsonl", str(spine_path)])
    first_payload = json.loads(capsys.readouterr().out)
    main(["Second local task", "--spine-jsonl", str(spine_path)])
    second_payload = json.loads(capsys.readouterr().out)

    assert spine_path.exists()
    assert first_payload["persisted_event_count"] > 0
    assert second_payload["persisted_event_count"] > first_payload["persisted_event_count"]


def test_cli_persists_memory_jsonl_between_runs(tmp_path, capsys) -> None:
    memory_path = tmp_path / "memory.jsonl"

    main(["First memory task", "--memory-jsonl", str(memory_path)])
    first_payload = json.loads(capsys.readouterr().out)
    main(["Second memory task", "--memory-jsonl", str(memory_path)])
    second_payload = json.loads(capsys.readouterr().out)

    assert memory_path.exists()
    assert first_payload["persisted_memory_count"] == 1
    assert second_payload["persisted_memory_count"] == 2


def test_cli_hydrates_memory_jsonl_into_index(tmp_path, capsys) -> None:
    memory_path = tmp_path / "memory.jsonl"

    main(["Hydration target phrase", "--memory-jsonl", str(memory_path)])
    first_payload = json.loads(capsys.readouterr().out)
    main(["Hydration target phrase", "--memory-jsonl", str(memory_path)])
    second_payload = json.loads(capsys.readouterr().out)

    assert first_payload["hydrated_memory_count"] == 0
    assert first_payload["retrieval_result_count"] == 0
    assert second_payload["hydrated_memory_count"] == 1
    assert second_payload["retrieval_result_count"] >= 1
    assert second_payload["retrieval_method"] == "exact"


def test_cli_hydrates_active_skills_jsonl(tmp_path, capsys) -> None:
    skills_path = tmp_path / "skills.jsonl"
    active_skill = SkillRecord(
        name="memory workflow",
        description="Use hydrated memory before reasoning.",
        trigger_tags=["memory"],
        workflow_steps=["hydrate", "retrieve", "verify"],
        confidence=0.9,
        status=SkillStatus.ACTIVE,
    )
    candidate_skill = SkillRecord(
        name="candidate workflow",
        description="Not active yet.",
        trigger_tags=["memory"],
        status=SkillStatus.CANDIDATE,
    )
    SkillJsonlStore(skills_path).save([active_skill, candidate_skill])

    main(
        [
            "Use memory workflow",
            "--domain",
            "memory",
            "--skills-jsonl",
            str(skills_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["hydrated_skill_count"] == 1
    assert payload["matched_skill_count"] == 1


def test_cli_bootstraps_skill_jsonl(tmp_path, capsys) -> None:
    skills_path = tmp_path / "skills.jsonl"

    exit_code = main(
        [
            "--bootstrap-skill",
            str(skills_path),
            "--skill-name",
            "memory workflow",
            "--skill-description",
            "Use local memory before reasoning.",
            "--skill-trigger",
            "memory",
            "--skill-step",
            "hydrate",
            "--skill-step",
            "retrieve",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert skills_path.exists()
    assert payload["bootstrapped_skill_count"] == 1
    assert payload["active_skill_count"] == 1
    assert payload["skill_name"] == "memory workflow"
    assert payload["skill_status"] == "active"


def test_cli_bootstrapped_skill_can_be_hydrated(tmp_path, capsys) -> None:
    skills_path = tmp_path / "skills.jsonl"
    main(
        [
            "--bootstrap-skill",
            str(skills_path),
            "--skill-name",
            "memory workflow",
            "--skill-trigger",
            "memory",
        ]
    )
    capsys.readouterr()

    main(
        [
            "Use memory workflow",
            "--domain",
            "memory",
            "--skills-jsonl",
            str(skills_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["hydrated_skill_count"] == 1
    assert payload["matched_skill_count"] == 1


def test_cli_inspects_spine_jsonl(tmp_path, capsys) -> None:
    spine_path = tmp_path / "spine.jsonl"
    main(["Trace inspectable task", "--spine-jsonl", str(spine_path)])
    capsys.readouterr()

    main(["--inspect-spine", str(spine_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["inspect_type"] == "spine"
    assert payload["exists"] is True
    assert payload["integrity_ok"] is True
    assert payload["total_events"] > 0
    assert payload["task_count"] == 1


def test_cli_inspects_memory_jsonl(tmp_path, capsys) -> None:
    memory_path = tmp_path / "memory.jsonl"
    memory = MemoryRecord(title="m", body="b", tags=["compressed"])
    LocalMemoryJsonlStore(memory_path).save([memory])

    main(["--inspect-memory", str(memory_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["inspect_type"] == "memory"
    assert payload["exists"] is True
    assert payload["total_memory_count"] == 1
    assert payload["visible_memory_count"] == 1
    assert payload["tag_counts"] == {"compressed": 1}


def test_cli_inspects_skills_jsonl(tmp_path, capsys) -> None:
    skills_path = tmp_path / "skills.jsonl"
    active_skill = SkillRecord(
        name="active",
        description="Active skill",
        status=SkillStatus.ACTIVE,
    )
    archived_skill = SkillRecord(
        name="archived",
        description="Archived skill",
        status=SkillStatus.ARCHIVED,
    )
    SkillJsonlStore(skills_path).save([active_skill, archived_skill])

    main(["--inspect-skills", str(skills_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["inspect_type"] == "skills"
    assert payload["exists"] is True
    assert payload["total_skill_count"] == 2
    assert payload["active_skill_count"] == 1
    assert payload["archived_skill_count"] == 1


def test_cli_rejects_multiple_inspect_modes(tmp_path) -> None:
    spine_path = tmp_path / "spine.jsonl"
    memory_path = tmp_path / "memory.jsonl"

    with pytest.raises(ValueError, match="only one inspect mode"):
        main(
            [
                "--inspect-spine",
                str(spine_path),
                "--inspect-memory",
                str(memory_path),
            ]
        )


def test_cli_profile_persists_spine_and_memory(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"

    main(["Profile task", "--profile", str(profile)])
    first_payload = json.loads(capsys.readouterr().out)
    main(["Profile task", "--profile", str(profile)])
    second_payload = json.loads(capsys.readouterr().out)

    assert (profile / "spine.jsonl").exists()
    assert (profile / "memory.jsonl").exists()
    assert first_payload["profile_path"] == str(profile)
    assert first_payload["persisted_memory_count"] == 1
    assert second_payload["persisted_event_count"] > first_payload["persisted_event_count"]
    assert second_payload["persisted_memory_count"] == 2
    assert second_payload["hydrated_memory_count"] == 1
    assert second_payload["retrieval_method"] == "exact"


def test_cli_profile_hydrates_skills(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    skills_path = profile / "skills.jsonl"
    SkillJsonlStore(skills_path).save(
        [
            SkillRecord(
                name="memory workflow",
                description="Use hydrated memory before reasoning.",
                trigger_tags=["memory"],
                status=SkillStatus.ACTIVE,
            )
        ]
    )

    main(["Use profile skill", "--profile", str(profile), "--domain", "memory"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["hydrated_skill_count"] == 1
    assert payload["matched_skill_count"] == 1


def test_cli_profile_respects_explicit_path_overrides(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    explicit_memory = tmp_path / "memory.jsonl"

    main(
        [
            "Override memory path",
            "--profile",
            str(profile),
            "--memory-jsonl",
            str(explicit_memory),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert (profile / "spine.jsonl").exists()
    assert not (profile / "memory.jsonl").exists()
    assert explicit_memory.exists()
    assert payload["profile_path"] == str(profile)
    assert payload["persisted_memory_count"] == 1


def test_summarize_result_matches_pipeline_output_contract() -> None:
    result = CortexPipeline().run(
        Task(
            content="Summarize local pipeline result",
            domain_hints=["logic"],
        )
    )

    payload = summarize_result(result)

    assert payload["task_id"] == result.task_id
    assert payload["mode"] == result.routing_decision.mode.value
    assert payload["selected_cells"] == result.routing_decision.selected_cells
    assert payload["clock_completed"] is True
