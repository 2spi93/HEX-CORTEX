from __future__ import annotations

import json

from hex_cortex.memory.cortex_cognitive_brain_benchmark import (
    DOMAIN_TASKS,
    build_openai_request_body,
    build_prompt,
    grade_batch_response,
)


def test_build_openai_request_body_disables_thinking_and_caps_tokens() -> None:
    tasks = DOMAIN_TASKS["coding"][:2]

    payload = build_openai_request_body(
        model="qwen3-8b-uncensored",
        prompt=build_prompt("coding", tasks),
        temperature=0.2,
        seed=7,
    )

    assert payload["model"] == "qwen3-8b-uncensored"
    assert payload["temperature"] == 0.2
    assert payload["seed"] == 7
    assert payload["stream"] is False
    assert payload["max_tokens"] == 256
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["stop"] == ["</think>"]
    assert payload["messages"][0]["role"] == "system"
    assert "JSON object" in payload["messages"][0]["content"]
    assert payload["messages"][1]["role"] == "user"



def test_build_prompt_includes_task_ids_and_expected_json_shape() -> None:
    tasks = DOMAIN_TASKS["research"][:2]

    prompt = build_prompt("research", tasks)

    assert 'Return ONLY a JSON object' in prompt
    assert 't1' in prompt
    assert 't2' in prompt
    assert tasks[0].prompt in prompt
    assert tasks[1].prompt in prompt



def test_grade_batch_response_scores_numeric_and_text_answers() -> None:
    tasks = [
        DOMAIN_TASKS["research"][7],
        DOMAIN_TASKS["research"][8],
    ]
    response = json.dumps({"t8": "Tokyo", "t9": "Paris"})

    payload = grade_batch_response(tasks, response)

    assert payload["correct"] == 2
    assert payload["total"] == 2
    assert payload["score"] == 1.0
    assert payload["graded_answers"] == {"t8": 1, "t9": 1}



def test_grade_batch_response_fails_closed_on_missing_answers() -> None:
    tasks = DOMAIN_TASKS["general"][:2]
    response = json.dumps({"t1": "17"})

    payload = grade_batch_response(tasks, response)

    assert payload["correct"] == 1
    assert payload["total"] == 2
    assert payload["score"] == 0.5
    assert payload["graded_answers"]["t1"] == 1
    assert payload["graded_answers"]["t2"] == 0
