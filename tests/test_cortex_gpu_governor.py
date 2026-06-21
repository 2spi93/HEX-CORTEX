import pytest

from hex_cortex.memory.cortex_gpu_governor import decide_gpu_admission
from hex_cortex.memory.cortex_gpu_governor import default_governor_policy


def _snap(**over: object) -> dict[str, object]:
    base = {
        "vram_total_mb": 12000.0,
        "vram_used_mb": 1000.0,
        "temperature_c": 60.0,
        "gpu_utilization_pct": 20.0,
        "loaded_model_count": 0,
        "big_model_loaded": False,
        "queue_depth": 0,
        "recent_latency_ms": 2000.0,
        "recent_oom_count": 0,
        "in_cooldown": False,
        "interactive_task_active": False,
    }
    base.update(over)
    return base


def test_small_admitted_on_idle_card() -> None:
    d = decide_gpu_admission(_snap(), {"tier": "small"})
    assert d["action"] == "admit"
    assert d["granted_tier"] == "small"


def test_large_admitted_with_headroom() -> None:
    d = decide_gpu_admission(_snap(vram_used_mb=1000.0), {"tier": "large"})
    assert d["action"] == "admit"
    assert d["granted_tier"] == "large"


def test_large_queued_when_a_big_model_already_loaded() -> None:
    snap = _snap(vram_used_mb=9800.0, big_model_loaded=True, loaded_model_count=1)
    d = decide_gpu_admission(snap, {"tier": "large"})
    assert d["action"] == "queue"
    assert "one_big_model_at_a_time" in d["reasons"]


def test_large_downgraded_when_no_headroom_but_small_fits() -> None:
    # 7B (4 GB) resident, want 14B: 9800 MB > 8000 MB free -> downgrade to small.
    snap = _snap(vram_used_mb=4000.0, loaded_model_count=1)
    d = decide_gpu_admission(snap, {"tier": "large"})
    assert d["action"] == "downgrade"
    assert d["granted_tier"] == "small"
    assert "insufficient_headroom_for_large" in d["reasons"]


def test_benchmark_yields_to_interactive_task() -> None:
    d = decide_gpu_admission(_snap(interactive_task_active=True), {"tier": "small", "is_benchmark": True})
    assert d["action"] == "defer"
    assert "benchmark_yields_to_interactive" in d["reasons"]


def test_oom_forces_small() -> None:
    d = decide_gpu_admission(_snap(recent_oom_count=1), {"tier": "large"})
    assert d["action"] == "downgrade"
    assert d["granted_tier"] == "small"
    assert "oom_or_cooldown_forces_small" in d["reasons"]


def test_cooldown_admits_small_only() -> None:
    d = decide_gpu_admission(_snap(in_cooldown=True), {"tier": "small"})
    assert d["action"] == "admit"
    assert "cooldown_small_only" in d["reasons"]


def test_vram_critical_defers_and_recommends_unload() -> None:
    d = decide_gpu_admission(_snap(vram_used_mb=11200.0), {"tier": "small"})
    assert d["action"] == "defer"
    assert d["recommend_unload_idle"] is True
    assert "vram_critical_clean_stop" in d["reasons"]
    assert d["fail_closed"] is True


def test_temperature_critical_defers() -> None:
    d = decide_gpu_admission(_snap(temperature_c=88.0), {"tier": "small"})
    assert d["action"] == "defer"
    assert "temperature_critical_cooldown" in d["reasons"]


def test_saturated_queue_rejected() -> None:
    d = decide_gpu_admission(_snap(queue_depth=8), {"tier": "small"})
    assert d["action"] == "reject"
    assert "request_queue_saturated" in d["reasons"]


def test_loaded_model_cap_queues() -> None:
    snap = _snap(vram_used_mb=1000.0, loaded_model_count=2)
    d = decide_gpu_admission(snap, {"tier": "small"})
    assert d["action"] == "queue"
    assert "loaded_model_cap_reached" in d["reasons"]


def test_policy_override_and_unknown_key() -> None:
    d = decide_gpu_admission(
        _snap(temperature_c=80.0),
        {"tier": "small"},
        policy={"temperature_critical_c": 75.0},
    )
    assert d["action"] == "defer"
    with pytest.raises(ValueError):
        decide_gpu_admission(_snap(), {"tier": "small"}, policy={"bogus": 1})


def test_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError):
        decide_gpu_admission({"vram_total_mb": 0.0, "vram_used_mb": 0.0}, {"tier": "small"})
    with pytest.raises(ValueError):
        decide_gpu_admission(_snap(), {"tier": "huge"})
    with pytest.raises(ValueError):
        decide_gpu_admission({"vram_total_mb": 1000.0, "vram_used_mb": 2000.0}, {"tier": "small"})


def test_default_policy_shape() -> None:
    pol = default_governor_policy()
    assert pol["tier_vram_mb"]["large"] > pol["tier_vram_mb"]["small"]
    assert 0.0 < pol["vram_high_fraction"] < pol["vram_critical_fraction"] <= 1.0
