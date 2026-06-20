import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_genome_cli import main


def test_genome_cli_audits_repository_contract(capsys) -> None:
    code = main(["audit"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["genome_ready"] is True


def test_genome_cli_appends_residual_without_raw_values(
    tmp_path: Path,
    capsys,
) -> None:
    ledger = tmp_path / "residuals.jsonl"
    code = main(
        [
            "residual",
            "--ledger",
            str(ledger),
            "--model-id",
            "private-model-name",
            "--model-family",
            "gemma",
            "--domain",
            "hex-cortex",
            "--context-signature",
            "private-context",
            "--state-ref",
            "private-state",
            "--predicted-ref",
            "private-prediction",
            "--observed-ref",
            "private-observation",
            "--failure-class",
            "logic_error",
            "--residual-magnitude",
            "0.3",
            "--profiles",
            "scientist,adversary",
            "--tools",
            "pytest",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["record_type"] == "cognitive_residual_record_v1"
    text = ledger.read_text(encoding="utf-8")
    assert "private-model-name" not in text
    assert "private-context" not in text
    assert "private-state" not in text


def test_genome_cli_rejects_full_weight_mutation(capsys) -> None:
    code = main(
        [
            "mutation-plan",
            "--skill-candidate-hash",
            "a" * 64,
            "--mutation-level",
            "full_weight_update",
            "--baseline-ref",
            "baseline",
            "--evaluator-ref",
            "evaluator",
            "--revocation-ref",
            "revoke",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert "full_weight_update_disabled" in payload["blockers"]


def test_genome_cli_projects_empty_cr_jepa_manifest(
    tmp_path: Path,
    capsys,
) -> None:
    ledger = tmp_path / "missing.jsonl"
    code = main(["cr-jepa-manifest", "--ledger", str(ledger)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["training_allowed"] is False
    assert payload["residual_count"] == 0
