from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_SURPRISE_FILENAME = "cortex-surprise.jsonl"


def build_cortex_surprise(
    profile: Path,
    *,
    transition_record: dict[str, object],
    observed_state: dict[str, object],
    low_threshold: float = 0.2,
    high_threshold: float = 0.5,
) -> dict[str, object]:
    blockers = _blockers(
        transition_record,
        observed_state,
        low_threshold,
        high_threshold,
    )
    allowed = not blockers
    predicted_capabilities = _string_list(
        transition_record.get("predicted_capabilities")
    )
    observed_capabilities = _string_list(
        observed_state.get("capabilities")
    )
    predicted_set = set(predicted_capabilities)
    observed_set = set(observed_capabilities)
    missing_expected = sorted(predicted_set - observed_set)
    unexpected_observed = sorted(observed_set - predicted_set)
    capability_union = predicted_set.union(observed_set)
    capability_error = (
        round(
            len(predicted_set.symmetric_difference(observed_set))
            / len(capability_union),
            4,
        )
        if capability_union
        else 0.0
    )
    predicted_confidence = _number(
        transition_record.get("predicted_average_confidence"),
        default=0.0,
    )
    observed_confidence = _number(
        observed_state.get("average_confidence"),
        default=0.0,
    )
    confidence_error = round(
        abs(predicted_confidence - observed_confidence),
        4,
    )
    surprise_score = round(
        0.7 * capability_error + 0.3 * confidence_error,
        4,
    )
    surprise_level = (
        _surprise_level(surprise_score, low_threshold, high_threshold)
        if allowed
        else None
    )
    learning_signal = (
        _learning_signal(surprise_level)
        if surprise_level is not None
        else None
    )
    predicted_feature_hash = _feature_hash(
        predicted_capabilities,
        predicted_confidence,
    )
    observed_feature_hash = _feature_hash(
        observed_capabilities,
        observed_confidence,
    )
    error_hash = _hash(
        str(profile),
        str(transition_record.get("transition_hash")),
        str(observed_state.get("state_hash")),
        predicted_feature_hash,
        observed_feature_hash,
        str(surprise_score),
        *blockers,
    )
    record = {
        "prediction_error_id": f"cortex_error_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "prediction_error_status": "ready" if allowed else "blocked",
        "prediction_error_allowed": allowed,
        "transition_hash": transition_record.get("transition_hash"),
        "observed_state_hash": observed_state.get("state_hash"),
        "predicted_feature_hash": predicted_feature_hash,
        "observed_feature_hash": observed_feature_hash,
        "feature_hash_match": predicted_feature_hash == observed_feature_hash,
        "missing_expected_capabilities": missing_expected,
        "unexpected_observed_capabilities": unexpected_observed,
        "capability_error": capability_error,
        "confidence_error": confidence_error,
        "surprise_score": surprise_score,
        "surprise_level": surprise_level,
        "learning_signal": learning_signal,
        "model_call_performed": False,
        "network_call_performed": False,
        "raw_state_persisted": False,
        "next_action": (
            _next_action(surprise_level)
            if allowed
            else "repair_prediction_error_input"
        ),
        "blockers": blockers,
        "prediction_error_hash": error_hash,
    }
    path = profile / CORTEX_SURPRISE_FILENAME
    rows = _load(path)
    if not any(
        row.get("prediction_error_hash") == error_hash
        for row in rows
    ):
        rows.append(record)
    _write(path, rows)
    return {
        "prediction_error_type": "cortex_prediction_error",
        "prediction_error_path": str(path),
        "prediction_error_count": len(rows),
        "prediction_error_records": [record],
    }


def summarize_cortex_surprise(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_prediction_error",
        "path": str(path),
        "exists": path.exists(),
        "total_prediction_error_count": len(rows),
        "latest_prediction_error_allowed": (
            latest.get("prediction_error_allowed") if latest else None
        ),
        "latest_surprise_score": (
            latest.get("surprise_score") if latest else None
        ),
        "latest_surprise_level": (
            latest.get("surprise_level") if latest else None
        ),
        "latest_next_action": (
            latest.get("next_action") if latest else None
        ),
    }


def _blockers(
    transition_record: dict[str, object],
    observed_state: dict[str, object],
    low_threshold: float,
    high_threshold: float,
) -> list[str]:
    blockers = []
    if transition_record.get("transition_allowed") is not True:
        blockers.append("transition_not_allowed")
    if not _text(transition_record.get("transition_hash")):
        blockers.append("missing_transition_hash")
    if observed_state.get("state_allowed") is not True:
        blockers.append("observed_state_not_allowed")
    if not _text(observed_state.get("state_hash")):
        blockers.append("missing_observed_state_hash")
    if not _valid_string_list(
        transition_record.get("predicted_capabilities")
    ):
        blockers.append("predicted_capabilities_invalid")
    if not _valid_string_list(observed_state.get("capabilities")):
        blockers.append("observed_capabilities_invalid")
    if not _valid_confidence(
        transition_record.get("predicted_average_confidence")
    ):
        blockers.append("predicted_confidence_invalid")
    if not _valid_confidence(observed_state.get("average_confidence")):
        blockers.append("observed_confidence_invalid")
    if not (
        _is_number(low_threshold)
        and _is_number(high_threshold)
        and 0 <= low_threshold < high_threshold <= 1
    ):
        blockers.append("surprise_thresholds_invalid")
    return blockers


def _surprise_level(
    score: float,
    low_threshold: float,
    high_threshold: float,
) -> str:
    if score <= low_threshold:
        return "low"
    if score < high_threshold:
        return "medium"
    return "high"


def _learning_signal(level: str) -> str:
    return {
        "low": "no_update",
        "medium": "bounded_update",
        "high": "priority_update",
    }[level]


def _next_action(level: str | None) -> str:
    return {
        "low": "accept_prediction",
        "medium": "review_prediction",
        "high": "repair_transition_model",
    }.get(level, "repair_prediction_error_input")


def _feature_hash(capabilities: list[str], confidence: float) -> str:
    return _hash(*sorted(capabilities), str(round(confidence, 4)))


def _valid_string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) for item in value
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _valid_confidence(value: object) -> bool:
    return _is_number(value) and 0 <= float(value) <= 1


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _number(value: object, *, default: float) -> float:
    return float(value) if _is_number(value) else default


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
