import json

from hex_cortex.memory.cortex_seq import CORTEX_SEQ_FILENAME
from hex_cortex.memory.cortex_seq import build_cortex_seq
from hex_cortex.memory.cortex_seq import summarize_cortex_seq
from hex_cortex.memory.cortex_seq import verify_cortex_seq_chain


def test_cortex_seq_builds_first_temporal_record(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_seq(
        profile,
        initial_state=_state("state-a"),
        transition_record=_transition("state-a", "transition-a", "inspect"),
        observed_state=_state("state-b"),
        error_record=_error("transition-a", "state-b", "error-a"),
    )

    record = payload["seq_records"][0]
    assert record["seq_allowed"] is True
    assert record["seq_index"] == 0
    assert record["previous_seq_hash"] is None
    assert record["initial_state_hash"] == "state-a"
    assert record["action_id"] == "inspect"
    assert record["observed_state_hash"] == "state-b"
    assert record["surprise_level"] == "medium"
    assert record["learning_signal"] == "bounded_update"
    assert record["raw_state_persisted"] is False
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["next_action"] == "index_temporal_memory"

    summary = summarize_cortex_seq(profile / CORTEX_SEQ_FILENAME)
    assert summary["latest_seq_allowed"] is True
    assert summary["latest_seq_index"] == 0

    verification = verify_cortex_seq_chain(profile / CORTEX_SEQ_FILENAME)
    assert verification["chain_valid"] is True
    assert verification["blockers"] == []


def test_cortex_seq_chains_multiple_records(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    first = build_cortex_seq(
        profile,
        initial_state=_state("state-a"),
        transition_record=_transition("state-a", "transition-a", "inspect"),
        observed_state=_state("state-b"),
        error_record=_error("transition-a", "state-b", "error-a"),
    )
    second = build_cortex_seq(
        profile,
        initial_state=_state("state-b"),
        transition_record=_transition("state-b", "transition-b", "review"),
        observed_state=_state("state-c"),
        error_record=_error("transition-b", "state-c", "error-b"),
    )

    first_record = first["seq_records"][0]
    second_record = second["seq_records"][0]
    assert second["seq_count"] == 2
    assert second_record["seq_index"] == 1
    assert second_record["previous_seq_hash"] == first_record["seq_hash"]

    verification = verify_cortex_seq_chain(profile / CORTEX_SEQ_FILENAME)
    assert verification["chain_valid"] is True
    assert verification["seq_count"] == 2


def test_cortex_seq_is_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    kwargs = {
        "initial_state": _state("state-a"),
        "transition_record": _transition(
            "state-a",
            "transition-a",
            "inspect",
        ),
        "observed_state": _state("state-b"),
        "error_record": _error("transition-a", "state-b", "error-a"),
    }

    first = build_cortex_seq(profile, **kwargs)
    second = build_cortex_seq(profile, **kwargs)

    assert first["seq_count"] == 1
    assert second["seq_count"] == 1
    assert (
        first["seq_records"][0]["seq_hash"]
        == second["seq_records"][0]["seq_hash"]
    )
    assert second["seq_records"][0]["seq_index"] == 0


def test_cortex_seq_blocks_lineage_mismatch(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_seq(
        profile,
        initial_state=_state("state-a"),
        transition_record=_transition(
            "wrong-source",
            "transition-a",
            "inspect",
        ),
        observed_state=_state("state-b"),
        error_record=_error(
            "wrong-transition",
            "wrong-observed",
            "error-a",
        ),
    )

    record = payload["seq_records"][0]
    assert record["seq_allowed"] is False
    assert "transition_source_state_mismatch" in record["blockers"]
    assert "prediction_error_transition_mismatch" in record["blockers"]
    assert "prediction_error_observed_state_mismatch" in record["blockers"]
    assert record["next_action"] == "repair_sequence_lineage"


def test_cortex_seq_chain_verifier_detects_tampering(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    build_cortex_seq(
        profile,
        initial_state=_state("state-a"),
        transition_record=_transition("state-a", "transition-a", "inspect"),
        observed_state=_state("state-b"),
        error_record=_error("transition-a", "state-b", "error-a"),
    )
    path = profile / CORTEX_SEQ_FILENAME
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["seq_index"] = 3
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    verification = verify_cortex_seq_chain(path)

    assert verification["chain_valid"] is False
    assert "seq_0_index_mismatch" in verification["blockers"]


def _state(state_hash: str) -> dict[str, object]:
    return {
        "state_allowed": True,
        "state_hash": state_hash,
    }


def _transition(
    source_hash: str,
    transition_hash: str,
    action_id: str,
) -> dict[str, object]:
    return {
        "transition_allowed": True,
        "source_state_hash": source_hash,
        "transition_hash": transition_hash,
        "action_id": action_id,
    }


def _error(
    transition_hash: str,
    observed_hash: str,
    error_hash: str,
) -> dict[str, object]:
    return {
        "prediction_error_allowed": True,
        "transition_hash": transition_hash,
        "observed_state_hash": observed_hash,
        "prediction_error_hash": error_hash,
        "surprise_score": 0.3,
        "surprise_level": "medium",
        "learning_signal": "bounded_update",
        "next_action": "review_prediction",
    }
