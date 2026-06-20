import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome_cli_v2 import main


def test_genome_v2_cli_audits_repository(capsys) -> None:
    code = main(["audit"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["genome_ready"] is True


def test_genome_v2_cli_projects_empty_topology(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "residuals.jsonl"
    code = main(["topology", "--ledger", str(ledger)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["cluster_count"] == 0
    assert payload["next_action"] == "collect_verified_residuals"
