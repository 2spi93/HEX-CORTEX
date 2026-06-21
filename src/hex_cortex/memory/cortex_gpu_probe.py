"""GPU probe — assemble real accelerator metrics into a governor snapshot.

The governor is a brain with no eyes: it decides from a snapshot but reads
nothing itself. This is the wiring. On this Windows + AMD host the usable
signals are Ollama's /api/ps (authoritative VRAM per resident model) and the
Windows performance counter \\GPU Adapter Memory\\Dedicated Usage (total VRAM in
use, including non-Ollama load). rocm-smi is absent, so temperature is optional;
VRAM exhaustion — the "screen turns all green" TDR crash — is the signal that
matters, and VRAM we can measure.

This module is pure: a thin sensor layer (PowerShell) gathers the raw numbers
and hands them here; we assemble the snapshot the governor expects. Total VRAM
defaults to 12288 MB because the driver misreports it as 4 GB (32-bit field).
"""

from __future__ import annotations

_RX6700XT_VRAM_MB = 12288.0
_BIG_MODEL_THRESHOLD_MB = 7000.0


def build_snapshot_from_sources(
    ollama_ps: dict[str, object],
    *,
    vram_total_mb: float = _RX6700XT_VRAM_MB,
    dedicated_usage_mb: float | None = None,
    gpu_utilization_pct: float = 0.0,
    temperature_c: float = 0.0,
    queue_depth: int = 0,
    recent_latency_ms: float = 0.0,
    recent_oom_count: int = 0,
    in_cooldown: bool = False,
    interactive_task_active: bool = False,
    big_model_threshold_mb: float = _BIG_MODEL_THRESHOLD_MB,
) -> dict[str, object]:
    """Assemble a governor snapshot from Ollama /api/ps + measured VRAM usage."""
    if vram_total_mb <= 0.0:
        raise ValueError("vram_total_mb must be positive")
    models = _models(ollama_ps)
    ollama_vram_mb = sum(_size_vram_mb(model) for model in models)
    big_model_loaded = any(_size_vram_mb(model) >= big_model_threshold_mb for model in models)

    # Trust the larger of measured dedicated usage and Ollama's own attribution:
    # the counter captures non-Ollama load too, but may lag a just-loaded model.
    measured = float(dedicated_usage_mb) if dedicated_usage_mb is not None else 0.0
    vram_used_mb = min(vram_total_mb, max(measured, ollama_vram_mb))

    return {
        "vram_total_mb": vram_total_mb,
        "vram_used_mb": vram_used_mb,
        "temperature_c": float(temperature_c),
        "gpu_utilization_pct": float(gpu_utilization_pct),
        "loaded_model_count": len(models),
        "big_model_loaded": big_model_loaded,
        "queue_depth": int(queue_depth),
        "recent_latency_ms": float(recent_latency_ms),
        "recent_oom_count": int(recent_oom_count),
        "in_cooldown": bool(in_cooldown),
        "interactive_task_active": bool(interactive_task_active),
        "ollama_attributed_vram_mb": round(ollama_vram_mb, 1),
        "probe_source": "ollama_ps+windows_dedicated_usage",
    }


def _models(ollama_ps: dict[str, object]) -> list[dict[str, object]]:
    if not isinstance(ollama_ps, dict):
        raise ValueError("ollama_ps must be a dict")
    models = ollama_ps.get("models", [])
    if models is None:
        return []
    if not isinstance(models, list):
        raise ValueError("ollama_ps.models must be a list")
    return [m for m in models if isinstance(m, dict)]


def _size_vram_mb(model: dict[str, object]) -> float:
    raw = model.get("size_vram", 0)
    if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < 0:
        return 0.0
    return raw / (1024.0 * 1024.0)
