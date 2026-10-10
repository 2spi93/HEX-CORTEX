"""Local Ollama model identity preflight regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_repo_repair_cli import (
    inspect_ollama_model,
    main,
    run_local_repair_probe,
)


def _brain(names: list[str]) -> LocalOllamaBrain:
    def transport(url: str, body: bytes | None, timeout: float) -> str:
        assert url == "http://127.0.0.1:11434/api/tags"
        assert body is None
        return json.dumps({
            "models": [
                {
                    "name": name,
                    "digest": "sha256:" + "a" * 64,
                    "details": {"quantization_level": "Q4_K_M"},
                }
                for name in names
            ]
        })
    return LocalOllamaBrain(transport=transport)


def test_preflight_reads_actual_installed_model_digest_and_quantization() -> None:
    metadata = inspect_ollama_model(
        _brain(["qwen2.5-coder:7b"]), "qwen2.5-coder:7b"
    )
    assert metadata["digest"] == "sha256:" + "a" * 64
    assert metadata["quantization"] == "Q4_K_M"


def test_placeholder_model_is_denied_before_any_inference() -> None:
    with pytest.raises(ValueError, match="model_not_installed"):
        inspect_ollama_model(_brain(["qwen2.5-coder:7b"]), "NOM_DU_MODELE")


def test_failed_model_calls_have_a_different_error_from_code_rejection(
    tmp_path: Path,
) -> None:
    def blocked_brain(model, task):
        raise OSError("test simulation: model unavailable")

    report = run_local_repair_probe(
        model_id="correct-name", model_digest="sha256:some-digest",
        quantization="Q4", hardware_id="CPU", approved=True,
        project_root=tmp_path, brain=blocked_brain,
    )
    assert report["model_responses_received"] == 0
    assert report["model_call_failures"] == 4
    assert report["model_calls_attempted"] == 4
    assert {row["error_code"] for row in report["task_results"]} == {"model_call_failed"}


def test_cli_preflight_denies_unknown_model_without_sending_four_calls(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    import hex_cortex.memory.cortex_repo_repair_cli as cli

    def deny(brain, model_id):
        raise ValueError("model_not_installed")

    monkeypatch.setattr(cli, "inspect_ollama_model", deny)
    result = main([
        "--model-id", "NOM_DU_MODELE", "--approve-model",
        "--project-root", str(tmp_path),
    ])
    assert result == 2
    assert "model_not_installed" in capsys.readouterr().err


def test_cli_missing_metadata_cannot_silently_use_placeholder(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    import hex_cortex.memory.cortex_repo_repair_cli as cli

    monkeypatch.setattr(
        cli, "inspect_ollama_model",
        lambda brain, model_id: {
            "digest": "sha256:" + "d" * 64, "quantization": "Q4_K_M"
        }
    )
    result = main([
        "--model-id", "qwen2.5-coder:7b", "--approve-model",
        "--digest", "sha256:DIGEST_REEL",
        "--project-root", str(tmp_path),
    ])
    assert result == 2
    assert "model_digest_mismatch" in capsys.readouterr().err


def test_cli_not_reporting_zero_score_as_model_capability_when_all_calls_fail(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    import hex_cortex.memory.cortex_repo_repair_cli as cli

    monkeypatch.setattr(
        cli, "inspect_ollama_model",
        lambda brain, model_id: {"digest": "sha256:actual", "quantization": "Q4"},
    )
    def simulate(*args, **kwargs):
        return {
            "localhost_model_requested": True,
            "model_responses_received": 0,
            "model_calls_attempted": 4,
        }
    monkeypatch.setattr(cli, "run_local_repair_probe", simulate)
    result = main([
        "--model-id", "qwen2.5-coder:7b", "--approve-model",
        "--project-root", str(tmp_path),
    ])
    assert result == 2
    message = json.loads(capsys.readouterr().err)
    assert message["status"] == "blocked"
    assert message["reason"] == "all_model_calls_failed"
    assert "overall_score" not in message


def test_approved_docker_mode_stays_closed_for_invalid_candidate(
    tmp_path: Path, capsys
) -> None:
    bad_responses = tmp_path / "bad.json"
    bad_responses.write_text('{"fees_sign":"garbage"}', encoding="utf-8")
    result = main([
        "--model-id", "offline",
        "--digest", "sha256:offline",
        "--quantization", "Q4",
        "--responses", str(bad_responses),
        "--approve-docker",
    ])
    assert result == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["critic_reviews"]) == 4
    assert all(review["verdict"] == "static_rejected" for review in report["critic_reviews"])
    assert all(review["sandbox_executed"] is False for review in report["critic_reviews"])


def test_offline_scores_still_require_user_supplied_identity(
    tmp_path: Path, capsys
) -> None:
    responses = tmp_path / "empty.json"
    responses.write_text("{}", encoding="utf-8")
    result = main(["--model-id", "offline", "--responses", str(responses)])
    assert result == 2
    assert "requires explicit --digest" in capsys.readouterr().err
