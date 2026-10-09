"""Modern MCP Skills and Tasks optional local protocol regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_mcp_modern import handle_modern_request
from hex_cortex.memory.cortex_mcp_skills import LocalSkillCatalog


def _request(method: str, *, request_id: int = 1, tasks: bool = False,
             **params: object) -> dict[str, object]:
    capabilities: dict[str, object] = {}
    if tasks:
        capabilities["extensions"] = {"io.modelcontextprotocol/tasks": {}}
    return {
        "jsonrpc": "2.0", "id": request_id, "method": method,
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": capabilities,
            },
            **params,
        },
    }


def _skill_dir(tmp_path: Path) -> Path:
    path = tmp_path / "skills"
    location = path / "repo-audit"
    location.mkdir(parents=True)
    (location / "SKILL.md").write_text(
        "---\nname: repo-audit\ndescription: Inspect a repository safely\n"
        "---\n# Instructions\nCheck local metadata.\n", encoding="utf-8",
    )
    return path


def test_discovery_and_skills_with_verified_resource(tmp_path: Path, monkeypatch) -> None:
    folder = _skill_dir(tmp_path)
    monkeypatch.setenv("HEX_CORTEX_SKILLS_DIRECTORY", str(folder))
    discover = handle_modern_request(_request("server/discover"))["result"]
    assert "io.modelcontextprotocol/skills" in discover["capabilities"]["extensions"]
    assert "resources" in discover["capabilities"]
    listing = handle_modern_request(_request("skills/list"))["result"]
    assert listing["skills"][0]["uri"] == "skill://repo-audit/SKILL.md"
    assert listing["skills"][0]["resources"][0]["digest"].startswith("sha256:")
    assert listing["skills"][0]["frontmatter"] == {
        "name": "repo-audit", "description": "Inspect a repository safely",
    }
    single = handle_modern_request(
        _request("skills/get", uri="skill://repo-audit/SKILL.md")
    )["result"]
    assert single["skill"] == listing["skills"][0]
    content = handle_modern_request(
        _request("resources/read", uri="skill://repo-audit/SKILL.md")
    )["result"]["contents"][0]["text"]
    assert "Check local metadata" in content
    assert "resources" in handle_modern_request(_request("resources/list"))["result"]


def test_skill_symlinks_and_traversal_blocked(tmp_path: Path) -> None:
    folder = _skill_dir(tmp_path)
    catalog = LocalSkillCatalog(folder)
    import pytest

    with pytest.raises(ValueError):
        catalog.read("skill://repo-audit/../secret.md")
    with pytest.raises(ValueError):
        catalog.read("skill://repo-audit/unknown.py")
    (folder / "repo-audit" / "secret.md").symlink_to(tmp_path / "private")
    with pytest.raises(ValueError, match="symlink"):
        catalog.all()


def test_skills_not_advertised_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("HEX_CORTEX_SKILLS_DIRECTORY", raising=False)
    discover = handle_modern_request(_request("server/discover"))["result"]
    assert "resources" not in discover["capabilities"]
    error = handle_modern_request(_request("skills/list"))["error"]
    assert error["code"] == -32602


def test_task_extension_is_capability_negotiated_and_durable(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "tasks.sqlite"
    monkeypatch.setenv("HEX_CORTEX_TASK_STORE", str(path))
    discover = handle_modern_request(_request("server/discover"))["result"]
    assert "io.modelcontextprotocol/tasks" in discover["capabilities"]["extensions"]
    tool = handle_modern_request(
        _request(
            "tools/call", tasks=True, name="hex_cortex_measured_intelligence",
            arguments={"action": "benchmark_suite"},
        )
    )["result"]
    assert tool["resultType"] == "task"
    assert tool["status"] == "completed"
    assert "result" not in tool
    ident = tool["taskId"]
    fetched = handle_modern_request(
        _request("tasks/get", tasks=True, taskId=ident)
    )["result"]
    assert fetched["resultType"] == "complete"
    assert fetched["status"] == "completed"
    assert fetched["result"]["isError"] is False
    assert path.exists()
    cancelled = handle_modern_request(
        _request("tasks/cancel", tasks=True, taskId=ident)
    )["result"]
    assert cancelled["resultType"] == "complete"
    still_completed = handle_modern_request(
        _request("tasks/get", tasks=True, taskId=ident)
    )["result"]
    assert still_completed["status"] == "completed"
    update = handle_modern_request(
        _request("tasks/update", tasks=True, taskId=ident, inputResponses={})
    )["result"]
    assert update["resultType"] == "complete"


def test_tasks_unsupported_without_client_capability(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HEX_CORTEX_TASK_STORE", str(tmp_path / "tasks.sqlite"))
    result = handle_modern_request(
        _request(
            "tools/call", name="hex_cortex_measured_intelligence",
            arguments={"action": "benchmark_suite"},
        )
    )["result"]
    assert result["resultType"] == "complete"
    assert "taskId" not in result
    assert handle_modern_request(
        _request("tasks/get", taskId="some-uuid")
    )["error"]["code"] == -32021


def test_missing_skill_rejected_with_invalid_params(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HEX_CORTEX_SKILLS_DIRECTORY", str(_skill_dir(tmp_path)))
    result = handle_modern_request(
        _request("skills/get", uri="skill://missing/SKILL.md")
    )
    assert result["error"]["code"] == -32602


def test_existing_resource_bytes_match_manifest(tmp_path: Path) -> None:
    catalog = LocalSkillCatalog(_skill_dir(tmp_path))
    entry = catalog.all()[0]
    body = catalog.read(entry["uri"])["contents"][0]["text"].encode("utf-8")
    import hashlib

    assert hashlib.sha256(body).hexdigest() == entry["resources"][0]["digest"][7:]
    assert len(body) == entry["resources"][0]["size"]
