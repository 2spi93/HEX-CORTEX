from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_cli import main


def test_brain_cli_writes_template_without_shell_placeholders(
    tmp_path: Path,
    capsys,
) -> None:
    config = tmp_path / "windows-brain.json"

    code = main(
        [
            "template",
            "--output",
            str(config),
            "--platform",
            "windows",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    persisted = json.loads(config.read_text(encoding="utf-8"))

    assert code == 0
    assert payload["status"] == "written"
    assert persisted["runtime_id"] == "windows.ollama"
    assert persisted["reliability_score"] is None


def test_brain_cli_registers_validated_config_file(tmp_path: Path, capsys) -> None:
    config = tmp_path / "windows-brain.json"
    ledger = tmp_path / "brains.jsonl"
    main(["template", "--output", str(config), "--platform", "windows"])
    capsys.readouterr()

    payload = json.loads(config.read_text(encoding="utf-8"))
    payload.update(
        {
            "model_id": "qwen2.5-coder:7b",
            "model_family": "qwen2.5-coder",
            "domain_scores": {"coding": 0.82, "research": 0.61, "general": 0.71},
            "reliability_score": 0.91,
            "latency_ms": 845.0,
            "baseline_hash": "b" * 64,
            "parameter_class": "7b",
            "quantization": "q4_k_m",
            "operator_approved": True,
        }
    )
    config.write_text(json.dumps(payload), encoding="utf-8")

    code = main(
        [
            "register-file",
            "--config",
            str(config),
            "--ledger",
            str(ledger),
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["registration_source"] == "validated_config_file"
    assert result["operator_approved"] is True
    assert ledger.is_file()


def test_brain_cli_blocks_unedited_template(tmp_path: Path, capsys) -> None:
    config = tmp_path / "kali-brain.json"
    main(["template", "--output", str(config), "--platform", "kali"])
    capsys.readouterr()

    code = main(["register-file", "--config", str(config)])
    result = json.loads(capsys.readouterr().out)

    assert code == 2
    assert result["status"] == "blocked"
    assert "placeholder not replaced" in result["blockers"][0]
