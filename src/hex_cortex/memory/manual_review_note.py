"""Manual operator review notes for HEX-CORTEX profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

MANUAL_REVIEW_NOTE_FILENAME = "manual-review-note.jsonl"
ALLOWED_MANUAL_REVIEW_CHOICES = {"accept", "decline", "hold"}


class ManualReviewNoteRecord(BaseModel):
    """One persisted manual operator review note."""

    note_id: str = Field(default_factory=lambda: f"manual_review_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    operator_choice: str
    note_status: str
    note_allowed: bool
    reviewer: str
    note: str
    next_action: str
    reasons: list[str]


class ManualReviewNoteSummary(BaseModel):
    """Summary of persisted manual review notes."""

    inspect_type: str = "manual_review_note"
    path: str
    exists: bool
    total_note_count: int = Field(ge=0)
    latest_note_id: str | None
    latest_selected_skill: str | None
    latest_operator_choice: str | None
    latest_note_status: str | None
    latest_note_allowed: bool | None
    latest_next_action: str | None


class ManualReviewNoteJsonlStore:
    """Persist manual review notes as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ManualReviewNoteRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ManualReviewNoteRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid manual review note at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ManualReviewNoteRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ManualReviewNoteRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_manual_review_note(
    profile: Path,
    *,
    selected_skill: str,
    choice: str,
    note: str,
    reviewer: str = "operator_local",
) -> dict[str, object]:
    """Record one manual review note."""

    if choice not in ALLOWED_MANUAL_REVIEW_CHOICES:
        raise ValueError(f"unsupported manual review choice: {choice}")
    note_allowed = choice == "accept"
    record = ManualReviewNoteRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        operator_choice=choice,
        note_status="ready" if note_allowed else "watch",
        note_allowed=note_allowed,
        reviewer=reviewer,
        note=note,
        next_action=(
            "rerun_construction_status"
            if note_allowed
            else "prepare_skill_activation_review"
        ),
        reasons=[f"manual_review_{choice}"],
    )
    path = profile / MANUAL_REVIEW_NOTE_FILENAME
    count = ManualReviewNoteJsonlStore(path).append(record)
    return {
        "note_type": "manual_review_note",
        "profile_path": str(profile),
        "note_path": str(path),
        "note_count": count,
        "note_record": record.model_dump(mode="json"),
    }


def summarize_manual_review_notes(path: Path) -> dict[str, object]:
    records = ManualReviewNoteJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ManualReviewNoteSummary(
        path=str(path),
        exists=path.exists(),
        total_note_count=len(records),
        latest_note_id=latest.note_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_operator_choice=latest.operator_choice if latest else None,
        latest_note_status=latest.note_status if latest else None,
        latest_note_allowed=latest.note_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")
