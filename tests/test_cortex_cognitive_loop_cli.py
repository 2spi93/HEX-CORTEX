from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory import cortex_cognitive_loop_cli as loop_cli


def test_loop_cli_builds_plan_from_snapshot_file(tmp_path: Path, monkeypatch, capsys) -> None:
    snapshot = tmp_path / "gpu.json"
    snapshot.write_text('{"vram_total_mb":12288,"vram_used_mb":1000}', encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_plan(ledger: Path, gpu_snapshot: dict[str, object], **kwargs):
        captured["ledger"] = ledger
        captured["snapshot"] = gpu_snapshot
        captured.update(kwargs)
        return {"status": "ready", "strategy": "small_single", "blockers": []}

    monkeypatch.setattr(loop_cli, "build_cognitive_loop_plan", fake_plan)
    code = loop_cli.main(
        [
            "plan",
            "--gpu-snapshot",
            str(snapshot),
            "--task-domain",
            "code_generation",
            "--context-sensitivity",
            "private",
            "--difficulty",
            "high",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"
    assert captured["snapshot"] == {"vram_total_mb": 12288, "vram_used_mb": 1000}
    assert captured["task_domain"] == "code_generation"
    assert captured["difficulty"] == "high"


def test_loop_cli_aggregates_weighted_consensus(tmp_path: Path, capsys) -> None:
    samples = tmp_path / "samples.json"
    weights = tmp_path / "weights.json"
    samples.write_text('["42", "42", "41"]', encoding="utf-8")
    weights.write_text("[1.0, 1.0, 0.2]", encoding="utf-8")

    code = loop_cli.main(
        [
            "consensus",
            "--samples",
            str(samples),
            "--weights",
            str(weights),
            "--mode",
            "numeric",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "verified"
    assert payload["weighted"] is True
    assert payload["consensus_answer"] == "42"


def test_loop_cli_fails_closed_on_invalid_snapshot(tmp_path: Path, capsys) -> None:
    snapshot = tmp_path / "gpu.json"
    snapshot.write_text("[]", encoding="utf-8")

    code = loop_cli.main(
        [
            "plan",
            "--gpu-snapshot",
            str(snapshot),
            "--task-domain",
            "coding",
            "--context-sensitivity",
            "private",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["JSON payload must be an object"]
