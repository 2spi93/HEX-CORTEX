from hex_cortex.memory.cortex_coding_model_executor import execute_coding_model_task


def test_local_coding_model_execution_returns_volatile_result() -> None:
    calls = []

    def transport(method, url, headers, payload, timeout):
        calls.append((method, url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": "Proposed patch plan"
                    }
                }
            ]
        }

    receipt = execute_coding_model_task(
        provider_id="local_open_weight",
        model="local-coder",
        instruction="Return a concise coding plan.",
        task_prompt="Fix the parser.",
        bounded_context="file.py: failing line",
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "completed"
    assert receipt["volatile_result_text"] == "Proposed patch plan"
    assert receipt["result_persisted"] is False
    assert receipt["raw_response_persisted"] is False
    assert receipt["raw_secret_persisted"] is False
    assert calls[0][1] == "http://127.0.0.1:8080/v1/chat/completions"
    assert "Authorization" not in calls[0][2]


def test_remote_execution_requires_operator_approval() -> None:
    receipt = execute_coding_model_task(
        provider_id="remote_api",
        model="remote-model",
        instruction="Review code.",
        task_prompt="Review this patch.",
        operator_approved=False,
    )

    assert receipt["status"] == "blocked"
    assert receipt["model_call_performed"] is False
    assert "operator_approval_required" in receipt["blockers"]


def test_secret_context_is_never_sent_remote(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    receipt = execute_coding_model_task(
        provider_id="remote_api",
        model="remote-model",
        instruction="Review code.",
        task_prompt="Review this patch.",
        bounded_context="private secret",
        context_sensitivity="secret",
        operator_approved=True,
    )

    assert receipt["status"] == "blocked"
    assert receipt["network_call_performed"] is False
    assert receipt["blockers"] == ["secret_context_remote_forbidden"]


def test_remote_response_parser_supports_responses_output(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")

    def transport(method, url, headers, payload, timeout):
        assert url == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer secret-key"
        assert payload["input"] == "Review this patch."
        return {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "No blocking issue."}
                    ]
                }
            ]
        }

    receipt = execute_coding_model_task(
        provider_id="remote_api",
        model="remote-model",
        instruction="Review code.",
        task_prompt="Review this patch.",
        context_sensitivity="private",
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "completed"
    assert receipt["volatile_result_text"] == "No blocking issue."
    assert receipt["raw_secret_persisted"] is False


def test_context_size_is_bounded() -> None:
    receipt = execute_coding_model_task(
        provider_id="local_open_weight",
        model="local-coder",
        instruction="Plan.",
        task_prompt="Task.",
        bounded_context="x" * 250_001,
        operator_approved=True,
    )

    assert receipt["status"] == "blocked"
    assert "bounded_context_too_large" in receipt["blockers"]
