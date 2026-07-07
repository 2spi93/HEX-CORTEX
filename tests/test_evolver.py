import pytest

from hex_cortex.evolver.schemas import (
    EvaluationMetric,
    EvaluationResult,
    ImprovementHypothesis,
    PromotionDecisionType,
    RiskLevel,
)
from hex_cortex.evolver.selector import EvolutionSelector


def make_hypothesis(risk_level: RiskLevel = RiskLevel.LOW) -> ImprovementHypothesis:
    return ImprovementHypothesis(
        title="Improve retrieval threshold",
        target_module="RetrievalRouter",
        rationale="Recent episodes show semantic fallback activates too often.",
        proposed_change="Raise lexical threshold calibration using replay metrics.",
        expected_benefit="Lower context cost without reducing useful retrieval.",
        risk_level=risk_level,
        source_event_ids=["evt_1"],
    )


def make_evaluation(hypothesis_id: str, *, tests_passed: bool = True) -> EvaluationResult:
    return EvaluationResult(
        hypothesis_id=hypothesis_id,
        evaluator="pytest",
        metrics=[
            EvaluationMetric(name="accuracy", value=0.9, passed=True, weight=2.0),
            EvaluationMetric(name="latency", value=0.8, passed=True, weight=1.0),
        ],
        tests_passed=tests_passed,
    )


def test_improvement_hypothesis_requires_lineage() -> None:
    with pytest.raises(ValueError, match="lineage"):
        ImprovementHypothesis(
            title="No lineage",
            target_module="Router",
            rationale="Missing evidence.",
            proposed_change="Change threshold.",
            expected_benefit="Maybe faster.",
        )


def test_selector_promotes_good_low_risk_candidate_with_rollback() -> None:
    selector = EvolutionSelector(min_score=0.75)
    hypothesis = make_hypothesis()
    evaluation = make_evaluation(hypothesis.hypothesis_id)

    decision = selector.decide(
        hypothesis,
        evaluation,
        rollback_plan="Restore previous retrieval threshold.",
    )

    assert decision.decision == PromotionDecisionType.PROMOTE
    assert decision.score == pytest.approx(0.8666666667)
    assert decision.rollback_plan == "Restore previous retrieval threshold."


def test_selector_rejects_regressions() -> None:
    selector = EvolutionSelector()
    hypothesis = make_hypothesis()
    evaluation = make_evaluation(hypothesis.hypothesis_id)
    evaluation.regressions.append("test_retrieval_router failed")

    decision = selector.decide(
        hypothesis,
        evaluation,
        rollback_plan="Restore previous code.",
    )

    assert decision.decision == PromotionDecisionType.REJECT
    assert decision.reason == "regressions_detected"


def test_selector_rejects_failed_tests() -> None:
    selector = EvolutionSelector()
    hypothesis = make_hypothesis()
    evaluation = make_evaluation(hypothesis.hypothesis_id, tests_passed=False)

    decision = selector.decide(
        hypothesis,
        evaluation,
        rollback_plan="Restore previous code.",
    )

    assert decision.decision == PromotionDecisionType.REJECT
    assert decision.reason == "tests_failed"


def test_selector_requires_rollback_plan_for_promotion() -> None:
    selector = EvolutionSelector(min_score=0.75)
    hypothesis = make_hypothesis()
    evaluation = make_evaluation(hypothesis.hypothesis_id)

    decision = selector.decide(hypothesis, evaluation)

    assert decision.decision == PromotionDecisionType.NEEDS_MORE_EVIDENCE
    assert decision.reason == "missing_rollback_plan"


def test_selector_quarantines_critical_risk_candidate() -> None:
    selector = EvolutionSelector(allow_high_risk=True)
    hypothesis = make_hypothesis(risk_level=RiskLevel.CRITICAL)
    evaluation = make_evaluation(hypothesis.hypothesis_id)

    decision = selector.decide(
        hypothesis,
        evaluation,
        rollback_plan="Restore previous state.",
    )

    assert decision.decision == PromotionDecisionType.QUARANTINE
    assert decision.reason == "critical_risk_requires_manual_review"


def test_evaluation_metric_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        EvaluationMetric(name="loss", value=float("nan"), passed=True)
    with pytest.raises(ValueError):
        EvaluationMetric(name="loss", value=float("inf"), passed=True)

    metric = EvaluationMetric(name="loss", value=0.42, passed=True)
    assert metric.value == pytest.approx(0.42)
