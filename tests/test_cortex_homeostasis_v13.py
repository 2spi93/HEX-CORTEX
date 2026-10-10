"""Bio-inspired homeostatic feedback: quarantine and cautious recovery."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from hex_cortex.core.cortex_homeostasis_v13 import (
    HealthObservation,
    HealthState,
    homeostatic_review,
)


def _obs(**kwargs) -> HealthObservation:
    base = dict(
        cell_id="isolated-scientific-cell",
        error_rate=0.0,
        latency_ratio=0.2,
        consecutive_failures=0,
        spine_integrity_ok=True,
    )
    base.update(kwargs)
    return HealthObservation(**base)


def test_stable_no_promotion_or_actuation():
    report = homeostatic_review(_obs())
    assert report["advisory_state"] == "stable"
    assert report["may_execute_automatically"] is False
    assert report["registry_mutated"] is False
    assert report["physical_actuation_allowed"] is False


@pytest.mark.parametrize("kwargs", [
    {"consecutive_failures": 1},
    {"error_rate": 0.23},
    {"latency_ratio": 1.5},
])
def test_degrade_under_mild_pressure_without_effect(kwargs):
    report = homeostatic_review(_obs(**kwargs))
    assert report["advisory_state"] == "degraded"
    assert report["reason"] == "negative_feedback_degradation"
    assert report["may_execute_automatically"] is False


def test_corrupt_spine_forces_quarantine_even_with_perfect_metrics():
    report = homeostatic_review(_obs(spine_integrity_ok=False))
    assert report["advisory_state"] == "quarantined"
    assert report["reason"] == "integrity_failed"
    assert report["human_review_required"] is True


@pytest.mark.parametrize("kwargs", [
    {"consecutive_failures": 3},
    {"error_rate": 0.5},
    {"error_rate": 0.9, "latency_ratio": 5},
])
def test_sustained_error_quarantine(kwargs):
    assert homeostatic_review(_obs(**kwargs))["advisory_state"] == "quarantined"


def test_recovery_requires_multiple_proofs_and_human_review():
    blocked = homeostatic_review(_obs(
        prior_state=HealthState.QUARANTINED,
        independently_verified=True, verified_recovery_samples=4,
    ))
    assert blocked["advisory_state"] == "quarantined"
    ready = homeostatic_review(_obs(
        prior_state=HealthState.QUARANTINED,
        independently_verified=True, verified_recovery_samples=5,
    ))
    assert ready["advisory_state"] == "recovery_review"
    assert ready["may_reinstate_automatically"] is False
    assert ready["human_review_required"] is True


def test_recovery_requires_independent_evidence_not_just_time():
    report = homeostatic_review(_obs(
        prior_state=HealthState.QUARANTINED,
        independently_verified=False, verified_recovery_samples=100,
    ))
    assert report["advisory_state"] == "quarantined"


@pytest.mark.parametrize("kwargs", [
    {"error_rate": float("nan")},
    {"error_rate": float("inf")},
    {"latency_ratio": float("inf")},
    {"consecutive_failures": -1},
])
def test_nonsensical_metrics_are_refused(kwargs):
    with pytest.raises(ValidationError):
        _obs(**kwargs)


def test_sensitive_cell_id_not_persisted_and_receipt_deterministic():
    obs = _obs(cell_id="secret-broker-key-is-embodied-cell")
    a = homeostatic_review(obs)
    b = homeostatic_review(obs)
    assert a["receipt_sha256"] == b["receipt_sha256"]
    assert "secret-broker-key" not in json.dumps(a)
