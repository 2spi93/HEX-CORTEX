"""Deterministic promotion selector for HEX-CORTEX self-improvement."""

from __future__ import annotations

from hex_cortex.evolver.schemas import (
    EvaluationMetric,
    EvaluationResult,
    ImprovementHypothesis,
    PromotionDecision,
    PromotionDecisionType,
    RiskLevel,
)


class EvolutionSelector:
    """Decides whether an improvement hypothesis is safe to promote.

    This is a gate, not an autonomous code modifier.
    """

    def __init__(self, *, min_score: float = 0.75, allow_high_risk: bool = False) -> None:
        self.min_score = min_score
        self.allow_high_risk = allow_high_risk

    def score(self, evaluation: EvaluationResult) -> float:
        """Compute weighted pass score from evaluation metrics."""

        if not evaluation.metrics:
            return 0.0

        total_weight = sum(metric.weight for metric in evaluation.metrics)
        if total_weight <= 0:
            return 0.0

        passed_weight = sum(
            metric.weight * self._metric_value(metric)
            for metric in evaluation.metrics
        )
        return max(0.0, min(1.0, passed_weight / total_weight))

    def decide(
        self,
        hypothesis: ImprovementHypothesis,
        evaluation: EvaluationResult,
        *,
        rollback_plan: str | None = None,
    ) -> PromotionDecision:
        """Create a promotion decision for one hypothesis/evaluation pair."""

        if evaluation.hypothesis_id != hypothesis.hypothesis_id:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.REJECT,
                reason="evaluation_hypothesis_mismatch",
                score=0.0,
            )

        if hypothesis.risk_level == RiskLevel.CRITICAL:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.QUARANTINE,
                reason="critical_risk_requires_manual_review",
                score=0.0,
            )

        if hypothesis.risk_level == RiskLevel.HIGH and not self.allow_high_risk:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.NEEDS_MORE_EVIDENCE,
                reason="high_risk_requires_explicit_allowance",
                score=0.0,
            )

        score = self.score(evaluation)

        if evaluation.regressions:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.REJECT,
                reason="regressions_detected",
                score=score,
            )

        if not evaluation.tests_passed:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.REJECT,
                reason="tests_failed",
                score=score,
            )

        if score < self.min_score:
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.NEEDS_MORE_EVIDENCE,
                reason="score_below_threshold",
                score=score,
            )

        if not (rollback_plan or "").strip():
            return PromotionDecision(
                hypothesis_id=hypothesis.hypothesis_id,
                evaluation_id=evaluation.evaluation_id,
                decision=PromotionDecisionType.NEEDS_MORE_EVIDENCE,
                reason="missing_rollback_plan",
                score=score,
            )

        return PromotionDecision(
            hypothesis_id=hypothesis.hypothesis_id,
            evaluation_id=evaluation.evaluation_id,
            decision=PromotionDecisionType.PROMOTE,
            reason="evaluation_passed_with_rollback_plan",
            score=score,
            rollback_plan=rollback_plan,
        )

    @staticmethod
    def _metric_value(metric: EvaluationMetric) -> float:
        if not metric.passed:
            return 0.0
        return max(0.0, min(metric.value, 1.0))
