"""Command Center V2: actual local Harness brain plus HTTP permission security."""
from __future__ import annotations

import http.client
import json
import threading

import pytest

from hex_cortex.memory.cortex_command_center_chat_v2 import (
    available_models,
    safe_cpu_chat,
)
from hex_cortex.memory.cortex_command_center_v2 import (
    CommandCenterV2Server,
    capabilities,
    main,
)
from hex_cortex.memory.cortex_command_center_view_v2 import CSS, HTML, JS


def _model_transport(url, body, timeout):
    assert "127.0.0.1:11434" in url
    assert timeout <= 45.0
    if url.endswith("/api/tags"):
        assert body is None
        return json.dumps({"models": [{"name": "qwen2.5:3b"}, {"name": "small:1b"}]})
    assert url.endswith("/api/chat")
    payload = json.loads(body)
    assert payload["options"]["num_gpu"] == 0
    assert payload["options"]["num_predict"] == 256
    assert payload["keep_alive"] == 0
    assert payload["model"] == "qwen2.5:3b"
    assert payload["messages"][-1]["content"] == "Bonjour"
    return json.dumps({"message": {"content": "Bonjour, je suis local."}})


def test_real_existing_brain_adapter_and_harness_cpu_ephemeral(tmp_path):
    models = available_models(transport=_model_transport)
    assert models == ["qwen2.5:3b", "small:1b"]
    result = safe_cpu_chat(
        root=tmp_path, model="qwen2.5:3b", prompt="Bonjour",
        transport=_model_transport,
    )
    assert result["status"] == "completed"
    assert result["reply"] == "Bonjour, je suis local."
    assert result["gpu_used"] is False and result["cpu_only_requested"] is True
    assert result["calls_used"] == 1
    assert result["files_written"] is False
    assert result["spine_saved"] is False
    assert result["tools_executed"] is False
    assert not list(tmp_path.iterdir())


def test_unknown_model_does_not_call_chat(tmp_path):
    calls = []
    def fake(url, body, timeout):
        calls.append(url)
        return json.dumps({"models": [{"name": "known:1b"}]})
    with pytest.raises(ValueError, match="not_installed"):
        safe_cpu_chat(root=tmp_path, model="unknown:8b", prompt="Bonjour", transport=fake)
    assert len(calls) == 1
    assert calls[0].endswith("/api/tags")


def test_model_and_prompt_bounds_do_not_contact_network(tmp_path):
    def no_call(*args):
        raise AssertionError("model must not be contacted")
    for prompt in ("", "x" * 1601):
        with pytest.raises(ValueError, match="prompt_invalid"):
            safe_cpu_chat(root=tmp_path, model="qwen", prompt=prompt, transport=no_call)
    with pytest.raises(ValueError, match="model_invalid"):
        safe_cpu_chat(root=tmp_path, model="", prompt="ok", transport=no_call)


def test_module_catalog_declares_disabled_capabilities_without_faking_actions():
    disabled = capabilities(chat_enabled=False)
    enabled = capabilities(chat_enabled=True)
    assert disabled["automatic_tools_enabled"] is False
    assert disabled["gpu_access_enabled"] is False
    assert disabled["cloud_access_enabled"] is False
    entries = {c["id"]: c for c in disabled["features"]}
    assert entries["voice"]["status"] == "not_connected"
    assert entries["mcp"]["status"] == "existing_modules_not_exposed"
    assert entries["chat"]["status"] == "disabled_until_launch_opt_in"
    assert {c["id"]: c for c in enabled["features"]}["chat"]["status"] == "enabled_cpu_opt_in"


def test_v2_interface_contains_chat_catalog_tabs_and_no_remote_resources():
    assert 'id="chat-form"' in HTML
    assert 'id="catalog-list"' in HTML
    assert 'id="vision-list"' in HTML
    assert 'id="chat-model"' in HTML
    assert "fetch('/api/ollama/chat'" in JS
    assert "text.textContent=message" in JS
    assert "sections.forEach" in JS
    assert ".main section[hidden]" in CSS
    assert "https://" not in HTML


def _fetch(server, method, path, *, origin=None, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    h = {"Host": f"127.0.0.1:{server.server_port}"}
    if origin is not None:
        h["Origin"] = origin
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    res = conn.getresponse()
    status = res.status
    data = res.read()
    conn.close()
    return status, data


def test_disabled_api_refuses_inference_and_models(tmp_path):
    with CommandCenterV2Server(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            r, raw = _fetch(server, "GET", "/api/capabilities")
            assert r == 200
            assert json.loads(raw)["automatic_tools_enabled"] is False
            r, raw = _fetch(server, "GET", "/api/ollama/models")
            assert r == 403 and json.loads(raw)["status"] == "disabled"
            r, raw = _fetch(server, "POST", "/api/ollama/chat")
            assert r == 403
            r, raw = _fetch(server, "GET", "/api/snapshot")
            assert r == 200 and json.loads(raw)["writes_enabled"] is False
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_cpu_chat_http_real_permissions_and_no_extra_endpoints(tmp_path, monkeypatch):
    from hex_cortex.memory import cortex_command_center_v2 as cc

    calls = []
    monkeypatch.setattr(cc, "available_models", lambda: ["qwen2.5:3b"])
    def stub(*, root, model, prompt):
        calls.append((model, prompt))
        return {
            "status": "completed", "reply": "local only",
            "model_used": model, "files_written": False,
        }
    monkeypatch.setattr(cc, "safe_cpu_chat", stub)
    with CommandCenterV2Server(tmp_path, port=0, chat_enabled=True) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            good_headers = {
                "X-HEX-Chat-Approval": "single-cpu-request",
                "Content-Type": "application/json",
            }
            payload = json.dumps({"model": "qwen2.5:3b", "prompt": "Bonjour"})
            r, raw = _fetch(server, "GET", "/api/ollama/models")
            assert r == 200 and json.loads(raw)["models"] == ["qwen2.5:3b"]
            r, raw = _fetch(server, "POST", "/api/ollama/chat", body=payload)
            assert r == 403
            r, raw = _fetch(server, "POST", "/api/ollama/chat", origin="https://evil.example",
                            headers=good_headers, body=payload)
            assert r == 403
            r, raw = _fetch(server, "POST", "/api/ollama/chat", origin=url,
                            headers={"Content-Type": "application/json"}, body=payload)
            assert r == 403
            r, raw = _fetch(server, "POST", "/api/ollama/chat", origin=url,
                            headers=good_headers, body=json.dumps({
                                "model": "qwen2.5:3b", "prompt": "hello",
                                "command": "delete files",
                            }))
            assert r == 400
            assert calls == []
            r, raw = _fetch(server, "POST", "/api/ollama/chat", origin=url,
                            headers=good_headers, body=payload)
            assert r == 200 and json.loads(raw)["reply"] == "local only"
            assert calls == [("qwen2.5:3b", "Bonjour")]
            r, raw = _fetch(server, "POST", "/api/tools/exec", origin=url,
                            headers=good_headers, body=payload)
            assert r == 405
            assert not list(tmp_path.iterdir())
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_dry_run_and_invalid_port_never_start_network(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--enable-cpu-chat", "--dry-run"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["chat_enabled"] is True
    assert output["network_used"] is False
    assert output["model_called"] is False
    assert main(["--port", "80", "--dry-run"]) == 2
    assert not list(tmp_path.iterdir())
