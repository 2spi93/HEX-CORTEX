"""V8 SDK actual API contract tested with a fake provider; never run DSH in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_deepseek_sdk_pilot_v8 as pilot


class _FakeResult:
    final_response = "Fixed calc.py and ran tests inside fixture."
    finish_reason = "completed"
    events = [{"type": "turn/start"}, {"type": "tool/call"},
              {"type": "tool/result"}, {"type": "turn/end"}]
    notifications = [{"method": "session.event"}]


class _FakeHarness:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def run(self, prompt, *, session_id):
        assert "python -m unittest" in prompt
        assert session_id.startswith("hex-v8-fixture-")
        assert self.kwargs["profile"] == "sdk-minimal"
        assert self.kwargs["request_timeout_seconds"] == 120
        work = Path(self.kwargs["cwd"])
        (work / "calc.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )
        return _FakeResult()


def test_dry_run_has_no_runtime_or_file_effects(tmp_path, capsys):
    fixture = tmp_path / "fixture"
    assert pilot.main(["--workspace", str(fixture)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "dry_run"
    assert data["external_sdk_runtime_launched"] is False
    assert not fixture.exists()


def test_preparation_requires_explicit_approval(tmp_path):
    workspace = tmp_path / "fixture"
    result = pilot.prepare_fixture(
        workspace=workspace, project_root=tmp_path,
        approved_create=False,
    )
    assert result["files_written"] is False
    assert not workspace.exists()


def test_fixture_is_minimal_and_rejects_existing_destination(tmp_path):
    home = tmp_path / "fixture"
    result = pilot.prepare_fixture(
        workspace=home, project_root=pilot._repo_root(),
        approved_create=True,
    )
    assert result["fixture_verified"]
    assert set(x.name for x in home.iterdir()) == {"README.md", "calc.py", "test_calc.py"}
    with pytest.raises(ValueError, match="workspace_must_be_new"):
        pilot.prepare_fixture(
            workspace=home, project_root=pilot._repo_root(),
            approved_create=True,
        )


def test_pilot_never_runs_without_acknowledged_vm_and_shell(tmp_path):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    home = tmp_path / "dsh-home"
    with pytest.raises(PermissionError, match="vm_and_shell_approval_required"):
        pilot.pilot_run(
            workspace=work, dsh_home=home, project_root=pilot._repo_root(),
            provider="deepseek-official", model="deepseek-v4-flash",
            expected_sdk_version="1", approved_disposable_vm=False,
            approved_model_and_shell=True, sdk_factory=_FakeHarness,
        )
    assert not home.exists()


def test_sdk_pilot_uses_public_official_constructor_and_sanitizes_result(tmp_path):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    home = tmp_path / "dsh-home"
    result = pilot.pilot_run(
        workspace=work, dsh_home=home, project_root=pilot._repo_root(),
        provider="deepseek-official", model="deepseek-v4-flash",
        expected_sdk_version="1.2.3", approved_disposable_vm=True,
        approved_model_and_shell=True, sdk_factory=_FakeHarness,
    )
    assert result["status"] == "sdk_turn_finished_without_accuracy_attestation"
    assert result["model_called"] is True
    assert result["external_sdk_runtime_launched"] is True
    assert result["root_event_count"] == 4
    assert result["notification_count"] == 1
    assert result["exact_expected_fix_found"] is True
    assert result["unit_tests_independently_executed_by_adapter"] is False
    assert result["auto_promoted_to_canonical_spine"] is False
    assert result["host_vm_isolation_verified_by_python"] is False
    assert "Fixed calc.py" not in json.dumps(result)
    assert "prompt" not in result  # only a hash
    assert not home.exists()  # mocked only; real runtime owns its own home


def test_tampered_fixture_rejected_before_sdk_load(tmp_path):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    (work / "calc.py").write_text("evil()", encoding="utf-8")
    with pytest.raises(ValueError, match="fixture_missing_or_modified"):
        pilot.pilot_run(
            workspace=work, dsh_home=tmp_path / "home",
            project_root=pilot._repo_root(),
            provider="deepseek-official", model="deepseek-v4-flash",
            expected_sdk_version="1", approved_disposable_vm=True,
            approved_model_and_shell=True, sdk_factory=_FakeHarness,
        )


def test_main_repo_target_denied(tmp_path):
    with pytest.raises(ValueError, match="main_repo"):
        pilot.prepare_fixture(
            workspace=pilot._repo_root() / "receipts" / "v8_fixture",
            project_root=pilot._repo_root(), approved_create=True,
        )


def test_workspace_and_dsh_home_cannot_overlap(tmp_path):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    with pytest.raises(ValueError, match="must_be_separate"):
        pilot.pilot_run(
            workspace=work, dsh_home=work / "dsh-home",
            project_root=pilot._repo_root(),
            provider="deepseek-official", model="deepseek-v4-flash",
            expected_sdk_version="1", approved_disposable_vm=True,
            approved_model_and_shell=True, sdk_factory=_FakeHarness,
        )


def test_sdk_not_installed_does_not_start_any_agent(tmp_path, monkeypatch):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    def no_sdk(_name):
        raise pilot.importlib.metadata.PackageNotFoundError
    monkeypatch.setattr(pilot.importlib.metadata, "version", no_sdk)
    with pytest.raises(ValueError, match="sdk_not_installed"):
        pilot.pilot_run(
            workspace=work, dsh_home=tmp_path / "home",
            project_root=pilot._repo_root(),
            provider="deepseek-official", model="deepseek-v4-flash",
            expected_sdk_version="0.1", approved_disposable_vm=True,
            approved_model_and_shell=True,
        )


def test_cli_no_approval_returns_generic_sanitized_error(tmp_path, capsys):
    ret = pilot.main([
        "--workspace", str(tmp_path / "none"), "--dsh-home", str(tmp_path / "home"),
        "--run-agent",
    ])
    assert ret == 2
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "blocked_or_failed"
    assert data["raw_sdk_output_saved"] is False


def test_host_repo_code_does_not_import_external_deepseek_on_module_import():
    assert "deepseek_harness" not in pilot.__dict__


def test_cannot_use_shell_arguments_as_provider_or_model(tmp_path):
    work = tmp_path / "fixture"
    pilot.prepare_fixture(
        workspace=work, project_root=pilot._repo_root(), approved_create=True,
    )
    with pytest.raises(ValueError, match="model_or_version_invalid"):
        pilot.pilot_run(
            workspace=work, dsh_home=tmp_path / "home",
            project_root=pilot._repo_root(),
            provider="abc\nbad", model="deepseek-v4-flash",
            expected_sdk_version="1", approved_disposable_vm=True,
            approved_model_and_shell=True, sdk_factory=_FakeHarness,
        )
