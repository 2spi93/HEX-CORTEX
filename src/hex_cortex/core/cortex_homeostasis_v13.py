"""Homeostatic feedback: bio-inspired *advisory* safety controller.

The organism analogy is limited: software cell trust and health are
engineering measurements, not biological physiology. This module does
not mutate the registry, change policies, enable actuators or run tools.
Hysteresis prevents rapid oscillation between ready and quarantined.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, Field


class HealthState(StrEnum):
    STABLE = "stable"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RECOVERY_REVIEW = "recovery_review"


class HealthObservation(BaseModel):
    cell_id: str = Field(min_length=1, max_length=128)
    prior_state: HealthState = HealthState.STABLE
    error_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    latency_ratio: float = Field(ge=0, le=10, allow_inf_nan=False)
    consecutive_failures: int = Field(ge=0, le=1_000_000)
    verified_recovery_samples: int = Field(default=0, ge=0, le=1_000_000)
    spine_integrity_ok: bool
    independently_verified: bool = False


def homeostatic_review(observation: HealthObservation) -> dict[str, object]:
    """Select safe action using integrity precedence and bounded hysteresis."""
    corrupted = not observation.spine_integrity_ok
    failed = observation.consecutive_failures >= 3 or observation.error_rate >= 0.50
    lagging = observation.latency_ratio > 1.0
    recovering = (
        observation.prior_state in (HealthState.QUARANTINED, HealthState.RECOVERY_REVIEW)
        and observation.verified_recovery_samples >= 5
        and observation.independently_verified
        and observation.consecutive_failures == 0
        and observation.error_rate <= 0.05
        and observation.latency_ratio <= 0.8
        and not corrupted
    )
    if corrupted or failed:
        next_state = HealthState.QUARANTINED
        reason = "integrity_failed" if corrupted else "sustained_error_pressure"
    elif observation.prior_state in (HealthState.QUARANTINED, HealthState.RECOVERY_REVIEW):
        next_state = HealthState.RECOVERY_REVIEW if recovering else HealthState.QUARANTINED
        reason = "requires_operator_reinstatement" if recovering else "recovering_not_proven"
    elif lagging or observation.error_rate >= 0.20 or observation.consecutive_failures > 0:
        next_state = HealthState.DEGRADED
        reason = "negative_feedback_degradation"
    else:
        next_state = HealthState.STABLE
        reason = "within_observed_limits"

    receipt = {
        "receipt_type": "cortex_homeostatic_feedback_v13",
        "cell_id_sha256": hashlib.sha256(observation.cell_id.encode()).hexdigest(),
        "previous_state": observation.prior_state.value,
        "advisory_state": next_state.value,
        "reason": reason,
        "may_execute_automatically": False,
        "may_reinstate_automatically": False,
        "physical_actuation_allowed": False,
        "registry_mutated": False,
        "policy_mutated": False,
        "independent_verification_required_for_recovery": True,
        "human_review_required": next_state in {
            HealthState.QUARANTINED, HealthState.RECOVERY_REVIEW
        },
        "observed_failure_pressure": failed,
        "observed_latency_pressure": lagging,
        "spine_integrity_verified": not corrupted,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return receipt
