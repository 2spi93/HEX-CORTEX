import json

from hex_cortex.memory.cortex_a import CORTEX_A_FILENAME
from hex_cortex.memory.cortex_a import build_cortex_a
from hex_cortex.memory.cortex_a import summarize_cortex_a


def test_cortex_a_imports() -> None:
    assert CORTEX_A_FILENAME == "cortex-a.jsonl"


def test_cortex_a_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-lc.jsonl", _lc_row())

    payload = build_cortex_a(profile, expected_kind="ollama")

    record = payload["a_records"][0]
    assert record["a_allowed"] is True
    assert record["a_status"] == "ready"
    assert record["kind"] == "ollama"
    assert record["model"] == "qwen2.5-coder:7b-instruct"
    assert record["runtime_binding"] == "none_shape_only"
    assert record["did_model"] is False
    assert record["did_net"] is False
    assert record["did_repo"] is False
    assert record["did_cmd"] is False
    assert record["saved_output"] is False
    assert record["needs_operator"] is True
    assert record["shape"]["input_hash_only"] is True
    assert record["shape"]["tools"] is False
    assert record["shape"]["repo"] is False
    assert record["shape"]["cmd"] is False
    assert record["shape"]["save_output"] is False
    assert record["next_action"] == "go_a1"

    summary = summarize_cortex_a(profile / CORTEX_A_FILENAME)
    assert summary["latest_a_allowed"] is True
    assert summary["latest_kind"] == "ollama"


def test_cortex_a_blocks_not_ready_source(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    row = _lc_row()
    row["next_action"] = "repair_lc"
    _write_jsonl(profile / "cortex-lc.jsonl", row)

    payload = build_cortex_a(profile)

    record = payload["a_records"][0]
    assert record["a_allowed"] is False
    assert "lc_not_ready" in record["blockers"]


def _lc_row() -> dict[str, object]:
    return {
        "lc_allowed": True,
        "lc_hash": "lc-hash",
        "kind": "ollama",
        "model": "qwen2.5-coder:7b-instruct",
        "next_action": "prepare_first_local_advisory_call_contract",
        "metadata_only": True,
        "text_sent": False,
        "answer_requested": False,
        "repo_change_performed": False,
        "command_performed": False,
        "raw_output_saved": False,
    }


def _write_jsonl(path, row) -> None:
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
