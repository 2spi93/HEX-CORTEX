from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

JsonTransport = Callable[[str, str, dict[str, str], dict[str, object], float], dict[str, object]]

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


def execute_coding_model_task(
    *,
    provider_id: str,
    model: str,
    instruction: str,
    task_prompt: str,
    bounded_context: str = "",
    context_sensitivity: str = "private",
    local_endpoint: str = "http://127.0.0.1:8080",
    remote_api_key_ref: str = "env:OPENAI_API_KEY",
    max_output_tokens: int = 4096,
    timeout_seconds: float = 120.0,
    temperature: float = 0.0,
    ollama_keep_alive: str = "5m",
    operator_approved: bool = False,
    transport: JsonTransport | None = None,
) -> dict[str, object]:
    blockers = _validate_inputs(
        provider_id=provider_id,
        model=model,
        instruction=instruction,
        task_prompt=task_prompt,
        bounded_context=bounded_context,
        context_sensitivity=context_sensitivity,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        ollama_keep_alive=ollama_keep_alive,
        operator_approved=operator_approved,
    )
    if blockers:
        return _blocked(blockers)

    caller = transport or _http_json
    if provider_id == "local_open_weight":
        endpoint = _validated_local_endpoint(local_endpoint) + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": _build_user_content(task_prompt, bounded_context)},
            ],
            "temperature": temperature,
            "stream": False,
            "max_tokens": max_output_tokens,
        }
        protocol = "openai_compatible_chat_completions"
    elif provider_id == "local_ollama":
        endpoint = _validated_local_endpoint(local_endpoint) + "/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": _build_user_content(task_prompt, bounded_context)},
            ],
            "stream": False,
            "think": False,
            "keep_alive": ollama_keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_output_tokens,
            },
        }
        protocol = "ollama_chat"
    else:
        if context_sensitivity == "secret":
            return _blocked(["secret_context_remote_forbidden"])
        api_key = _resolve_env_secret(remote_api_key_ref)
        if api_key is None:
            return _blocked(["remote_api_key_unavailable"])
        endpoint = _OPENAI_RESPONSES_ENDPOINT
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "instructions": instruction,
            "input": _build_user_content(task_prompt, bounded_context),
            "max_output_tokens": max_output_tokens,
        }
        protocol = "openai_responses"

    error_type: str | None = None
    response: dict[str, object] = {}
    try:
        response = caller("POST", endpoint, headers, payload, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - fail-closed receipt records only type.
        error_type = type(exc).__name__
    result_text = _extract_result_text(protocol, response) if error_type is None else ""
    completed = error_type is None and bool(result_text)
    receipt = {
        "receipt_type": "coding_model_execution_v1",
        "status": "completed" if completed else "failed",
        "provider_id": provider_id,
        "protocol": protocol,
        "model": model,
        "context_sensitivity": context_sensitivity,
        "instruction_hash": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "task_prompt_hash": hashlib.sha256(task_prompt.encode("utf-8")).hexdigest(),
        "bounded_context_hash": hashlib.sha256(bounded_context.encode("utf-8")).hexdigest(),
        "bounded_context_chars": len(bounded_context),
        "result_hash": hashlib.sha256(result_text.encode("utf-8")).hexdigest() if result_text else None,
        "result_chars": len(result_text),
        "volatile_result_text": result_text,
        "result_persisted": False,
        "prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "model_call_performed": True,
        "network_call_performed": True,
        "operator_approved": operator_approved,
        "temperature": temperature,
        "ollama_keep_alive": ollama_keep_alive if provider_id == "local_ollama" else None,
        "error_type": error_type,
        "blockers": [] if completed else ["model_execution_failed"],
        "next_action": "review_model_result" if completed else "repair_model_provider",
    }
    receipt["receipt_hash"] = _stable_hash(
        {key: value for key, value in receipt.items() if key != "volatile_result_text"}
    )
    return receipt


def _validate_inputs(
    *,
    provider_id: str,
    model: str,
    instruction: str,
    task_prompt: str,
    bounded_context: str,
    context_sensitivity: str,
    max_output_tokens: int,
    timeout_seconds: float,
    temperature: float,
    ollama_keep_alive: str,
    operator_approved: bool,
) -> list[str]:
    blockers: list[str] = []
    if provider_id not in {"local_open_weight", "local_ollama", "remote_api"}:
        blockers.append("provider_id_invalid")
    if not model.strip():
        blockers.append("model_missing")
    if not instruction.strip():
        blockers.append("instruction_missing")
    if not task_prompt.strip():
        blockers.append("task_prompt_missing")
    if context_sensitivity not in {"public", "private", "secret"}:
        blockers.append("context_sensitivity_invalid")
    if len(instruction) > 16_000:
        blockers.append("instruction_too_large")
    if len(task_prompt) > 64_000:
        blockers.append("task_prompt_too_large")
    if len(bounded_context) > 250_000:
        blockers.append("bounded_context_too_large")
    if not 1 <= max_output_tokens <= 32_768:
        blockers.append("max_output_tokens_out_of_range")
    if not 1.0 <= timeout_seconds <= 1800.0:
        blockers.append("timeout_seconds_out_of_range")
    if isinstance(temperature, bool) or not isinstance(temperature, int | float):
        blockers.append("temperature_invalid")
    elif not 0.0 <= float(temperature) <= 2.0:
        blockers.append("temperature_out_of_range")
    if not isinstance(ollama_keep_alive, str) or not ollama_keep_alive.strip():
        blockers.append("ollama_keep_alive_invalid")
    if not operator_approved:
        blockers.append("operator_approval_required")
    return blockers


def _validated_local_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("local endpoint must be explicit localhost HTTP with port")
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def _resolve_env_secret(secret_ref: str) -> str | None:
    scheme, separator, name = secret_ref.partition(":")
    if separator != ":" or scheme != "env" or not name:
        return None
    value = os.environ.get(name, "")
    return value if value else None


def _build_user_content(task_prompt: str, bounded_context: str) -> str:
    if not bounded_context:
        return task_prompt
    return f"{task_prompt}\n\n<bounded_context>\n{bounded_context}\n</bounded_context>"


def _extract_result_text(protocol: str, response: dict[str, object]) -> str:
    if protocol == "openai_compatible_chat_completions":
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        return content if isinstance(content, str) else ""
    if protocol == "ollama_chat":
        message = response.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        return content if isinstance(content, str) else ""
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    output = response.get("output")
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(str(part["text"]))
    return "\n".join(chunks)


def _http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout_seconds: float,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - endpoint is validated/fixed.
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("model response must be a JSON object")
    return result


def _blocked(blockers: list[str]) -> dict[str, object]:
    payload = {
        "receipt_type": "coding_model_execution_v1",
        "status": "blocked",
        "volatile_result_text": "",
        "result_persisted": False,
        "prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_model_execution_inputs",
    }
    payload["receipt_hash"] = _stable_hash(
        {key: value for key, value in payload.items() if key != "volatile_result_text"}
    )
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
