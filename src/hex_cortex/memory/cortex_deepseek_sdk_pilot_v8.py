"""V8 *actual* DeepSeek Python SDK pilot, for a disposable external VM ONLY.

The official SDK starts an agent with shell capability. THIS MODULE DOES
NOT MAKE THAT AGENT SAFE: Windows processes and Python flags do not sandbox.
Never run it on the host machine or with a mounted HEX/GTIXT/TXT checkout.
The task is fixed to a synthetic fixture, with separate DSH_HOME. This
module has NO Command Center POST route and exports only redacted metrics.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import secrets
import sys
from pathlib import Path

_FIXTURE = {
    "calc.py": "def add(a: int, b: int) -> int:\n    return a - b  # deliberate test failure\n",
    "test_calc.py": (
        "import unittest\nfrom calc import add\n\n"
        "class TestCalc(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n"
        "        self.assertEqual(add(-2, 3), 1)\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n"
    ),
    "README.md": (
        "# Disposable DeepSeek Harness Agent Fixture\n"
        "Deliberately broken add() function. This project is NOT HEX-CORTEX.\n"
        "Goal: make the supplied unittest pass. Work only on calc.py.\n"
    ),
}
_PROMPT = (
    "You are in an isolated, disposable example repository containing only "
    "calc.py, test_calc.py and README.md. Inspect the fixture, correct the "
    "deliberate arithmetic bug in calc.py, and run python -m unittest. "
    "Do not install dependencies, access any network, read outside this "
    "fixture, or touch any credentials. Describe what you changed and the "
    "test result. This prompt is an evaluation scenario, NOT a sandbox."
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _independent_path(target: Path, *, project: Path) -> Path:
    path = target.absolute()
    if path.is_symlink():
        raise ValueError("v8_symlink_target_denied")
    try:
        canonical = path.resolve(strict=False)
        canonical.relative_to(project.resolve())
        raise ValueError("v8_refuse_paths_inside_main_repo")
    except ValueError as exc:
        if str(exc) == "v8_refuse_paths_inside_main_repo":
            raise
    if canonical == Path(canonical.anchor):
        raise ValueError("v8_filesystem_root_denied")
    return canonical


def _fixture_valid(workspace: Path) -> bool:
    if not workspace.is_dir() or workspace.is_symlink():
        return False
    try:
        names = {path.name for path in workspace.iterdir()}
        if names != set(_FIXTURE):
            return False
        for name, content in _FIXTURE.items():
            file = workspace / name
            if not file.is_file() or file.is_symlink():
                return False
            if file.read_bytes() != content.encode("utf-8"):
                return False
    except OSError:
        return False
    return True


def prepare_fixture(
    *, workspace: Path, project_root: Path, approved_create: bool,
) -> dict:
    """Create exactly three generated files, only in a NEW external directory."""
    if not approved_create:
        return {"status": "dry_run", "files_written": False}
    project = project_root.resolve(strict=True)
    target = _independent_path(workspace, project=project)
    if target.exists():
        raise ValueError("v8_workspace_must_be_new")
    if target.parent.is_symlink():
        raise ValueError("v8_workspace_parent_symlink_denied")
    target.mkdir(parents=False, exist_ok=False)
    for name, content in _FIXTURE.items():
        (target / name).write_bytes(content.encode("utf-8"))
    return {
        "status": "generated_disposable_fixture", "files_written": True,
        "fixture_verified": _fixture_valid(target),
        "fixture_file_sha256": {
            name: _digest(content.encode("utf-8"))
            for name, content in sorted(_FIXTURE.items())
        },
        "dsh_runtime_launched": False, "model_called": False,
    }


def pilot_run(
    *, workspace: Path, dsh_home: Path, project_root: Path,
    provider: str, model: str, expected_sdk_version: str,
    approved_disposable_vm: bool, approved_model_and_shell: bool,
    sdk_factory=None,
) -> dict:
    """ONE official SDK call; only the VM isolates shell and runtime.

    No workspace bind mount, network policy, ACL or VM isolation is enforced
    in this Python process. Acknowledgment must reflect a REAL disposable VM.
    """
    if not approved_disposable_vm or not approved_model_and_shell:
        raise PermissionError("v8_vm_and_shell_approval_required")
    if (
        not 1 <= len(provider) <= 90
        or not 1 <= len(model) <= 120
        or not 1 <= len(expected_sdk_version) <= 80
        or any(ord(c) < 32 for c in provider + model + expected_sdk_version)
    ):
        raise ValueError("v8_model_or_version_invalid")
    root = project_root.resolve(strict=True)
    work = _independent_path(workspace, project=root)
    home = _independent_path(dsh_home, project=root)
    if home == work or home in work.parents or work in home.parents:
        raise ValueError("v8_workspace_and_home_must_be_separate")
    if not _fixture_valid(work):
        raise ValueError("v8_fixture_missing_or_modified_before_agent")
    if home.exists():
        raise ValueError("v8_dsh_home_must_be_new_before_pilot")
    if home.parent.is_symlink():
        raise ValueError("v8_dsh_home_parent_symlink_denied")
    genuine_sdk = sdk_factory is None
    if genuine_sdk:
        try:
            found = importlib.metadata.version("deepseek-harness-sdk")
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError("v8_deepseek_sdk_not_installed") from exc
        if found != expected_sdk_version:
            raise ValueError("v8_sdk_version_not_expected")
        # Explicit import ONLY after all approvals and fixture checks.
        from deepseek_harness import DeepSeekHarness
        sdk_factory = DeepSeekHarness
    session = "hex-v8-fixture-" + secrets.token_hex(8)
    with sdk_factory(
        provider=provider, model=model, profile="sdk-minimal",
        cwd=str(work), runtime_cwd=str(work), dsh_home=str(home),
        max_tokens=2048, initialize_timeout_seconds=45.0,
        request_timeout_seconds=120.0, shutdown_timeout_seconds=3.0,
    ) as client:
        result = client.run(_PROMPT, session_id=session)
    changed_bytes = (work / "calc.py").read_bytes()
    # This is a file-content diagnostic, NOT a trustworthy test pass.
    corrected = changed_bytes == (
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    ).encode("utf-8")
    names = sorted(p.name for p in work.iterdir())  # no recursive scan
    allowed_events = {
        "turn/start", "turn/end", "step/start", "step/end",
        "tool/call", "tool/result", "assistant/message",
    }
    event_type_counts = {
        kind: sum(
            event.get("type") == kind for event in result.events
            if isinstance(event, dict)
        )
        for kind in sorted(allowed_events)
    }
    return {
        "schema": "hex.deepseek_sdk_disposable_pilot.v8",
        "status": "sdk_turn_finished_without_accuracy_attestation",
        "session_id_sha256": _digest(session.encode()),
        "prompt_sha256": _digest(_PROMPT.encode()),
        "provider": provider, "model": model,
        "sdk_version_expected": expected_sdk_version,
        "profile": "sdk-minimal",
        "finish_reason": result.finish_reason,
        "root_event_count": len(result.events),
        "root_event_type_counts": event_type_counts,
        "observed_tool_call_events": event_type_counts["tool/call"],
        "observed_tool_result_events": event_type_counts["tool/result"],
        "specific_tool_names_verified": False,
        "notification_count": len(result.notifications),
        "response_sha256": _digest(result.final_response.encode()),
        "observed_file_names": names,
        "calc_file_sha256_after": _digest(changed_bytes),
        "exact_expected_fix_found": corrected,
        "unit_tests_independently_executed_by_adapter": False,
        "model_called": genuine_sdk, "external_sdk_runtime_launched": genuine_sdk,
        "sdk_test_double_used": not genuine_sdk,
        "shell_capability_exposed_to_agent": True,
        "host_vm_isolation_verified_by_python": False,
        "tool_permissions_enforced_by_hex": False,
        "receipt_contains_raw_model_text": False,
        "auto_promoted_to_canonical_spine": False,
        "main_hex_repository_access_independently_audited": False,
        "notes": "Run only inside VM; review changes and DSH_HOME/session logs there.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V8 DSH SDK pilot: external disposable VM only")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dsh-home", type=Path)
    parser.add_argument("--prepare-fixture", action="store_true")
    parser.add_argument("--run-agent", action="store_true")
    parser.add_argument("--approve-create-fixture", action="store_true")
    parser.add_argument("--ack-disposable-vm", action="store_true")
    parser.add_argument("--approve-model-and-shell", action="store_true")
    parser.add_argument("--provider", default="deepseek-official")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--expected-sdk-version", default="")
    args = parser.parse_args(argv)
    if args.prepare_fixture and args.run_agent:
        parser.error("prepare and run must be separate invocations")
    if not args.prepare_fixture and not args.run_agent:
        print(json.dumps({
            "status": "dry_run", "files_written": False, "model_called": False,
            "external_sdk_runtime_launched": False,
        }, sort_keys=True))
        return 0
    try:
        if args.prepare_fixture:
            receipt = prepare_fixture(
                workspace=args.workspace, project_root=_repo_root(),
                approved_create=args.approve_create_fixture,
            )
        else:
            if args.dsh_home is None:
                parser.error("--dsh-home required for runtime execution")
            receipt = pilot_run(
                workspace=args.workspace, dsh_home=args.dsh_home,
                project_root=_repo_root(), provider=args.provider,
                model=args.model, expected_sdk_version=args.expected_sdk_version,
                approved_disposable_vm=args.ack_disposable_vm,
                approved_model_and_shell=args.approve_model_and_shell,
            )
    except Exception as exc:  # noqa: BLE001
        # Error type only: paths, environment, model responses and credentials
        # must never be serialized to stdout or a persistent HEX receipt.
        print(json.dumps({
            "status": "blocked_or_failed", "reason_type": type(exc).__name__,
            "raw_sdk_output_saved": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
