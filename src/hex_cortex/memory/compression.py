"""Memory compression engine for HEX-CORTEX.

v0.1 deliberately uses deterministic heuristics. Heavy model-based summarization comes later.
"""

from __future__ import annotations

from hex_cortex.memory.schemas import (
    CompressionRecord,
    EpisodeSummary,
    MemoryRecord,
    ReplayOutcome,
    TacitRule,
)


class MemoryCompressionSpine:
    """Compress cognitive episodes into reusable memory records and tacit rules."""

    def summarize_episode(
        self,
        *,
        task_id: str,
        goal: str,
        active_cells: list[str],
        observations: list[str] | None = None,
        errors: list[str] | None = None,
        used_memory_ids: list[str] | None = None,
        outcome: ReplayOutcome = ReplayOutcome.UNKNOWN,
        confidence: float = 0.5,
    ) -> EpisodeSummary:
        return EpisodeSummary(
            task_id=task_id,
            goal=goal,
            active_cells=active_cells,
            used_memory_ids=used_memory_ids or [],
            outcome=outcome,
            observations=self._clean_lines(observations or []),
            errors=self._clean_lines(errors or []),
            confidence=confidence,
        )

    def compress_episode(
        self,
        episode: EpisodeSummary,
        *,
        source_event_ids: list[str],
    ) -> CompressionRecord:
        if not source_event_ids:
            raise ValueError("cannot compress episode without source_event_ids")

        summary = self._build_summary(episode)
        rules = self._extract_rules(episode, source_event_ids)

        return CompressionRecord(
            source_event_ids=source_event_ids,
            source_episode_id=episode.episode_id,
            summary=summary,
            extracted_rules=rules,
            confidence=episode.confidence,
        )

    def to_memory_record(self, compression: CompressionRecord) -> MemoryRecord:
        tags = ["compressed", "episode"]
        if compression.extracted_rules:
            tags.append("tacit-rule")

        body_parts = [compression.summary]
        for rule in compression.extracted_rules:
            body_parts.append(f"Rule: {rule.claim}")

        return MemoryRecord(
            title="Compressed cognitive episode",
            body="\n".join(body_parts),
            tags=tags,
            source_event_ids=compression.source_event_ids,
            confidence=compression.confidence,
            reason_for_storage="episode_compression",
        )

    def update_rule_from_replay(self, rule: TacitRule, outcome: ReplayOutcome) -> TacitRule:
        success_count = rule.success_count
        failure_count = rule.failure_count

        if outcome == ReplayOutcome.SUCCESS:
            success_count += 1
        elif outcome == ReplayOutcome.FAILURE:
            failure_count += 1

        confidence = self._confidence_from_counts(success_count, failure_count)

        return rule.model_copy(
            update={
                "success_count": success_count,
                "failure_count": failure_count,
                "confidence": confidence,
            }
        )

    def _extract_rules(
        self,
        episode: EpisodeSummary,
        source_event_ids: list[str],
    ) -> list[TacitRule]:
        rules: list[TacitRule] = []
        domains = self._domains_from_episode(episode)

        if episode.errors:
            rules.append(
                TacitRule(
                    claim=(
                        f"For tasks like '{episode.goal}', require CriticCell review before "
                        "ActionCell when errors are observed."
                    ),
                    applies_to=domains,
                    source_event_ids=source_event_ids,
                    source_episode_ids=[episode.episode_id],
                    failure_count=1,
                    confidence=0.55,
                )
            )

        if episode.outcome == ReplayOutcome.SUCCESS and episode.active_cells:
            cell_path = " → ".join(episode.active_cells)
            rules.append(
                TacitRule(
                    claim=(
                        f"For tasks like '{episode.goal}', the cell path "
                        f"{cell_path} was useful."
                    ),
                    applies_to=domains,
                    source_event_ids=source_event_ids,
                    source_episode_ids=[episode.episode_id],
                    success_count=1,
                    confidence=max(0.55, episode.confidence),
                )
            )

        if episode.used_memory_ids and episode.outcome == ReplayOutcome.SUCCESS:
            rules.append(
                TacitRule(
                    claim=(
                        f"For tasks like '{episode.goal}', retrieve prior memory "
                        "before deep reasoning."
                    ),
                    applies_to=[*domains, "memory"],
                    source_event_ids=source_event_ids,
                    source_episode_ids=[episode.episode_id],
                    success_count=1,
                    confidence=max(0.55, episode.confidence),
                )
            )

        return rules

    @staticmethod
    def _build_summary(episode: EpisodeSummary) -> str:
        parts = [f"Goal: {episode.goal}"]
        if episode.active_cells:
            parts.append(f"Cells: {', '.join(episode.active_cells)}")
        if episode.observations:
            parts.append(f"Observations: {'; '.join(episode.observations)}")
        if episode.errors:
            parts.append(f"Errors: {'; '.join(episode.errors)}")
        parts.append(f"Outcome: {episode.outcome.value}")
        return "\n".join(parts)

    @staticmethod
    def _domains_from_episode(episode: EpisodeSummary) -> list[str]:
        words = [
            word.strip(".,:;!?()[]{}'\"").lower()
            for word in episode.goal.split()
        ]
        return sorted({word for word in words if len(word) >= 4})[:8]

    @staticmethod
    def _clean_lines(lines: list[str]) -> list[str]:
        return [line.strip() for line in lines if line.strip()]

    @staticmethod
    def _confidence_from_counts(success_count: int, failure_count: int) -> float:
        total = success_count + failure_count
        if total == 0:
            return 0.5
        # Conservative Bayesian smoothing: two virtual neutral observations.
        return (success_count + 1) / (total + 2)
