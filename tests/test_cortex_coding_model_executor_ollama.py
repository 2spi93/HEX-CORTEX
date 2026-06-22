from hex_cortex.memory.cortex_coding_model_executor import ModelTransportError
from hex_cortex.memory.cortex_coding_model_executor import execute_coding_model_task


def test_native_ollama_chat_uses_bounded_non_streaming_payload() -> None:
    calls = []

    def transport(method, url, headers, payload, timeout):
        calls.append((method, url, headers, payload, timeout))
        return {"message": {"role": "assistant", "content": "candidate answer"}, "done": True}

    receipt = execute_coding_model_task(
        provider_id="local_ollama",
        model="qwen2.5-coder:7b",
        instruction="Return one concise answer.",
        task_prompt="Inspect this function.",
        local_endpoint="http://127.0.0.1:11434",
        max_output_tokens=512,
        temperature=0.2,
        ollama_keep_alive="2m",
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "completed"
    assert receipt["protocol"] == "ollama_chat"
    assert receipt["volatile_result_text"] == "candidate answer"
    assert calls[0][1] == "http://127.0.0.1:11434/api/chat"
    assert calls[0][3]["stream"] is False
    assert "think" not in calls[0][3]
    assert calls[0][3]["keep_alive"] == "2m"
    assert calls[0][3]["options"] == {"temperature": 0.2, "num_predict": 512}


def test_native_ollama_passes_json_schema_to_format() -> None:
    calls = []
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    }

    def transport(method, url, headers, payload, timeout):
        del method, url, headers, timeout
        calls.append(payload)
        return {
            "message": {"role": "assistant", "content": '{"summary":"grounded"}'},
            "done": True,
        }

    receipt = execute_coding_model_task(
        provider_id="local_ollama",
        model="qwen2.5-coder:7b",
        instruction="Return JSON.",
        task_prompt="Inspect this function.",
        local_endpoint="http://127.0.0.1:11434",
        response_format=schema,
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "completed"
    assert calls[0]["format"] == schema
    assert receipt["response_format_hash"] is not None


def test_native_ollama_failure_is_diagnostic_and_attempts_unload() -> None:
    calls = []

    def transport(method, url, headers, payload, timeout):
        del method, headers, timeout
        calls.append((url, payload))
        if url.endswith("/api/chat"):
            raise ModelTransportError(
                "model runner failed",
                status_code=500,
                message_hash="a" * 64,
            )
        return {"done": True}

    receipt = execute_coding_model_task(
        provider_id="local_ollama",
        model="qwen2.5-coder:7b",
        instruction="Return one concise answer.",
        task_prompt="Inspect this function.",
        local_endpoint="http://127.0.0.1:11434",
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "failed"
    assert receipt["error_type"] == "ModelTransportError"
    assert receipt["error_status_code"] == 500
    assert receipt["error_message_hash"] == "a" * 64
    assert receipt["volatile_error_message"] == "model runner failed"
    assert receipt["cleanup_attempted"] is True
    assert receipt["cleanup_succeeded"] is True
    assert calls[-1][0].endswith("/api/generate")
    assert calls[-1][1]["keep_alive"] == 0


def test_native_ollama_rejects_non_loopback_endpoint() -> None:
    try:
        execute_coding_model_task(
            provider_id="local_ollama",
            model="qwen2.5-coder:7b",
            instruction="Plan.",
            task_prompt="Task.",
            local_endpoint="http://192.168.1.10:11434",
            operator_approved=True,
        )
    except ValueError as exc:
        assert "localhost" in str(exc)
    else:
        raise AssertionError("non-loopback Ollama endpoint should be rejected")
