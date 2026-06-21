"""GPU resource governor — admission control over a local accelerator.

The recent overload showed the missing organ is not more intelligence but a
*resource governor*: the GPU must stop being treated as infinite. This is the
pure decision core. Given a resource snapshot and a model request it returns an
admission decision — admit / queue / downgrade / defer / reject — enforcing the
operator's policy for a 12 GB RX 6700 XT:

    - 7B (small) by default; 14B (large) only with real VRAM headroom
    - one large model resident at a time
    - benchmarks yield to interactive tasks
    - OOM or cooldown forces a fall back to small
    - clean stop (defer + unload) when VRAM is critical or the card is hot

It performs no probing itself — a thin adapter fills the snapshot (Ollama
/api/ps for resident models + VRAM, rocm-smi for load/temperature). Keeping the
policy pure makes the whole thing testable in cold mode with no GPU present.
"""

from __future__ import annotations

_DECISION_TYPE = "cortex_gpu_governor_decision_v1"
_TIERS = {"small", "large"}
_NEXT_ACTION = {
    "admit": "dispatch_model",
    "downgrade": "dispatch_small_model",
    "queue": "wait_in_queue",
    "defer": "retry_after_cooldown",
    "reject": "reject_request",
}


def default_governor_policy() -> dict[str, object]:
    """Conservative defaults tuned for a 12 GB RX 6700 XT."""
    return {
        "vram_critical_fraction": 0.92,
        "vram_high_fraction": 0.80,
        "temperature_critical_c": 85.0,
        "max_loaded_models": 2,
        "max_queue_depth": 8,
        "tier_vram_mb": {"small": 5000.0, "large": 9800.0},
    }


def decide_gpu_admission(
    snapshot: dict[str, object],
    request: dict[str, object],
    *,
    policy: dict[str, object] | None = None,
) -> dict[str, object]:
    """Map a resource snapshot + a model request to an admission decision."""
    pol = _merge_policy(policy)
    snap = _validate_snapshot(snapshot)
    tier, is_benchmark, estimated_mb = _validate_request(request, pol)

    total = snap["vram_total_mb"]
    used = snap["vram_used_mb"]
    free = max(0.0, total - used)
    used_fraction = used / total if total > 0 else 1.0

    tier_vram = pol["tier_vram_mb"]
    small_mb = float(tier_vram["small"])
    critical = used_fraction >= float(pol["vram_critical_fraction"])
    high = used_fraction >= float(pol["vram_high_fraction"])

    def decide(action: str, granted: str | None, reasons: list[str], *, unload: bool = False) -> dict[str, object]:
        return {
            "governor_type": _DECISION_TYPE,
            "action": action,
            "granted_tier": granted,
            "requested_tier": tier,
            "is_benchmark": is_benchmark,
            "recommend_unload_idle": unload,
            "vram_used_fraction": round(used_fraction, 4),
            "vram_free_mb": round(free, 1),
            "reasons": reasons,
            "fail_closed": action in {"defer", "reject"},
            "next_action": _NEXT_ACTION[action],
        }

    # 1. Hard backpressure: a saturated queue is rejected outright.
    if snap["queue_depth"] >= int(pol["max_queue_depth"]):
        return decide("reject", None, ["request_queue_saturated"], unload=critical)

    # 2. Thermal protection takes precedence over everything that runs work.
    if snap["temperature_c"] >= float(pol["temperature_critical_c"]):
        return decide("defer", None, ["temperature_critical_cooldown"], unload=True)

    # 3. OOM history or an active cooldown forces small, never large.
    if snap["recent_oom_count"] > 0 or snap["in_cooldown"]:
        if critical or free < small_mb:
            return decide("defer", None, ["cooldown_vram_insufficient"], unload=True)
        if tier == "large":
            return decide("downgrade", "small", ["oom_or_cooldown_forces_small"])
        return decide("admit", "small", ["cooldown_small_only"])

    # 4. Critical VRAM with no cooldown yet: clean stop and reclaim memory.
    if critical:
        return decide("defer", None, ["vram_critical_clean_stop"], unload=True)

    # 5. Benchmarks must yield to interactive work.
    if is_benchmark and snap["interactive_task_active"]:
        return decide("defer", None, ["benchmark_yields_to_interactive"])

    # 6. Large model admission: one at a time, with genuine headroom.
    if tier == "large":
        if snap["big_model_loaded"]:
            return decide("queue", None, ["one_big_model_at_a_time"])
        if high or estimated_mb > free:
            if free >= small_mb:
                return decide("downgrade", "small", ["insufficient_headroom_for_large"])
            return decide("defer", None, ["insufficient_vram_for_any_model"], unload=True)
        if snap["loaded_model_count"] >= int(pol["max_loaded_models"]):
            return decide("queue", None, ["loaded_model_cap_reached"])
        return decide("admit", "large", ["large_admitted_with_headroom"])

    # 7. Small model admission.
    if estimated_mb > free:
        return decide("defer", None, ["insufficient_vram_for_small"], unload=True)
    if snap["loaded_model_count"] >= int(pol["max_loaded_models"]):
        return decide("queue", None, ["loaded_model_cap_reached"])
    return decide("admit", "small", ["small_admitted"])


