"""Repository-repair probe: behavior, determinism and fail-closed AST policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_repo_repair_probe_v3 import (
    CASES,
    _test_inputs,
    parse_candidate,
    render_task_prompt,
    score_repair,
    score_repository_benchmark,
    suite_manifest,
)

_GOOD = {
    "fees_sign": {"calc/pnl.py": "def net_pnl(gross, fees):\n    return gross - fees\n"},
    "risk_floor": {
        "risk/limits.py": "def position_room(limit, used):\n    return max(0, limit - used)\n"
    },
    "boundary_two_files": {
        "risk/limits.py": "def position_room(limit, used):\n    return max(0, limit - used)\n",
        "desk/order.py": (
            "from risk.limits import position_room\n"
            "def can_open(limit, used, request):\n"
            "    return request <= position_room(limit, used)\n"
        ),
    },
    "zero_division": {
        "metrics/win_rate.py": (
            "def win_rate(wins, losses):\n"
            "    return wins / (wins + losses) if wins + losses else 0\n"
        )
    },
}


def _valid_candidates() -> dict[str, str]:
    return {case_id: json.dumps({"files": files}) for case_id, files in _GOOD.items()}


def _report(responses: dict[str, str]) -> dict[str, object]:
    return score_repository_benchmark(
        responses, model_id="local-test", model_digest="sha256:actual",
        quantization="Q4", hardware_id="test-machine",
    )


def test_four_case_suite_with_reproducible_seed() -> None:
    manifest = suite_manifest()
    assert manifest == suite_manifest()
    assert manifest["task_count"] == 4
    assert {row["split"] for row in manifest["tasks"]} == {"holdout", "validation"}
    assert manifest["production_coding_certification"] is False
    assert _test_inputs("boundary_two_files", 20261009) == _test_inputs(
        "boundary_two_files", 20261009
    )
    assert _test_inputs("boundary_two_files", 1) != _test_inputs("boundary_two_files", 2)


def test_good_multifile_fix_and_strict_validation_pass() -> None:
    responses = _valid_candidates()
    report = _report(responses)
    assert report["passed_count"] == len(CASES)
    assert report["overall_score"] == 1.0
    assert report["holdout_score"] == 1.0
    assert report["routing_prior_authorized"] is False
    assert report["generated_code_executed"] is False
    assert report["checkout_modified"] is False
    assert report["raw_candidates_persisted"] is False
    for row in report["task_results"]:
        assert row["correct_cases"] == row["total_cases"]
    assert "def net_pnl" not in json.dumps(report)


def test_buggy_initial_repository_fails_all_four_cases() -> None:
    initial = {
        case.case_id: json.dumps({"files": case.files})
        for case in CASES
    }
    report = _report(initial)
    assert report["passed_count"] == 0
    assert report["holdout_score"] == 0.0


def test_response_can_never_escape_allowlisted_repo_files() -> None:
    target = CASES[0]
    bad_files = {
        "calc/pnl.py": _GOOD["fees_sign"]["calc/pnl.py"],
        "../GTIXT/secrets.py": "token = 'oops'",
    }
    with pytest.raises(ValueError, match="exactly"):
        parse_candidate(json.dumps({"files": bad_files}), target)
    assert score_repair(target, json.dumps({"files": bad_files}))["error_code"] == (
        "candidate_rejected"
    )
    assert score_repair(target, "text with no JSON")["passed"] is False
    assert score_repair(target, "x" * 40000)["passed"] is False


@pytest.mark.parametrize("dangerous", [
    "import os\ndef net_pnl(gross, fees):\n    return gross - fees",
    "def net_pnl(gross, fees):\n    return __import__('os').system('echo unsafe')",
    "def net_pnl(gross, fees):\n    return open('secrets.txt').read()",
    "def net_pnl(gross, fees):\n    while True: pass\n    return gross - fees",
    "def net_pnl(gross, fees):\n    return (lambda: gross - fees)()",
    "def net_pnl(gross, fees):\n    return globals()",
    "def net_pnl(gross, fees):\n    return (gross - fees).__class__",
    "def net_pnl(gross, fees):\n    return gross ** 9999999",
])
def test_generated_code_is_never_executed(dangerous: str, tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel"
    score = score_repair(
        CASES[0], json.dumps({"files": {"calc/pnl.py": dangerous}})
    )
    assert score["passed"] is False
    assert not sentinel.exists()


def test_known_good_check_does_not_write_any_checkout_files(tmp_path: Path) -> None:
    before = sorted(tmp_path.rglob("*"))
    scores = [
        score_repair(case, _valid_candidates()[case.case_id])
        for case in CASES
    ]
    assert all(row["passed"] for row in scores)
    assert sorted(tmp_path.rglob("*")) == before


def test_wrong_arithmetic_does_not_get_full_credit() -> None:
    score = score_repair(
        CASES[0], json.dumps({"files": {"calc/pnl.py": (
            "def net_pnl(gross, fees):\n    return gross + fees\n"
        )}})
    )
    assert score["passed"] is False
    assert score["correct_cases"] < score["total_cases"]


def test_invalid_seed_task_id_and_identity_are_rejected() -> None:
    with pytest.raises(ValueError):
        _report({"not-a-task": "candidate"})
    with pytest.raises(ValueError):
        score_repository_benchmark(
            {}, model_id="test", model_digest="hash", quantization="Q4",
            hardware_id="machine", seed=-1,
        )
    with pytest.raises(ValueError):
        score_repository_benchmark(
            {}, model_id="", model_digest="hash", quantization="Q4",
            hardware_id="machine",
        )


def test_prompts_contain_only_mutable_snapshot_and_instructions() -> None:
    for case in CASES:
        prompt = render_task_prompt(case)
        assert case.description in prompt
        assert all(f"FILE: {path}" in prompt for path in case.files)
        assert "No markdown or prose" in prompt
        assert "expected" not in prompt.lower()


def test_multifile_correction_requires_real_python_import() -> None:
    without_import = {
        "risk/limits.py": (
            "def position_room(limit, used):\n    return max(0, limit - used)\n"
        ),
        "desk/order.py": (
            "def can_open(limit, used, request):\n"
            "    return request <= position_room(limit, used)\n"
        ),
    }
    outcome = score_repair(
        CASES[2], json.dumps({"files": without_import})
    )
    assert outcome["passed"] is False
    assert outcome["error_code"] == "candidate_rejected"


def test_multifile_import_must_match_declared_provider() -> None:
    wrong_module = {
        "risk/limits.py": (
            "def position_room(limit, used):\n    return max(0, limit - used)\n"
        ),
        "desk/order.py": (
            "from metrics.win_rate import position_room\n"
            "def can_open(limit, used, request):\n"
            "    return request <= position_room(limit, used)\n"
        ),
    }
    outcome = score_repair(CASES[2], json.dumps({"files": wrong_module}))
    assert outcome["error_code"] == "candidate_rejected"

