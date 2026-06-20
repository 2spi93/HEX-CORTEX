from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path

CommandRunner = Callable[[Sequence[str], Path, float], tuple[int, str, str]]
CommandLocator = Callable[[str], str | None]

_REQUIRED_COMMANDS = (
    "hexcortex",
    "hexcortex-genome",
    "hexcortex-memory",
    "hexcortex-brains",
    "hexcortex-doctor",
)
_OPTIONAL_MODULES = ("PIL", "torch")


def build_environment_doctor(
    project_root: Path,
    *,
    expected_branch: str = "screen-lab-policy-v2",
    collect_tests: bool = False,
    runner: CommandRunner | None = None,
    locator: CommandLocator | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    call = runner or _run_command
    locate = locator or shutil.which
    blockers: list[str] = []
    warnings: list[str] = []

    pyproject_path = root / "pyproject.toml"
    scripts = _declared_scripts(pyproject_path)
    missing_declarations = sorted(set(_REQUIRED_COMMANDS).difference(scripts))
    if not pyproject_path.is_file():
        blockers.append("pyproject_missing")
    if missing_declarations:
        blockers.extend(f"console_script_not_declared:{name}" for name in missing_declarations)

    git_available = locate("git") is not None
    branch = None
    head_sha = None
    remote_sha = None
    dirty = None
    if not git_available:
        blockers.append("git_not_available")
    else:
        branch = _git_value(call, root, ("git", "branch", "--show-current"))
        head_sha = _git_value(call, root, ("git", "rev-parse", "HEAD"))
        remote_sha = _git_value(
            call,
            root,
            ("git", "rev-parse", f"refs/remotes/origin/{expected_branch}"),
        )
        status = _git_value(call, root, ("git", "status", "--short"), allow_empty=True)
        dirty = bool(status)
        if not branch:
            blockers.append("git_branch_unresolved")
        elif branch != expected_branch:
            blockers.append(f"branch_mismatch:{branch}:{expected_branch}")
        if head_sha and remote_sha and head_sha != remote_sha:
            warnings.append("local_head_differs_from_expected_remote")
        if dirty:
            warnings.append("working_tree_not_clean")

    installed_commands = {name: locate(name) for name in _REQUIRED_COMMANDS}
    missing_installed = sorted(name for name, path in installed_commands.items() if path is None)
    if missing_installed:
        blockers.extend(f"console_script_not_installed:{name}" for name in missing_installed)

    in_virtualenv = sys.prefix != sys.base_prefix
    if not in_virtualenv:
        warnings.append("python_virtualenv_not_detected")

    optional_modules = {
        name: importlib.util.find_spec(name) is not None for name in _OPTIONAL_MODULES
    }
    missing_optional = sorted(name for name, ready in optional_modules.items() if not ready)
    if missing_optional:
        warnings.extend(f"optional_module_missing:{name}" for name in missing_optional)

    test_collection: dict[str, object] = {
        "performed": False,
        "success": None,
        "collected_count": None,
        "error_type": None,
    }
    if collect_tests:
        code, stdout, stderr = call(
            (sys.executable, "-m", "pytest", "--collect-only", "-q"),
            root,
            180.0,
        )
        test_collection = {
            "performed": True,
            "success": code == 0,
            "collected_count": _parse_collected_count(stdout + "\n" + stderr),
            "error_type": None if code == 0 else "pytest_collection_failed",
        }
        if code != 0:
            blockers.append("pytest_collection_failed")

    ready = not blockers
    return {
        "audit_type": "hex_cortex_environment_doctor_v1",
        "status": "ready" if ready else "blocked",
        "project_root": str(root),
        "expected_branch": expected_branch,
        "current_branch": branch,
        "head_sha": head_sha,
        "expected_remote_sha": remote_sha,
        "working_tree_dirty": dirty,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "virtualenv_active": in_virtualenv,
        "declared_console_scripts": sorted(scripts),
        "required_console_scripts": list(_REQUIRED_COMMANDS),
        "installed_console_scripts": installed_commands,
        "optional_modules": optional_modules,
        "test_collection": test_collection,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "repair_commands": _repair_commands(expected_branch),
        "next_action": "run_hex_cortex" if ready else "repair_environment_alignment",
        "raw_environment_persisted": False,
        "secret_values_persisted": False,
    }


def _declared_scripts(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return set()
    project = payload.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    return set(scripts) if isinstance(scripts, dict) else set()


def _git_value(
    runner: CommandRunner,
    root: Path,
    command: Sequence[str],
    *,
    allow_empty: bool = False,
) -> str | None:
    code, stdout, _ = runner(command, root, 10.0)
    if code != 0:
        return None
    value = stdout.strip()
    if value or allow_empty:
        return value
    return None


def _parse_collected_count(text: str) -> int | None:
    patterns = (
        r"(\d+)\s+tests?\s+collected",
        r"collected\s+(\d+)\s+items?",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    node_ids = [line for line in text.splitlines() if "::test_" in line]
    return len(node_ids) if node_ids else None


def _repair_commands(expected_branch: str) -> dict[str, list[str]]:
    return {
        "windows_powershell": [
            "git fetch origin",
            f"git switch {expected_branch}",
            f"git pull --ff-only origin {expected_branch}",
            'python -m pip install -e ".[dev]"',
            "hexcortex-doctor --collect-tests",
        ],
        "linux_bash": [
            "git fetch origin",
            f"git switch {expected_branch}",
            f"git pull --ff-only origin {expected_branch}",
            "python -m pip install -e '.[dev]'",
            "hexcortex-doctor --collect-tests",
        ],
    }


def _run_command(
    command: Sequence[str],
    cwd: Path,
    timeout_seconds: float,
) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", type(exc).__name__
    return completed.returncode, completed.stdout, completed.stderr
