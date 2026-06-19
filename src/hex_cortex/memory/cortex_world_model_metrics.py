from __future__ import annotations

import hashlib
import json


def list_world_model_metrics() -> list[dict[str, object]]:
    return [
        {"metric": "latent_mse_h1", "direction": "lower", "critical": True, "weight": 1.0},
        {"metric": "latent_mse_h4", "direction": "lower", "critical": True, "weight": 1.0},
        {"metric": "latent_mse_h16", "direction": "lower", "critical": True, "weight": 1.25},
        {"metric": "rollout_divergence", "direction": "lower", "critical": True, "weight": 1.25},
        {"metric": "uncertainty_ece", "direction": "lower", "critical": True, "weight": 1.0},
        {"metric": "planning_success_rate", "direction": "higher", "critical": True, "weight": 2.0},
        {"metric": "goal_reach_rate", "direction": "higher", "critical": True, "weight": 1.5},
        {"metric": "ood_detection_auc", "direction": "higher", "critical": False, "weight": 1.0},
        {"metric": "latency_ms", "direction": "lower", "critical": False, "weight": 0.5},
        {"metric": "vram_mb", "direction": "lower", "critical": False, "weight": 0.25},
        {"metric": "reproducibility_delta", "direction": "lower", "critical": True, "weight": 0.75},
    ]


def compare_world_model_metrics(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    critical_tolerance: float = 0.02,
    required_gain: float = 0.01,
) -> dict[str, object]:
    catalog = list_world_model_metrics()
    required = {str(row["metric"]) for row in catalog}
    missing = sorted(required.difference(baseline) | required.difference(candidate))
    if missing:
        return {
            "comparison_complete": False,
            "accepted_for_review": False,
            "missing_metrics": missing,
            "blockers": ["required_metrics_missing"],
        }
    rows = []
    weighted = 0.0
    weight_total = 0.0
    critical_regressions = []
    for policy in catalog:
        metric = str(policy["metric"])
        base = float(baseline[metric])
        value = float(candidate[metric])
        denominator = max(abs(base), 1e-9)
        gain = (base - value) / denominator
        if policy["direction"] == "higher":
            gain = (value - base) / denominator
        weight = float(policy["weight"])
        weighted += gain * weight
        weight_total += weight
        if policy["critical"] is True and gain < -critical_tolerance:
            critical_regressions.append(metric)
        rows.append({
            "metric": metric,
            "baseline": base,
            "candidate": value,
            "relative_gain": round(gain, 8),
            "critical": policy["critical"],
        })
    score = weighted / weight_total
    blockers = []
    if critical_regressions:
        blockers.append("critical_metric_regression")
    if score < required_gain:
        blockers.append("weighted_gain_below_threshold")
    stable = {
        "rows": rows,
        "score": round(score, 8),
        "critical_regressions": critical_regressions,
        "blockers": blockers,
    }
    return {
        "comparison_complete": True,
        "accepted_for_review": not blockers,
        "manual_review_required": True,
        "automatic_deployment_allowed": False,
        "weighted_gain": round(score, 8),
        "critical_regressions": critical_regressions,
        "metric_rows": rows,
        "blockers": blockers,
        "comparison_hash": hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest(),
    }
