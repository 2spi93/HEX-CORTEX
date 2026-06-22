import json

from hex_cortex.memory.cortex_structured_code_plan import aggregate_structured_code_plans
from hex_cortex.memory.cortex_structured_code_plan import parse_structured_code_plan


_ALLOWED = {
    "src/hex_cortex/memory/cortex_verified_execution_runtime.py",
    "src/hex_cortex/memory/cortex_self_consistency.py",
    "tests/test_cortex_verified_execution_runtime.py",
}


def _sample(summary: str, file_path: str, change: str) -> str:
    return json.dumps(
        {
            "summary": summary,
            "focus_areas": [
                "consensus_quality",
                "repository_context",
                "phase_separation",
            ],
            "candidate_files": [
                file_path,
                "src/hex_cortex/memory/cortex_self_consistency.py",
            ],
            "proposed_changes": [
                {
                    "area": "repository_context",
                    "file": file_path,
                    "objective": "ground model plans in real repository evidence",
                    "change": change,
                    "confidence": 0.8,
                },
                {
                    "area": "consensus_quality",
                    "file": "src/hex_cortex/memory/cortex_self_consistency.py",
                    "objective": "compare structured decisions instead of prose",
                    "change": "aggregate normalized fields",
                    "confidence": 0.9,
                },
            ],
            "tests": ["add focused unit coverage"],
            "risks": ["overly narrow context selection"],
            "unknowns": [],
        }
    )


def test_parser_removes_hallucinated_paths() -> None:
    payload = parse_structured_code_plan(
        _sample("plan", "invented/context_manager.py", "add cache"),
        allowed_paths=_ALLOWED,
    )

    assert payload["status"] == "valid"
    assert payload["plan"]["candidate_files"] == [
        "src/hex_cortex/memory/cortex_self_consistency.py"
    ]
    assert payload["plan"]["proposed_changes"][0]["file"] is None
    assert payload["invalid_paths"] == ["invented/context_manager.py"]
    assert payload["grounding_ratio"] < 1.0


def test_field_level_consensus_accepts_different_prose() -> None:
    real = "src/hex_cortex/memory/cortex_verified_execution_runtime.py"
    samples = [
        _sample("Use a grounded structured plan.", real, "inject a bounded AST context"),
        _sample("Ground the planner before voting.", real, "build context from real modules"),
        _sample("Replace prose voting with schema voting.", real, "attach repository evidence"),
    ]

    result = aggregate_structured_code_plans(
        samples,
        allowed_paths=_ALLOWED,
        sample_weights=[0.83, 0.83, 0.83],
    )

    assert result["status"] == "consensus"
    assert result["valid_sample_count"] == 3
    assert result["support_count"] == 3
    assert result["agreement_ratio"] == 1.0
    assert result["grounding_ratio"] == 1.0
    assert result["consensus_plan"]["candidate_files"] == [
        "src/hex_cortex/memory/cortex_self_consistency.py",
        real,
    ]
    assert result["raw_response_persisted"] is False


def test_invalid_json_fails_closed() -> None:
    result = aggregate_structured_code_plans(
        ["not json", "still not json"],
        allowed_paths=_ALLOWED,
    )

    assert result["status"] == "no_consensus"
    assert result["decision"] == "no_valid_structured_sample"
    assert result["valid_sample_count"] == 0
