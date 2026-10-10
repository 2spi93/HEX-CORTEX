"""Opt-in local Docker verification for restricted Python repair proposals.

Never mount the real checkout. Candidates are first subject to the strict AST
allowlist, then copied into a disposable directory with a trusted test driver.
A preexisting local image is required: no image pull, socket access, shell,
host network, writable bind mount, privileged container, or credentials.
Docker reduces risk but is NOT a guarantee against hostile-code escape.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_repo_repair_probe_v3 import (
    RepairCase,
    _build_functions,
    _oracle,
    _test_inputs,
    parse_candidate,
)

_IMAGE = "python:3.11-slim"
_TIMEOUT_SECONDS = 25
Runner = Callable[..., subprocess.CompletedProcess[str]]


def _trusted_test_runner(case: RepairCase, seed: int) -> str:
    pairs = [
        {"args": list(values), "expected": _oracle(case.case_id, values)}
        for values in _test_inputs(case.case_id, seed)
    ]
    module = next(
        path.removesuffix(".py").replace("/", ".")
        for path, source in case.files.items()
        if any(
            "def " + case.function + "(" in line for line in source.splitlines()
        )
    )
    # Embed literal JSON data as a quoted Python string; no candidate text
    # is interpolated into this trusted test runner.
    cases = json.dumps(pairs, sort_keys=True)
    return (
        "import importlib, json, math, sys\\n"
        "sys.path.insert(0, '/work')\\n"
        f"m = importlib.import_module({module!r})\\n"
        f"fn = getattr(m, {case.function!r})\\n"
        f"tests = json.loads({cases!r})\\n"
        "passed = 0\\n"
        "for row in tests:\\n"
        "    try:\\n"
        "        value = fn(*row['args'])\\n"
        "        expected = row['expected']\\n"
        "        ok = (type(value) is bool and value is expected) if "
        "type(expected) is bool else (type(value) in (float, int) "
        "and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9))\\n"
        "        passed += int(ok)\\n"
        "    except Exception:\\n"
        "        pass\\n"
        "print(json.dumps({'total': len(tests), 'passed': passed}, "
        "sort_keys=True))\\n"
    )


def _invoke(runner: Runner, args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return runner(args, shell=False, capture_output=True, text=True, timeout=timeout)


def _secure_container_args(workdir: Path) -> list[str]:
    return [
        "docker", "run", "--rm", "--pull=never", "--network=none",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--memory=256m", "--cpus=1",
        "--user=65534:65534", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=32m",
        "--mount", f"type=bind,src={workdir},dst=/work,readonly",
        "--workdir", "/work", "--entrypoint", "python",
        _IMAGE, "-I", "-B", "/work/__trusted_test_runner__.py",
    ]


def verify_repair_in_local_docker(
    case: RepairCase,
    candidate: str,
    *,
    approved: bool = False,
    seed: int = 20261009,
    runner: Runner = subprocess.run,
) -> dict[str, object]:
    """Return redacted results; no Docker calls whatsoever without approval."""
    blocked = {
        "case_id": case.case_id,
        "verification_mode": "local_docker_python_tests",
        "passed": False,
        "executed": False,
        "reason": "approval_required",
        "checkout_modified": False,
    }
    if not approved:
        return blocked
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        return {**blocked, "reason": "invalid_seed"}

    try:
        files = parse_candidate(candidate, case)
        _build_functions(files)  # Fail closed before any subprocess is invoked.
    except (ValueError, TypeError):
        return {**blocked, "reason": "unsafe_or_invalid_candidate"}

    try:
        inspected = _invoke(runner, ["docker", "image", "inspect", _IMAGE], timeout=8)
        if inspected.returncode != 0:
            return {**blocked, "reason": "local_docker_image_missing"}
        with tempfile.TemporaryDirectory(prefix="hex-cortex-repair-v4-") as temporary:
            root = Path(temporary).resolve()
            for relative, source in files.items():
                target = (root / relative).resolve()
                if not target.is_relative_to(root):
                    raise ValueError("unsafe materialized candidate path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.encode("utf-8"))
            runner_path = root / "__trusted_test_runner__.py"
            runner_path.write_bytes(_trusted_test_runner(case, seed).encode("utf-8"))
            command = _secure_container_args(root)
            done = _invoke(runner, command, timeout=_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {**blocked, "executed": True, "reason": "sandbox_timeout"}
    except (FileNotFoundError, OSError):
        return {**blocked, "reason": "local_docker_unavailable"}
    except ValueError:
        return {**blocked, "reason": "sandbox_preflight_failed"}

    if done.returncode != 0:
        return {**blocked, "executed": True, "reason": "sandbox_tests_failed"}
    try:
        raw = done.stdout.strip()
        if len(raw.encode("utf-8")) > 4096:
            raise ValueError("sandbox output too large")
        parsed = json.loads(raw)
        if set(parsed) != {"total", "passed"}:
            raise ValueError("unexpected sandbox JSON")
        total, passed = parsed["total"], parsed["passed"]
        if (type(total) is not int or type(passed) is not int
                or total != len(_test_inputs(case.case_id, seed))
                or not 0 <= passed <= total):
            raise ValueError("sandbox output malformed")
    except (ValueError, TypeError, json.JSONDecodeError):
        return {**blocked, "executed": True, "reason": "sandbox_output_invalid"}
    return {
        **blocked, "executed": True,
        "reason": "ok" if passed == total else "functional_tests_failed",
        "passed": passed == total, "passed_cases": passed, "total_cases": total,
    }
