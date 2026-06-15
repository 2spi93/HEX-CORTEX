import json

from hex_cortex.cli import main, summarize_result
from hex_cortex.core.cortex_pipeline import CortexPipeline
from hex_cortex.core.schemas import Task
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore


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

    main(["Use memory workflow", "--domain", "memory", "--skills-jsonl", str(skills_path)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["hydrated_skill_count"] == 1
    assert payload["matched_skill_count"] == 1


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
