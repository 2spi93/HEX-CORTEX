import json

from hex_cortex.cli import main, summarize_result
from hex_cortex.core.cortex_pipeline import CortexPipeline
from hex_cortex.core.schemas import Task


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
