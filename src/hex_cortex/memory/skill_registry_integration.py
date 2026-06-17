"""Integrate symbolic latent states with the persistent skill registry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.evolver.skill_library import SkillLibrary
from hex_cortex.memory.latent_state_compression import (
    LATENT_STATE_FILENAME,
    LatentStateJsonlStore,
)

SKILL_REGISTRY_FILENAME = "skills.jsonl"
SKILL_REGISTRY_MATCH_FILENAME = "skill-registry-match.jsonl"


class SkillRegistryMatchRecord(BaseModel):
    """One persisted latent-to-skill registry match."""

    match_id: str = Field(default_factory=lambda: f"skill_match_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    latent_id: str | None
    registry_path: str
    registry_status: str
    latent_suggested_skill: str
    matched_skill_id: str | None
    matched_skill_name: str | None
    matched_skill_confidence: float | None
    match_score: float = Field(ge=0.0, le=1.0)
    match_reason: str
    trigger_tags: list[str]
    action_score: float = Field(ge=0.0, le=1.0)
    compression_score: float = Field(ge=0.0, le=1.0)


class SkillRegistryMatchSummary(BaseModel):
    """Summary of persisted registry matches."""

    inspect_type: str = "skill_registry_match"
    path: str
    exists: bool
    total_match_count: int = Field(ge=0)
    latest_match_id: str | None
    latest_registry_status: str | None
    latest_matched_skill_name: str | None
    latest_match_score: float | None
    latest_match_reason: str | None


class SkillRegistryMatchJsonlStore:
    """Persist registry matches as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillRegistryMatchRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(SkillRegistryMatchRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid skill registry match at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[SkillRegistryMatchRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: SkillRegistryMatchRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def match_latest_latent_to_skill_registry(profile: Path) -> dict[str, object]:
    """Match latest latent state against active skills in the local registry."""

    latent_records = LatentStateJsonlStore(profile / LATENT_STATE_FILENAME).load()
    registry_path = profile / SKILL_REGISTRY_FILENAME
    if not latent_records:
        record = _missing_latent_match(profile, registry_path)
    else:
        active_skills = SkillJsonlStore(registry_path).active()
        record = _match_latent(profile, registry_path, latent_records[-1], active_skills)
    path = profile / SKILL_REGISTRY_MATCH_FILENAME
    count = SkillRegistryMatchJsonlStore(path).append(record)
    return {
        "match_type": "skill_registry_integration",
        "profile_path": str(profile),
        "match_path": str(path),
        "match_count": count,
        "match_record": record.model_dump(mode="json"),
    }


def summarize_skill_registry_matches(path: Path) -> dict[str, object]:
    records = SkillRegistryMatchJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = SkillRegistryMatchSummary(
        path=str(path),
        exists=path.exists(),
        total_match_count=len(records),
        latest_match_id=latest.match_id if latest else None,
        latest_registry_status=latest.registry_status if latest else None,
        latest_matched_skill_name=latest.matched_skill_name if latest else None,
        latest_match_score=latest.match_score if latest else None,
        latest_match_reason=latest.match_reason if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_latent_match(profile: Path, registry_path: Path) -> SkillRegistryMatchRecord:
    return SkillRegistryMatchRecord(
        profile_path=str(profile),
        latent_id=None,
        registry_path=str(registry_path),
        registry_status="latent_missing",
        latent_suggested_skill="latent_state_missing",
        matched_skill_id=None,
        matched_skill_name=None,
        matched_skill_confidence=None,
        match_score=0.0,
        match_reason="latent_state_missing",
        trigger_tags=[],
        action_score=0.0,
        compression_score=0.0,
    )


def _match_latent(
    profile: Path,
    registry_path: Path,
    latent,
    active_skills,
) -> SkillRegistryMatchRecord:
    trigger_tags = _trigger_tags(latent)
    if not active_skills:
        return _fallback_match(profile, registry_path, latent, trigger_tags)
    library = SkillLibrary(active_skills)
    matches = library.search(trigger_tags)
    if not matches:
        return _fallback_match(profile, registry_path, latent, trigger_tags)
    best = _best_skill(matches, latent)
    return SkillRegistryMatchRecord(
        profile_path=str(profile),
        latent_id=latent.latent_id,
        registry_path=str(registry_path),
        registry_status="matched",
        latent_suggested_skill=latent.suggested_skill,
        matched_skill_id=best.skill_id,
        matched_skill_name=best.name,
        matched_skill_confidence=best.confidence,
        match_score=_match_score(best, latent),
        match_reason="active_skill_matched_from_latent_tags",
        trigger_tags=trigger_tags,
        action_score=latent.action_score,
        compression_score=latent.compression_score,
    )


def _fallback_match(
    profile: Path,
    registry_path: Path,
    latent,
    trigger_tags: list[str],
) -> SkillRegistryMatchRecord:
    return SkillRegistryMatchRecord(
        profile_path=str(profile),
        latent_id=latent.latent_id,
        registry_path=str(registry_path),
        registry_status="fallback",
        latent_suggested_skill=latent.suggested_skill,
        matched_skill_id=None,
        matched_skill_name=latent.suggested_skill,
        matched_skill_confidence=None,
        match_score=round(latent.action_score * 0.5, 4),
        match_reason="no_active_registry_skill_matched",
        trigger_tags=trigger_tags,
        action_score=latent.action_score,
        compression_score=latent.compression_score,
    )


def _trigger_tags(latent) -> list[str]:
    tags = [latent.suggested_skill, latent.candidate_action]
    for token in latent.tokens:
        if ":" in token:
            tags.append(token.split(":", maxsplit=1)[1])
    return sorted({tag for tag in tags if tag})


def _best_skill(skills, latent):
    return sorted(skills, key=lambda skill: _match_score(skill, latent), reverse=True)[0]


def _match_score(skill, latent) -> float:
    skill_tags = {tag.lower() for tag in skill.trigger_tags}
    latent_tags = {tag.lower() for tag in _trigger_tags(latent)}
    overlap = len(skill_tags.intersection(latent_tags))
    overlap_score = min(overlap / 3, 1.0)
    name_bonus = 1.0 if skill.name == latent.suggested_skill else 0.0
    raw = (0.45 * overlap_score) + (0.35 * name_bonus) + (0.2 * skill.confidence)
    return round(raw * latent.action_score * latent.compression_score, 4)
