import json

from hex_cortex.memory.cortex_b import APPROVAL
from hex_cortex.memory.cortex_b import CORTEX_B_FILENAME
from hex_cortex.memory.cortex_b import build_cortex_b
from hex_cortex.memory.cortex_b import summarize_cortex_b


def test_cortex_b_imports() -> None:
    assert CORTEX_B_FILENAME == "cortex-b.jsonl"
    assert APPROVAL == "OPERATOR_APPROVE_A1"


def test_cortex_b_ready_with_runner(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-a.jsonl", _a_row())

    payload = build_cortex_b(profile, approval=APPROVAL, runner=_runner)

    record = payload["b_records"][0]
    assert record["b_allowed"] is True
    assert record["b_status"] == "ready"
    assert record["kind"] == "ollama"
    assert record["model"] == "qwen2.5-coder:7b-instruct"
    assert record["approval_phrase_matched"] is True
    assert record["model_call_performed"] is True
    assert record["network_call_performed"] is True
    assert record["repo_mutation_performed"] is False
    assert record["shell_execution_performed"] is False
    assert record["raw_output_saved"] is False
    assert record["observed_summary"]["status"] == "ok"
    assert record["observed_summary"]["summary_length"] > 0
    assert isinstance(record["observed_hash"], str)
    assert record["next_action"] == "inspect_b_receipt"

    summary = summarize_cortex_b(profile / CORTEX_B_FILENAME)
    assert summary["latest_b_allowed"] is True
    assert summary["latest_kind"] == "ollama"
    assert isinstance(summary["latest_observed_hash"], str)


def test_cortex_b_blocks_wrong_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-a.jsonl", _a_row())

    payload = build_cortex_b(profile, approval="NO", runner=_runner)

    record = payload["b_records"][0]
    assert record["b_allowed"] is False
    assert "approval_phrase_mismatch" in record["blockers"]


def test_cortex_b_blocks_missing_runner(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-a.jsonl", _a_row())

    payload = build_cortex_b(profile, approval=APPROVAL, runner=None)

    record = payload["b_records"][0]
    assert record["b_allowed"] is False
    assert "missing_runner" in record["blockers"]


def _runner(shape: dict[str, object]) -> dict[str, object]:
    assert shape["input_hash_only"] is True
    assert shape["tools"] is False
    return {"status": "ok", "summary": "local schema check passed"}


def _a_row() -> dict[str, object]:
    return {
        "a_allowed": True,
        "a_hash": "a-hash",
        "kind": "ollama",
        "model": "qwen2.5-coder:7b-instruct",
        "next_action": "go_a1",
        "needs_operator": True,
        "did_model": False,
        "did_net": False,
        "did_repo": False,
        "did_cmd": False,
        "saved_output": False,
        "shape": {
            "input_hash_only": True,
            "tools": False,
            "repo": False,
            "cmd": False,
            "save_output": False,
        },
    }


def _write_jsonl(path, row) -> None:
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
