from hex_cortex.memory.cortex_lc import CORTEX_LC_FILENAME
from hex_cortex.memory.cortex_lc import build_cortex_lc
from hex_cortex.memory.cortex_lc import summarize_cortex_lc


def test_cortex_lc_imports() -> None:
    assert CORTEX_LC_FILENAME == "cortex-lc.jsonl"


def test_cortex_lc_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_lc(
        profile,
        kind="ollama",
        model="qwen2.5-coder:7b-instruct",
        target="http://127.0.0.1:11434",
    )

    record = payload["lc_records"][0]
    assert record["lc_allowed"] is True
    assert record["lc_status"] == "ready"
    assert record["kind"] == "ollama"
    assert record["model"] == "qwen2.5-coder:7b-instruct"
    assert record["target_redacted"] == "http://127.0.0.1:<redacted>"
    assert record["metadata_only"] is True
    assert record["text_sent"] is False
    assert record["answer_requested"] is False
    assert record["repo_change_performed"] is False
    assert record["command_performed"] is False
    assert record["raw_output_saved"] is False
    assert record["next_action"] == "prepare_first_local_advisory_call_contract"

    summary = summarize_cortex_lc(profile / CORTEX_LC_FILENAME)
    assert summary["latest_lc_allowed"] is True
    assert summary["latest_kind"] == "ollama"


def test_cortex_lc_blocks_remote_target(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_lc(
        profile,
        kind="ollama",
        model="qwen2.5-coder:7b-instruct",
        target="https://example.invalid",
    )

    record = payload["lc_records"][0]
    assert record["lc_allowed"] is False
    assert "target_not_local" in record["blockers"]
