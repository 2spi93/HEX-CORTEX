"""Scientific corpus governance V19: versioned admission and revocation.

A bounded, hash-chained, *externally pinned* event ledger grants local
records permission to participate in the scientific evidence circuit.
An event hash is tamper-evidence, NOT a signature or publisher proof.
No network/model/device calls. A trusted operator must pin the head
independently of the editable ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from hex_cortex.core.cortex_scientific_knowledge_v16 import EvidenceRecord
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal,
    _read_regular_file,
)

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[a-z][a-z0-9_.-]{1,95}\Z")
_GENESIS = "0" * 64
_MAX_EVENTS = 128
_MAX_BYTES = 98_304


class CorpusRefusal(ValueError):
    """Safe error code without leaking untrusted source metadata."""


class CorpusOperation(StrEnum):
    ADMIT = "admit"
    REVOKE = "revoke"


class CorpusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int = Field(ge=1, le=_MAX_EVENTS)
    operation: CorpusOperation
    source_id: str
    revision: int = Field(ge=1, le=100_000)
    record_sha256: str
    previous_hash: str
    event_hash: str

    @field_validator("source_id")
    @classmethod
    def check_name(cls, value: str) -> str:
        if not _NAME.fullmatch(value):
            raise ValueError("corpus_source_id_invalid")
        return value

    @field_validator("record_sha256", "previous_hash", "event_hash")
    @classmethod
    def check_hash(cls, value: str) -> str:
        if not _HEX.fullmatch(value):
            raise ValueError("corpus_digest_invalid")
        return value


def _json_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def record_fingerprint(record: EvidenceRecord) -> str:
    """Fingerprint the *whole typed claim*, including source byte digest/version."""
    return _json_hash(record.model_dump(mode="json"))


def _event_hash(sequence: int, operation: CorpusOperation, source_id: str,
                revision: int, record_sha256: str, previous_hash: str) -> str:
    return _json_hash({
        "sequence": sequence,
        "operation": operation.value,
        "source_id": source_id,
        "revision": revision,
        "record_sha256": record_sha256,
        "previous_hash": previous_hash,
    })


def new_corpus_event(
    previous_events: list[CorpusEvent],
    *,
    operation: CorpusOperation,
    source_id: str,
    revision: int,
    record_sha256: str,
) -> CorpusEvent:
    """Construct the next candidate; validate state before an operator saves it."""
    state, head = inspect_corpus(previous_events)
    sequence = len(previous_events) + 1
    event = CorpusEvent(
        sequence=sequence, operation=operation, source_id=source_id,
        revision=revision, record_sha256=record_sha256, previous_hash=head,
        event_hash=_event_hash(sequence, operation, source_id, revision,
                               record_sha256, head),
    )
    _apply_event(state, event)
    return event


def _apply_event(
    state: dict[str, tuple[int, str, bool]],
    event: CorpusEvent,
) -> None:
    previous = state.get(event.source_id)
    if event.operation == CorpusOperation.ADMIT:
        if previous is not None and event.revision <= previous[0]:
            raise CorpusRefusal("corpus_revision_not_increasing")
        state[event.source_id] = (event.revision, event.record_sha256, True)
    else:
        if previous is None or not previous[2]:
            raise CorpusRefusal("corpus_revoke_requires_active_source")
        if (event.revision, event.record_sha256) != previous[:2]:
            raise CorpusRefusal("corpus_revoke_target_mismatch")
        state[event.source_id] = (event.revision, event.record_sha256, False)


def inspect_corpus(
    events: list[CorpusEvent],
    *,
    expected_head: str | None = None,
) -> tuple[dict[str, tuple[int, str, bool]], str]:
    """Replay the full chain, then optionally compare with trusted external pin."""
    if not isinstance(events, list) or len(events) > _MAX_EVENTS:
        raise CorpusRefusal("corpus_events_budget_invalid")
    if expected_head is not None and not _HEX.fullmatch(expected_head):
        raise CorpusRefusal("corpus_pin_invalid")
    state: dict[str, tuple[int, str, bool]] = {}
    head = _GENESIS
    for seq, event in enumerate(events, start=1):
        if not isinstance(event, CorpusEvent):
            raise CorpusRefusal("corpus_event_type_invalid")
        expected = _event_hash(
            event.sequence, event.operation, event.source_id, event.revision,
            event.record_sha256, event.previous_hash,
        )
        if event.sequence != seq or event.previous_hash != head or event.event_hash != expected:
            raise CorpusRefusal("corpus_history_chain_invalid")
        _apply_event(state, event)
        head = event.event_hash
    if expected_head is not None and head != expected_head:
        raise CorpusRefusal("corpus_externally_pinned_head_mismatch")
    return state, head


def load_corpus_events(path: Path, *, approved: bool = False) -> list[CorpusEvent]:
    """Read a bounded operator-selected JSON array; no implicit filesystem I/O."""
    if not approved:
        raise CorpusRefusal("corpus_operator_read_approval_required")
    try:
        raw = _read_regular_file(Path(path), max_bytes=_MAX_BYTES)
        values = json.loads(raw)
        if not isinstance(values, list) or len(values) > _MAX_EVENTS:
            raise CorpusRefusal("corpus_events_budget_invalid")
        events = [CorpusEvent.model_validate(value) for value in values]
    except (LocalEvidenceRefusal, ValidationError, UnicodeDecodeError,
            ValueError, TypeError) as exc:
        if isinstance(exc, CorpusRefusal):
            raise
        raise CorpusRefusal("corpus_ledger_read_or_schema_invalid") from exc
    inspect_corpus(events)
    return events


def evaluate_corpus_record(
    record: EvidenceRecord,
    *,
    ledger_path: Path,
    expected_head: str,
    base_verifier: Callable[[EvidenceRecord], bool],
    approved: bool = False,
) -> bool:
    """Re-read pinned governance AND source bytes on every verifier invocation.

    This recheck is intentional: a revocation or ledger replacement between
    evidence proposal and Critic verification must deny the final verdict.
    """
    if not approved or not isinstance(record, EvidenceRecord):
        return False
    if not isinstance(expected_head, str) or not _HEX.fullmatch(expected_head):
        return False
    try:
        events = load_corpus_events(ledger_path, approved=True)
        state, _ = inspect_corpus(events, expected_head=expected_head)
        selection = state.get(record.source_id)
        if selection is None or not selection[2]:
            return False
        if selection[1] != record_fingerprint(record):
            return False
        return base_verifier(record) is True
    except (CorpusRefusal, ValueError, OSError, TypeError):
        return False


def corpus_status(events: list[CorpusEvent], *,
                  expected_head: str | None = None) -> dict[str, object]:
    """Advisory redacted summary: source IDs and claims are not disclosed."""
    state, head = inspect_corpus(events, expected_head=expected_head)
    result = {
        "report_type": "hex_cortex_corpus_governance_v19",
        "chain_verified": True,
        "external_pin_verified": expected_head is not None,
        "head_sha256": head,
        "event_count": len(events),
        "sources_active": sum(1 for value in state.values() if value[2]),
        "sources_revoked": sum(1 for value in state.values() if not value[2]),
        "publisher_authenticity_verified": False,
        "scientific_truth_certified": False,
        "physical_action_authorized": False,
        "model_used": False,
        "checkout_modified": False,
    }
    return result
