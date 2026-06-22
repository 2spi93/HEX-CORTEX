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
    assert calls[0][3]["think"] is False
    assert calls[0][3]["keep_alive"] == "2m"
    assert calls[0][3]["options"] == {"temperature": 0.2, "num_predict": 512}


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
