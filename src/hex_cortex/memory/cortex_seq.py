from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_SEQ_FILENAME = "cortex-seq.jsonl"


def build_cortex_seq(
    profile: Path,
    *,
    initial_state: dict[str, object],
    transition_record: dict[str, object],
    observed_state: dict[str, object],
    error_record: dict[str, object],
) -> dict[str, object]:
    blockers = _blockers(
        initial_state,
        transition_record,
        observed_state,
        error_record,
    )
    path = profile / CORTEX_SEQ_FILENAME
    rows = _load(path)
    source_key = _hash(
        str(initial_state.get("state_hash")),
        str(transition_record.get("transition_hash")),
        str(observed_state.get("state_hash")),
        str(error_record.get("prediction_error_hash")),
    )
    existing = next(
        (row for row in rows if row.get("source_key") == source_key),
        None,
    )
    if existing is not None:
        return {
            "seq_type": "cortex_temporal_sequence",
            "seq_path": str(path),
            "seq_count": len(rows),
            "seq_records": [existing],
        }
    seq_index = len(rows)
    previous_seq_hash = rows[-1].get("seq_hash") if rows else None
    allowed = not blockers
    surprise_score = _number(
        error_record.get("surprise_score"),
        default=0.0,
    )
    seq_hash = _hash(
        str(profile),
        str(seq_index),
        str(previous_seq_hash),
        source_key,
        str(surprise_score),
        *blockers,
    )
    record = {
        "seq_id": f"cortex_seq_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "seq_status": "ready" if allowed else "blocked",
        "seq_allowed": allowed,
        "seq_index": seq_index,
        "previous_seq_hash": previous_seq_hash,
        "initial_state_hash": initial_state.get("state_hash"),
        "action_id": transition_record.get("action_id"),
        "transition_hash": transition_record.get("transition_hash"),
        "observed_state_hash": observed_state.get("state_hash"),
        "prediction_error_hash": error_record.get("prediction_error_hash"),
        "surprise_score": surprise_score,
        "surprise_level": error_record.get("surprise_level"),
        "learning_signal": error_record.get("learning_signal"),
        "repair_signal": error_record.get("next_action"),
        "raw_state_persisted": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "next_action": (
            "index_temporal_memory"
            if allowed
            else "repair_sequence_lineage"
        ),
        "blockers": blockers,
        "source_key": source_key,
        "seq_hash": seq_hash,
    }
    rows.append(record)
    _write(path, rows)
    return {
        "seq_type": "cortex_temporal_sequence",
        "seq_path": str(path),
        "seq_count": len(rows),
        "seq_records": [record],
    }


def summarize_cortex_seq(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_temporal_sequence",
        "path": str(path),
        "exists": path.exists(),
        "total_seq_count": len(rows),
        "latest_seq_allowed": latest.get("seq_allowed") if latest else None,
        "latest_seq_index": latest.get("seq_index") if latest else None,
        "latest_seq_hash": latest.get("seq_hash") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def verify_cortex_seq_chain(path: Path) -> dict[str, object]:
    rows = _load(path)
    blockers = []
    for index, row in enumerate(rows):
        expected_previous = rows[index - 1].get("seq_hash") if index else None
        if row.get("seq_index") != index:
            blockers.append(f"seq_{index}_index_mismatch")
        if row.get("previous_seq_hash") != expected_previous:
            blockers.append(f"seq_{index}_previous_hash_mismatch")
    return {
        "verify_type": "cortex_temporal_sequence_chain",
        "path": str(path),
        "seq_count": len(rows),
        "chain_valid": not blockers,
        "blockers": blockers,
    }


def _blockers(
    initial_state: dict[str, object],
    transition_record: dict[str, object],
    observed_state: dict[str, object],
    error_record: dict[str, object],
) -> list[str]:
    blockers = []
    if initial_state.get("state_allowed") is not True:
        blockers.append("initial_state_not_allowed")
    if transition_record.get("transition_allowed") is not True:
        blockers.append("transition_not_allowed")
    if observed_state.get("state_allowed") is not True:
        blockers.append("observed_state_not_allowed")
    if error_record.get("prediction_error_allowed") is not True:
        blockers.append("prediction_error_not_allowed")
    initial_hash = _text(initial_state.get("state_hash"))
    transition_source = _text(transition_record.get("source_state_hash"))
    transition_hash = _text(transition_record.get("transition_hash"))
    observed_hash = _text(observed_state.get("state_hash"))
    error_transition = _text(error_record.get("transition_hash"))
    error_observed = _text(error_record.get("observed_state_hash"))
    error_hash = _text(error_record.get("prediction_error_hash"))
    if not initial_hash:
        blockers.append("missing_initial_state_hash")
    if not transition_hash:
        blockers.append("missing_transition_hash")
    if not observed_hash:
        blockers.append("missing_observed_state_hash")
    if not error_hash:
        blockers.append("missing_prediction_error_hash")
    if initial_hash and transition_source and initial_hash != transition_source:
        blockers.append("transition_source_state_mismatch")
    if transition_hash and error_transition and transition_hash != error_transition:
        blockers.append("prediction_error_transition_mismatch")
    if observed_hash and error_observed and observed_hash != error_observed:
        blockers.append("prediction_error_observed_state_mismatch")
    return blockers


def _number(value: object, *, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
