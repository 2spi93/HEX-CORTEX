import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_memory_cli import main


def test_memory_cli_writes_competency_baseline(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "baselines.jsonl"
    code = main(
        [
            "baseline",
            "--ledger",
            str(ledger),
            "--model-id",
            "model-a",
            "--suite-ref",
            "suite-a",
            "--metrics-json",
            '{"architecture": 1.0, "coding": 0.8}',
            "--critical",
            "architecture",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["record_type"] == "competency_baseline_v1"
    assert ledger.is_file()


def test_memory_cli_blocks_irreversible_adapter(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "adapters.jsonl"
    code = main(
        [
            "adapter-register",
            "--ledger",
            str(ledger),
            "--adapter-id",
            "adapter-a",
            "--base-model-id",
            "model-a",
            "--skill-id",
            "skill-a",
            "--plan-hash",
            "a" * 64,
            "--checkpoint-hash",
            "b" * 64,
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert "adapter candidate must be reversible" in payload["blockers"]


def test_memory_cli_projects_empty_skill_graph(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "skills.jsonl"
    code = main(["skill-graph", "--ledger", str(ledger)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["graph_valid"] is True
    assert payload["node_count"] == 0
