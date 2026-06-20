from __future__ import annotations

import json

from hex_cortex.memory import cortex_environment_doctor_cli as doctor_cli


def test_doctor_cli_prints_pretty_ready_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        doctor_cli,
        "build_environment_doctor",
        lambda *args, **kwargs: {
            "audit_type": "hex_cortex_environment_doctor_v1",
            "status": "ready",
            "blockers": [],
        },
    )

    code = doctor_cli.main(["--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"


def test_doctor_cli_returns_nonzero_when_blocked(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        doctor_cli,
        "build_environment_doctor",
        lambda *args, **kwargs: {
            "audit_type": "hex_cortex_environment_doctor_v1",
            "status": "blocked",
            "blockers": ["branch_mismatch"],
        },
    )

    code = doctor_cli.main([])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["blockers"] == ["branch_mismatch"]
