from hex_cortex.memory.cortex_b import APPROVAL
from hex_cortex.memory.cortex_c import CORTEX_C_FILENAME
from hex_cortex.memory.cortex_c import build_cortex_c
from hex_cortex.memory.cortex_c import summarize_cortex_c


def test_cortex_c_imports() -> None:
    assert CORTEX_C_FILENAME == "cortex-c.jsonl"


def test_cortex_c_ready_chain(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_c(
        profile,
        kind="ollama",
        model="qwen2.5-coder:7b-instruct",
        target="http://127.0.0.1:11434",
        approval=APPROVAL,
        runner=_runner,
    )

    record = payload["c_records"][0]
    assert record["c_allowed"] is True
    assert record["c_status"] == "ready"
    assert record["kind"] == "ollama"
    assert record["model"] == "qwen2.5-coder:7b-instruct"
    assert record["approval_phrase_matched"] is True
    assert record["raw_output_saved"] is False
    assert record["repo_mutation_performed"] is False
    assert record["shell_execution_performed"] is False
    assert isinstance(record["lc_hash"], str)
    assert isinstance(record["a_hash"], str)
    assert isinstance(record["b_hash"], str)
    assert isinstance(record["observed_hash"], str)
    assert record["next_action"] == "inspect_c_receipt"

    summary = summarize_cortex_c(profile / CORTEX_C_FILENAME)
    assert summary["latest_c_allowed"] is True
    assert summary["latest_kind"] == "ollama"
    assert isinstance(summary["latest_observed_hash"], str)


def test_cortex_c_blocks_wrong_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_c(
        profile,
        kind="ollama",
        model="qwen2.5-coder:7b-instruct",
        target="http://127.0.0.1:11434",
        approval="NO",
        runner=_runner,
    )

    record = payload["c_records"][0]
    assert record["c_allowed"] is False
    assert "approval_phrase_mismatch" in record["blockers"]


def _runner(shape: dict[str, object]) -> dict[str, object]:
    assert shape["input_hash_only"] is True
    return {"status": "ok", "summary": "chain passed"}
