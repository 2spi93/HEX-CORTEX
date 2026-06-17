"""Gate registry update proposals without mutating the skill registry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.controlled_execution_receipt import (
    CONTROLLED_EXECUTION_RECEIPT_FILENAME,
    ControlledExecutionReceiptJsonlStore,
)
from hex_cortex.memory.registry_learning_candidate import (
    REGISTRY_LEARNING_FILENAME,
    RegistryLearningCandidateJsonlStore,
)

REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME = "registry-update-proposal-gate.jsonl"


class RegistryUpdateProposalGateRecord(BaseModel):
    """One persisted registry update proposal gate decision."""

    proposal_gate_id: str = Field(default_factory=lambda: f"registry_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_learning_id: str | None
    source_receipt_id: str | None
    learning_decision: str | None
    receipt_decision: str | None
    certification: str | None
    proposal_status: str
    proposal_decision: str
    proposal_allowed: bool
    proposal_type: str
    next_action: str
    proposal_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class RegistryUpdateProposalGateSummary(BaseModel):
    """Summary of persisted registry update proposal gate decisions."""

    inspect_type: str = "registry_update_proposal_gate"
    path: str
    exists: bool
    total_proposal_gate_count: int = Field(ge=0)
    latest_proposal_gate_id: str | None
    latest_selected_skill: str | None
    latest_proposal_status: str | None
    latest_proposal_decision: str | None
    latest_proposal_allowed: bool | None
    latest_next_action: str | None
    latest_proposal_confidence: float | None


class RegistryUpdateProposalGateJsonlStore:
    """Persist registry update proposal gates as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[RegistryUpdateProposalGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        RegistryUpdateProposalGateRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid registry update proposal gate at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[RegistryUpdateProposalGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: RegistryUpdateProposalGateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def evaluate_registry_update_proposal_gate(profile: Path) -> dict[str, object]:
    """Evaluate whether a registry update proposal may be prepared."""

    learning_records = RegistryLearningCandidateJsonlStore(
        profile / REGISTRY_LEARNING_FILENAME
    ).load()
    receipts = ControlledExecutionReceiptJsonlStore(
        profile / CONTROLLED_EXECUTION_RECEIPT_FILENAME
    ).load()
    if not learning_records:
        record = _missing_learning_gate(profile, receipts[-1] if receipts else None)
    else:
        record = _gate_from_sources(
            profile,
            learning_records[-1],
            receipts[-1] if receipts else None,
        )
    path = profile / REGISTRY_UPDATE_PROPOSAL_GATE_FILENAME
    count = RegistryUpdateProposalGateJsonlStore(path).append(record)
    return {
        "proposal_gate_type": "registry_update_proposal_gate",
        "profile_path": str(profile),
        "proposal_gate_path": str(path),
        "proposal_gate_count": count,
        "proposal_gate_record": record.model_dump(mode="json"),
    }


def summarize_registry_update_proposal_gates(path: Path) -> dict[str, object]:
    records = RegistryUpdateProposalGateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = RegistryUpdateProposalGateSummary(
        path=str(path),
        exists=path.exists(),
        total_proposal_gate_count=len(records),
        latest_proposal_gate_id=latest.proposal_gate_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_proposal_status=latest.proposal_status if latest else None,
        latest_proposal_decision=latest.proposal_decision if latest else None,
        latest_proposal_allowed=latest.proposal_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_proposal_confidence=latest.proposal_confidence if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_learning_gate(profile: Path, receipt) -> RegistryUpdateProposalGateRecord:
    return RegistryUpdateProposalGateRecord(
        profile_path=str(profile),
        selected_skill=receipt.selected_skill if receipt else "registry_learning_missing",
        source_learning_id=None,
        source_receipt_id=receipt.receipt_id if receipt else None,
        learning_decision=None,
        receipt_decision=receipt.receipt_decision if receipt else None,
        certification=receipt.certification if receipt else None,
        proposal_status="blocked",
        proposal_decision="proposal_blocked",
        proposal_allowed=False,
        proposal_type="none",
        next_action="build_registry_learning_candidate",
        proposal_confidence=0.0,
        reasons=["registry_learning_candidate_missing"],
    )


def _gate_from_sources(profile: Path, learning, receipt) -> RegistryUpdateProposalGateRecord:
    if _can_prepare_update(learning, receipt):
        return _ready_proposal_gate(profile, learning, receipt)
    if learning.learning_decision == "learning_hold":
        return _hold_proposal_gate(profile, learning, receipt)
    return _blocked_proposal_gate(profile, learning, receipt)


def _can_prepare_update(learning, receipt) -> bool:
    return (
        learning.learning_decision == "learning_ready"
        and receipt is not None
        and receipt.receipt_decision == "receipt_success"
        and receipt.certification == "controlled_execution_success_observed"
    )


def _ready_proposal_gate(profile: Path, learning, receipt) -> RegistryUpdateProposalGateRecord:
    return RegistryUpdateProposalGateRecord(
        profile_path=str(profile),
        selected_skill=learning.selected_skill,
        source_learning_id=learning.learning_id,
        source_receipt_id=receipt.receipt_id,
        learning_decision=learning.learning_decision,
        receipt_decision=receipt.receipt_decision,
        certification=receipt.certification,
        proposal_status="ready",
        proposal_decision="proposal_ready",
        proposal_allowed=True,
        proposal_type=_proposal_type(learning),
        next_action="prepare_registry_update_proposal_document",
        proposal_confidence=learning.learning_score,
        reasons=["registry_update_proposal_gate_ready"],
    )


def _hold_proposal_gate(profile: Path, learning, receipt) -> RegistryUpdateProposalGateRecord:
    return RegistryUpdateProposalGateRecord(
        profile_path=str(profile),
        selected_skill=learning.selected_skill,
        source_learning_id=learning.learning_id,
        source_receipt_id=receipt.receipt_id if receipt else None,
        learning_decision=learning.learning_decision,
        receipt_decision=receipt.receipt_decision if receipt else None,
        certification=receipt.certification if receipt else None,
        proposal_status="watch",
        proposal_decision="proposal_hold",
        proposal_allowed=False,
        proposal_type="none",
        next_action=learning.next_action,
        proposal_confidence=learning.learning_score,
        reasons=["registry_learning_hold", *learning.reasons],
    )


def _blocked_proposal_gate(profile: Path, learning, receipt) -> RegistryUpdateProposalGateRecord:
    return RegistryUpdateProposalGateRecord(
        profile_path=str(profile),
        selected_skill=learning.selected_skill,
        source_learning_id=learning.learning_id,
        source_receipt_id=receipt.receipt_id if receipt else None,
        learning_decision=learning.learning_decision,
        receipt_decision=receipt.receipt_decision if receipt else None,
        certification=receipt.certification if receipt else None,
        proposal_status="blocked",
        proposal_decision="proposal_blocked",
        proposal_allowed=False,
        proposal_type="none",
        next_action="repair_registry_learning_inputs",
        proposal_confidence=learning.learning_score,
        reasons=["registry_update_proposal_not_allowed", *learning.reasons],
    )


def _proposal_type(learning) -> str:
    if learning.registry_status == "fallback":
        return "skill_activation_proposal"
    return "skill_confidence_update_proposal"
