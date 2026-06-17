"""Review propagation records derived from manual review notes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.manual_review_note import (
    MANUAL_REVIEW_NOTE_FILENAME,
    ManualReviewNoteJsonlStore,
)

REVIEW_PROPAGATION_FILENAME = "review-propagation.jsonl"


class ReviewPropagationRecord(BaseModel):
    """One persisted review propagation record."""

    propagation_id: str = Field(
        default_factory=lambda: f"review_propagation_{uuid4().hex}"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_note_id: str | None
    operator_choice: str | None
    note_allowed: bool
    propagation_status: str
    propagation_decision: str
    propagation_allowed: bool
    next_action: str
    reasons: list[str]


class ReviewPropagationSummary(BaseModel):
    """Summary of persisted review propagation records."""

    inspect_type: str = "review_propagation"
    path: str
    exists: bool
    total_propagation_count: int = Field(ge=0)
    latest_propagation_id: str | None
    latest_selected_skill: str | None
    latest_operator_choice: str | None
    latest_propagation_status: str | None
    latest_propagation_decision: str | None
    latest_propagation_allowed: bool | None
    latest_next_action: str | None


class ReviewPropagationJsonlStore:
    """Persist review propagation records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewPropagationRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReviewPropagationRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review propagation at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewPropagationRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewPropagationRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_propagation(profile: Path) -> dict[str, object]:
    """Build one propagation record from the latest manual review note."""

    notes = ManualReviewNoteJsonlStore(profile / MANUAL_REVIEW_NOTE_FILENAME).load()
    if not notes:
        record = _missing_note_propagation(profile)
    else:
        record = _propagation_from_note(profile, notes[-1])
    path = profile / REVIEW_PROPAGATION_FILENAME
    count = ReviewPropagationJsonlStore(path).append(record)
    return {
        "propagation_type": "review_propagation",
        "profile_path": str(profile),
        "propagation_path": str(path),
        "propagation_count": count,
        "propagation_record": record.model_dump(mode="json"),
    }


def summarize_review_propagations(path: Path) -> dict[str, object]:
    records = ReviewPropagationJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewPropagationSummary(
        path=str(path),
        exists=path.exists(),
        total_propagation_count=len(records),
        latest_propagation_id=latest.propagation_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_operator_choice=latest.operator_choice if latest else None,
        latest_propagation_status=latest.propagation_status if latest else None,
        latest_propagation_decision=latest.propagation_decision if latest else None,
        latest_propagation_allowed=latest.propagation_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_note_propagation(profile: Path) -> ReviewPropagationRecord:
    return ReviewPropagationRecord(
        profile_path=str(profile),
        selected_skill="manual_review_missing",
        source_note_id=None,
        operator_choice=None,
        note_allowed=False,
        propagation_status="blocked",
        propagation_decision="propagation_blocked",
        propagation_allowed=False,
        next_action="record_manual_review_note",
        reasons=["manual_review_note_missing"],
    )


def _propagation_from_note(profile: Path, note) -> ReviewPropagationRecord:
    if note.note_allowed and note.operator_choice == "accept":
        return ReviewPropagationRecord(
            profile_path=str(profile),
            selected_skill=note.selected_skill,
            source_note_id=note.note_id,
            operator_choice=note.operator_choice,
            note_allowed=note.note_allowed,
            propagation_status="ready",
            propagation_decision="propagation_ready",
            propagation_allowed=True,
            next_action="rerun_construction_status",
            reasons=["manual_review_accept_propagated"],
        )
    return ReviewPropagationRecord(
        profile_path=str(profile),
        selected_skill=note.selected_skill,
        source_note_id=note.note_id,
        operator_choice=note.operator_choice,
        note_allowed=note.note_allowed,
        propagation_status="watch",
        propagation_decision="propagation_watch",
        propagation_allowed=False,
        next_action=note.next_action,
        reasons=[f"manual_review_{note.operator_choice}_not_promoted"],
    )