def _merge_policy(policy: dict[str, object] | None) -> dict[str, object]:
    merged = default_governor_policy()
    if policy:
        for key, value in policy.items():
            if key not in merged:
                raise ValueError(f"unknown governor policy key: {key}")
            merged[key] = value
    return merged


def _validate_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a dict")
    total = _number(snapshot, "vram_total_mb", minimum=1.0)
    used = _number(snapshot, "vram_used_mb", minimum=0.0)
    if used > total:
        raise ValueError("vram_used_mb cannot exceed vram_total_mb")
    return {
        "vram_total_mb": total,
        "vram_used_mb": used,
        "temperature_c": _number(snapshot, "temperature_c", minimum=0.0, default=0.0),
        "gpu_utilization_pct": _number(snapshot, "gpu_utilization_pct", minimum=0.0, default=0.0),
        "loaded_model_count": int(_number(snapshot, "loaded_model_count", minimum=0.0, default=0.0)),
        "big_model_loaded": bool(snapshot.get("big_model_loaded", False)),
        "queue_depth": int(_number(snapshot, "queue_depth", minimum=0.0, default=0.0)),
        "recent_latency_ms": _number(snapshot, "recent_latency_ms", minimum=0.0, default=0.0),
        "recent_oom_count": int(_number(snapshot, "recent_oom_count", minimum=0.0, default=0.0)),
        "in_cooldown": bool(snapshot.get("in_cooldown", False)),
        "interactive_task_active": bool(snapshot.get("interactive_task_active", False)),
    }


def _validate_request(
    request: dict[str, object],
    policy: dict[str, object],
) -> tuple[str, bool, float]:
    if not isinstance(request, dict):
        raise ValueError("request must be a dict")
    tier = request.get("tier")
    if tier not in _TIERS:
        raise ValueError("request tier must be 'small' or 'large'")
    is_benchmark = bool(request.get("is_benchmark", False))
    estimated = request.get("estimated_vram_mb")
    if estimated is None:
        estimated = float(policy["tier_vram_mb"][tier])
    elif not isinstance(estimated, int | float) or estimated < 0.0:
        raise ValueError("estimated_vram_mb must be a non-negative number")
    return str(tier), is_benchmark, float(estimated)


def _number(
    source: dict[str, object],
    key: str,
    *,
    minimum: float,
    default: float | None = None,
) -> float:
    if key not in source:
        if default is None:
            raise ValueError(f"snapshot missing required field: {key}")
        return default
    value = source[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"snapshot field {key} must be a number")
    if value < minimum:
        raise ValueError(f"snapshot field {key} must be >= {minimum}")
    return float(value)
