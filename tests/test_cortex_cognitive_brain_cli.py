import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_cli import main


def test_brain_cli_registers_and_selects_local_brain(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "brains.jsonl"
    register_code = main(
        [
            "register",
            "--ledger",
            str(ledger),
            "--brain-id",
            "windows-coding",
            "--model-id",
            "model-a",
            "--model-family",
            "coder",
            "--runtime-id",
            "windows.ollama",
            "--node-id",
            "windows-node",
            "--provider-scope",
            "local",
            "--domain-scores-json",
            '{"coding": 0.9, "general": 0.7}',
            "--reliability-score",
            "0.9",
            "--latency-ms",
            "1000",
            "--normalized-cost",
            "0.05",
            "--baseline-hash",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ]
    )
    register_payload = json.loads(capsys.readouterr().out)
    select_code = main(
        [
            "select",
            "--ledger",
            str(ledger),
            "--task-domain",
            "coding",
            "--context-sensitivity",
            "private",
            "--maximum-latency-ms",
            "5000",
            "--cost-pressure",
            "0.8",
        ]
    )
    select_payload = json.loads(capsys.readouterr().out)

    assert register_code == 0
    assert register_payload["raw_model_identifier_persisted"] is False
    assert select_code == 0
    assert select_payload["selected_brain_id"] == "windows-coding"


def test_brain_cli_fails_closed_with_empty_registry(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "select",
            "--ledger",
            str(tmp_path / "missing.jsonl"),
            "--task-domain",
            "coding",
            "--context-sensitivity",
            "private",
            "--maximum-latency-ms",
            "5000",
            "--cost-pressure",
            "0.5",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["no_eligible_brain"]
