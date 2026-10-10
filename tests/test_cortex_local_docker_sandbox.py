"""Docker isolation security contracts, never start Docker in CI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_critic_v4 import review_repair_candidate
from hex_cortex.memory.cortex_local_docker_sandbox import verify_repair_in_local_docker
from hex_cortex.memory.cortex_repo_repair_probe_v3 import CASES, _test_inputs


def _good_candidate() -> str:
    return json.dumps({
        "files": {"calc/pnl.py": "def net_pnl(gross, fees):\n    return gross - fees\n"}
    })


def _fake_docker(commands: list[list[str]], *, context: str = "npipe:////./pipe/docker_engine",
                 run_payload: str | None = None):
    def mock(args, **kwargs):
        assert kwargs["shell"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["timeout"] <= 25
        commands.append(list(args))
        if args[:3] == ["docker", "context", "inspect"]:
            return subprocess.CompletedProcess(args, 0, context + "\n", "")
        if args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        if args[:2] == ["docker", "run"]:
            assert "--network=none" in args
            assert "--read-only" in args
            assert "--pull=never" in args
            assert "--cap-drop=ALL" in args
            assert "--security-opt=no-new-privileges" in args
            assert "--memory=256m" in args
            assert "--pids-limit=64" in args
            assert "--user=65534:65534" in args
            assert "--privileged" not in args
            assert "-v" not in args
            assert "--mount" in args
            mount = args[args.index("--mount") + 1]
            assert mount.startswith("type=bind,src=")
            assert mount.endswith(",dst=/work,readonly")
            local_dir = Path(mount[len("type=bind,src="):-len(",dst=/work,readonly")])
            assert (local_dir / "calc" / "pnl.py").exists()
            assert (local_dir / "__trusted_test_runner__.py").exists()
            assert "gross - fees" in (local_dir / "calc" / "pnl.py").read_text(encoding="utf-8")
            assert args[-4:] == ["python:3.11-slim", "-I", "-B", "/work/__trusted_test_runner__.py"]
            return subprocess.CompletedProcess(args, 0, run_payload or json.dumps({
                "total": 15, "passed": 15
            }), "")
        raise AssertionError("unexpected Docker command")
    return mock


def test_no_approval_prevents_all_subprocess_calls() -> None:
    executed: list[list[str]] = []
    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), runner=_fake_docker(executed)
    )
    assert result["reason"] == "approval_required"
    assert result["executed"] is False
    assert executed == []


def test_bad_candidate_is_rejected_before_docker() -> None:
    executed: list[list[str]] = []
    malicious = json.dumps({"files": {"calc/pnl.py": "import os\n"
                                     "def net_pnl(gross, fees):\n    return gross - fees\n"}})
    result = verify_repair_in_local_docker(
        CASES[0], malicious, approved=True, runner=_fake_docker(executed)
    )
    assert result["reason"] == "unsafe_or_invalid_candidate"
    assert executed == []


def test_local_docker_argv_and_ephemeral_mount(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    calls: list[list[str]] = []
    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True,
        runner=_fake_docker(calls),
    )
    assert result["passed"] is True
    assert result["executed"] is True
    assert result["checkout_modified"] is False
    assert result["passed_cases"] == len(_test_inputs("fees_sign", 20261009))
    assert [cmd[:3] for cmd in calls] == [
        ["docker", "context", "inspect"], ["docker", "image", "inspect"],
        ["docker", "run", "--rm"],
    ]
    mounted = calls[-1][calls[-1].index("--mount") + 1]
    root = Path(mounted[len("type=bind,src="):-len(",dst=/work,readonly")])
    assert not root.exists()  # disposed after scoring


@pytest.mark.parametrize("context", ["ssh://remote.example", "tcp://1.2.3.4:2375"])
def test_remote_context_blocked_before_image_or_run(monkeypatch, context: str) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    calls: list[list[str]] = []
    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True,
        runner=_fake_docker(calls, context=context),
    )
    assert result["reason"] == "nonlocal_docker_context_denied"
    assert len(calls) == 1


def test_docker_host_environment_override_blocked(monkeypatch) -> None:
    monkeypatch.setenv("DOCKER_HOST", "ssh://remote.example")
    calls = []
    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True,
        runner=_fake_docker(calls),
    )
    assert result["reason"] == "explicit_docker_host_override_denied"
    assert calls == []


def test_sandbox_output_must_have_bounded_complete_schema(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    calls: list[list[str]] = []
    fake = _fake_docker(calls, run_payload='{"total":15,"passed":999}')
    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True, runner=fake,
    )
    assert result["reason"] == "sandbox_output_invalid"
    assert result["passed"] is False


def test_critic_reports_separate_static_and_runtime_outcomes(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    candidate = _good_candidate()
    no_approval = review_repair_candidate(CASES[0], candidate)
    assert no_approval["static_passed"] is True
    assert no_approval["sandbox_executed"] is False
    assert no_approval["trusted"] is False
    assert no_approval["allowed_to_modify_checkout"] is False

    calls: list[list[str]] = []
    verdict = review_repair_candidate(
        CASES[0], candidate, approve_docker=True,
        docker_runner=_fake_docker(calls),
    )
    assert verdict["verdict"] == "isolated_tests_passed"
    assert verdict["static_passed"] is True
    assert verdict["sandbox_passed"] is True
    assert verdict["trusted"] is False
    assert verdict["routing_prior_authorized"] is False
    assert candidate not in json.dumps(verdict)


def test_critic_blocks_static_fail_without_docker() -> None:
    calls: list[list[str]] = []
    bad = json.dumps({"files": {"calc/pnl.py": (
        "def net_pnl(gross, fees):\n    return gross + fees\n"
    )}})
    verdict = review_repair_candidate(
        CASES[0], bad, approve_docker=True,
        docker_runner=_fake_docker(calls),
    )
    assert verdict["verdict"] == "static_rejected"
    assert calls == []


def test_docker_missing_is_not_misrepresented_as_bad_model(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    calls = []

    def missing(args, **kwargs):
        calls.append(args)
        if args[:3] == ["docker", "context", "inspect"]:
            return subprocess.CompletedProcess(args, 0, "unix:///var/run/docker.sock", "")
        if args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 1, "", "image missing")
        raise AssertionError("should never start Docker")

    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True, runner=missing,
    )
    assert result["reason"] == "local_docker_image_missing"
    assert result["executed"] is False
    assert len(calls) == 2


def test_timeout_force_removes_named_container(monkeypatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    calls = []

    def timeout(args, **kwargs):
        calls.append(args)
        if args[:3] == ["docker", "context", "inspect"]:
            return subprocess.CompletedProcess(args, 0, "unix:///var/run/docker.sock", "")
        if args[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        if args[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(args, 25)
        if args[:3] == ["docker", "rm", "--force"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError("unknown command")

    result = verify_repair_in_local_docker(
        CASES[0], _good_candidate(), approved=True, runner=timeout,
    )
    assert result["reason"] == "sandbox_timeout"
    assert calls[-1][:3] == ["docker", "rm", "--force"]
    assert calls[-1][-1] == calls[-2][calls[-2].index("--name") + 1]
