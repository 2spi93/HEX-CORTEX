from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_environment_doctor import build_environment_doctor


_REQUIRED = (
    "hexcortex",
    "hexcortex-genome",
    "hexcortex-memory",
    "hexcortex-brains",
    "hexcortex-doctor",
)


def _write_pyproject(path: Path, scripts: tuple[str, ...] = _REQUIRED) -> None:
    body = [
        "[build-system]",
        'requires = ["setuptools>=68"]',
        'build-backend = "setuptools.build_meta"',
        "",
        "[project]",
        'name = "hex-cortex"',
        'version = "0.1.0"',
        "",
        "[project.scripts]",
    ]
    body.extend(f'{name} = "hex_cortex.fake:main"' for name in scripts)
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def _ready_runner(
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
) -> tuple[int, str, str]:
    del cwd, timeout_seconds
    values = {
        ("git", "branch", "--show-current"): "screen-lab-policy-v2\n",
        ("git", "rev-parse", "HEAD"): "a" * 40 + "\n",
        (
            "git",
            "rev-parse",
            "refs/remotes/origin/screen-lab-policy-v2",
        ): "a" * 40 + "\n",
        ("git", "status", "--short"): "",
    }
    if tuple(command) in values:
        return 0, values[tuple(command)], ""
    if "pytest" in command:
        return 0, "999 tests collected in 0.42s\n", ""
    return 1, "", "unknown command"


def test_doctor_reports_ready_for_aligned_checkout(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "pyproject.toml")

    payload = build_environment_doctor(
        tmp_path,
        collect_tests=True,
        runner=_ready_runner,
        locator=lambda name: f"/venv/bin/{name}",
    )

    assert payload["status"] == "ready"
    assert payload["current_branch"] == "screen-lab-policy-v2"
    assert payload["blockers"] == []
    assert payload["test_collection"]["collected_count"] == 999
    assert payload["installed_console_scripts"]["hexcortex-genome"].endswith(
        "hexcortex-genome"
    )


def test_doctor_blocks_branch_and_console_script_mismatch(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "pyproject.toml", scripts=("hexcortex",))

    def runner(
        command: Sequence[str],
        cwd: Path,
        timeout_seconds: float,
    ) -> tuple[int, str, str]:
        del cwd, timeout_seconds
        if tuple(command) == ("git", "branch", "--show-current"):
            return 0, "main\n", ""
        if tuple(command) == ("git", "rev-parse", "HEAD"):
            return 0, "a" * 40 + "\n", ""
        if tuple(command) == (
            "git",
            "rev-parse",
            "refs/remotes/origin/screen-lab-policy-v2",
        ):
            return 0, "b" * 40 + "\n", ""
        if tuple(command) == ("git", "status", "--short"):
            return 0, " M local.txt\n", ""
        return 1, "", ""

    payload = build_environment_doctor(
        tmp_path,
        runner=runner,
        locator=lambda name: "/usr/bin/git" if name == "git" else None,
    )

    assert payload["status"] == "blocked"
    assert "branch_mismatch:main:screen-lab-policy-v2" in payload["blockers"]
    assert "console_script_not_declared:hexcortex-genome" in payload["blockers"]
    assert "console_script_not_installed:hexcortex-genome" in payload["blockers"]
    assert "working_tree_not_clean" in payload["warnings"]
    assert "local_head_differs_from_expected_remote" in payload["warnings"]


def test_doctor_repair_commands_reinstall_metadata(tmp_path: Path) -> None:
    _write_pyproject(tmp_path / "pyproject.toml")

    payload = build_environment_doctor(
        tmp_path,
        runner=_ready_runner,
        locator=lambda name: f"/venv/bin/{name}",
    )

    windows = payload["repair_commands"]["windows_powershell"]
    linux = payload["repair_commands"]["linux_bash"]
    assert 'python -m pip install -e ".[dev]"' in windows
    assert "python -m pip install -e '.[dev]'" in linux
    assert windows[-1] == "hexcortex-doctor --collect-tests"
