"""Typed records for controlled self-improvement in HEX-CORTEX."""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class ImprovementStatus(StrEnum):
    """Lifecycle state of an improvement hypothesis."""

    PROPOSED = "proposed"
    EVALUATING = "evaluating"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


class RiskLevel(StrEnum):
    """Risk class for an improvement candidate."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PromotionDecisionType(StrEnum):
    """Promotion gate decision."""

    PROMOTE = "promote"
    REJECT = "reject"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    QUARANTINE = "quarantine"


class SkillStatus(StrEnum):
    """Skill lifecycle state."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ARCHIVED = "archived"


class ImprovementHypothesis(BaseModel):
    """A proposed way for HEX-CORTEX to improve.

    v0.1 hypotheses are records only. They do not execute code.
    """

    hypothesis_id: str = Field(default_factory=lambda: f"hyp_improve_{uuid4().hex}")
    title: str
    target_module: str
    rationale: str
    proposed_change: str
    expected_benefit: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: ImprovementStatus = ImprovementStatus.PROPOSED
    source_event_ids: list[str] = Field(default_factory=list)
    source_rule_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "title",
        "target_module",
        "rationale",
        "proposed_change",
        "expected_benefit",
    )
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("improvement hypothesis text fields must not be empty")
        return value

    @model_validator(mode="after")
    def hypothesis_must_have_lineage(self) -> ImprovementHypothesis:
        if not self.source_event_ids and not self.source_rule_ids:
            raise ValueError("improvement hypotheses require event or rule lineage")
        return self


class EvaluationMetric(BaseModel):
    """One evaluation metric for an improvement hypothesis."""

    name: str
    value: float = Field(allow_inf_nan=False)
    passed: bool
    weight: float = Field(default=1.0, ge=0.0, le=10.0)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("metric name must not be empty")
        return value


class EvaluationResult(BaseModel):
    """Evaluation evidence for an improvement hypothesis."""

    evaluation_id: str = Field(default_factory=lambda: f"eval_{uuid4().hex}")
    hypothesis_id: str
    evaluator: str
    metrics: list[EvaluationMetric] = Field(default_factory=list)
    tests_passed: bool = False
    regressions: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("hypothesis_id", "evaluator")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evaluation text fields must not be empty")
        return value


class PromotionDecision(BaseModel):
    """Decision made by the promotion gate."""

    decision_id: str = Field(default_factory=lambda: f"promo_{uuid4().hex}")
    hypothesis_id: str
    evaluation_id: str
    decision: PromotionDecisionType
    reason: str
    score: float = Field(ge=0.0, le=1.0)
    rollback_plan: str | None = None

    @field_validator("hypothesis_id", "evaluation_id", "reason")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("promotion decision text fields must not be empty")
        return value

    @model_validator(mode="after")
    def promoted_changes_need_rollback_plan(self) -> PromotionDecision:
        is_promotion = self.decision == PromotionDecisionType.PROMOTE
        has_rollback = bool((self.rollback_plan or "").strip())
        if is_promotion and not has_rollback:
            raise ValueError("promoted changes require a rollback plan")
        return self


class SkillRecord(BaseModel):
    """A reusable workflow or capability learned by HEX-CORTEX."""

    skill_id: str = Field(default_factory=lambda: f"skill_{uuid4().hex}")
    name: str
    description: str
    trigger_tags: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    source_hypothesis_ids: list[str] = Field(default_factory=list)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: SkillStatus = SkillStatus.CANDIDATE

    @field_validator("name", "description")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("skill text fields must not be empty")
        return value


class CellHealth(BaseModel):
    """Operational health and trust score for a cognitive cell."""

    cell_id: str
    trust_score: float = Field(default=0.75, ge=0.0, le=1.0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    quarantine: bool = False
    requires_double_check: bool = False
    last_issue: str | None = None

    @field_validator("cell_id")
    @classmethod
    def cell_id_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("cell_id must not be empty")
        return value
