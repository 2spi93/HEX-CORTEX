"""Confidence calibration — know when a model bluffs.

Models announce confidence; reality grades it. This module compares claimed
confidence against actual outcomes, bucket by bucket, and produces a
correction map: if a model's "0.9 confident" answers are right only 60% of
the time, the kernel should treat its 0.9 as 0.6. Small models bluff the
most, which makes this the cheapest intelligence upgrade in the kernel.

Buckets with too little evidence shrink toward the claimed value instead of
overriding it — calibration must itself stay calibrated. Pure and cold.
"""

from __future__ import annotations

from math import isfinite

_MAP_TYPE = "cortex_confidence_calibration_map_v1"
_MIN_BUCKET_SAMPLES = 5


def build_calibration_map(
    observations: list[dict[str, object]],
    *,
    bucket_count: int = 5,
) -> dict[str, object]:
    """Build a per-bucket calibration map from (claimed, success) observations.

    Also reports the expected calibration error (ECE): the trial-weighted mean
    gap between claimed confidence and observed success rate.
    """

    if not 2 <= bucket_count <= 20:
        raise ValueError("bucket_count must be between 2 and 20")

    totals = [[0, 0.0, 0.0] for _ in range(bucket_count)]  # trials, successes, claimed_sum
    for row in observations:
        claimed = row.get("claimed_confidence")
        success = row.get("success")
        if not isinstance(claimed, (int, float)) or isinstance(claimed, bool):
            raise ValueError("claimed_confidence must be a number")
        claimed = float(claimed)
        if not isfinite(claimed) or not 0.0 <= claimed <= 1.0:
            raise ValueError("claimed_confidence must be finite within [0, 1]")
        if not isinstance(success, bool):
            raise ValueError("success must be a boolean")
        index = min(int(claimed * bucket_count), bucket_count - 1)
        totals[index][0] += 1
        totals[index][1] += 1.0 if success else 0.0
        totals[index][2] += claimed

    buckets = []
    weighted_gap = 0.0
    total_trials = sum(row[0] for row in totals)
    for index, (trials, successes, claimed_sum) in enumerate(totals):
        low = index / bucket_count
        high = (index + 1) / bucket_count
        observed = round(successes / trials, 10) if trials else None
        mean_claimed = round(claimed_sum / trials, 10) if trials else None
        if trials and total_trials:
            weighted_gap += (trials / total_trials) * abs(mean_claimed - observed)
        buckets.append(
            {
                "bucket": index,
                "claimed_range": [round(low, 10), round(high, 10)],
                "trials": trials,
                "observed_success_rate": observed,
                "mean_claimed_confidence": mean_claimed,
                "reliable": trials >= _MIN_BUCKET_SAMPLES,
            }
        )

    return {
        "map_type": _MAP_TYPE,
        "bucket_count": bucket_count,
        "buckets": buckets,
        "total_observations": total_trials,
        "expected_calibration_error": round(weighted_gap, 10) if total_trials else None,
        "model_call_performed": False,
        "next_action": "apply_map_via_calibrate_confidence",
    }


def calibrate_confidence(
    claimed_confidence: float,
    calibration_map: dict[str, object],
) -> dict[str, object]:
    """Correct one claimed confidence using the calibration map.

    Reliable buckets replace the claim with the observed rate; thin buckets
    blend proportionally to the evidence they hold, so the correction never
    outruns the data behind it.
    """

    if not isinstance(claimed_confidence, (int, float)) or isinstance(claimed_confidence, bool):
        raise ValueError("claimed_confidence must be a number")
    claimed = float(claimed_confidence)
    if not isfinite(claimed) or not 0.0 <= claimed <= 1.0:
        raise ValueError("claimed_confidence must be finite within [0, 1]")
    if calibration_map.get("map_type") != _MAP_TYPE:
        raise ValueError("calibration_map has wrong type")

    bucket_count = int(calibration_map["bucket_count"])
    index = min(int(claimed * bucket_count), bucket_count - 1)
    bucket = calibration_map["buckets"][index]  # type: ignore[index]

    trials = int(bucket["trials"])
    observed = bucket["observed_success_rate"]
    if trials == 0 or observed is None:
        corrected = claimed
        basis = "no_evidence_claim_kept"
    else:
        weight = min(trials / _MIN_BUCKET_SAMPLES, 1.0)
        corrected = weight * float(observed) + (1.0 - weight) * claimed
        basis = "observed_rate" if weight == 1.0 else "partial_evidence_blend"

    return {
        "claimed_confidence": claimed,
        "corrected_confidence": round(corrected, 10),
        "bucket": index,
        "bucket_trials": trials,
        "correction_basis": basis,
        "bluff_detected": trials >= _MIN_BUCKET_SAMPLES
        and observed is not None
        and claimed - float(observed) >= 0.2,
    }
