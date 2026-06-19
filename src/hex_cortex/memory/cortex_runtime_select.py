from __future__ import annotations


def select_cortex_runtime_target(
    health_records: list[dict[str, object]],
    *,
    preferred_platform: str | None = None,
    required_model: str | None = None,
) -> dict[str, object]:
    ranked = []
    for record in health_records:
        if record.get("healthy") is not True:
            continue
        models = record.get("models")
        model_names = [str(item) for item in models] if isinstance(models, list) else []
        if required_model is not None and required_model not in model_names:
            continue
        priority = _number(record.get("priority"), default=50.0)
        latency_ms = _number(record.get("latency_ms"), default=2000.0)
        platform = record.get("platform")
        loaded_count = int(_number(record.get("loaded_model_count"), default=0.0))
        score = min(max(priority, 0.0), 100.0) / 100.0 * 0.45
        score += max(0.0, 1.0 - min(latency_ms, 2000.0) / 2000.0) * 0.2
        if preferred_platform is not None and platform == preferred_platform:
            score += 0.2
        if loaded_count > 0:
            score += 0.15
        if required_model is not None:
            score += 0.25
        ranked.append(
            {
                "target_id": record.get("target_id"),
                "kind": record.get("kind"),
                "platform": platform,
                "latency_ms": latency_ms,
                "priority": priority,
                "model_count": len(model_names),
                "loaded_model_count": loaded_count,
                "required_model_available": (
                    required_model in model_names if required_model is not None else None
                ),
                "selection_score": round(score, 6),
            }
        )
    ranked.sort(
        key=lambda item: (
            -float(item["selection_score"]),
            str(item.get("target_id")),
        )
    )
    selected = ranked[0] if ranked else None
    return {
        "selection_type": "cortex_runtime_target",
        "selection_allowed": selected is not None,
        "preferred_platform": preferred_platform,
        "required_model": required_model,
        "candidate_count": len(ranked),
        "ranked_targets": ranked,
        "selected_target": selected,
        "next_action": (
            "run_selected_runtime"
            if selected is not None
            else "repair_or_install_runtime"
        ),
        "blockers": [] if selected is not None else ["no_healthy_compatible_runtime"],
    }


def build_cortex_runtime_benchmark_plan(
    *,
    model: str,
    prompt_set_id: str = "runtime-smoke-v1",
    warmup_runs: int = 1,
    measured_runs: int = 3,
) -> dict[str, object]:
    if not model.strip():
        raise ValueError("model must be non-empty")
    if warmup_runs < 0 or warmup_runs > 5:
        raise ValueError("warmup_runs must be in [0, 5]")
    if measured_runs < 1 or measured_runs > 20:
        raise ValueError("measured_runs must be in [1, 20]")
    return {
        "plan_type": "cortex_runtime_benchmark",
        "model": model,
        "prompt_set_id": prompt_set_id,
        "warmup_runs": warmup_runs,
        "measured_runs": measured_runs,
        "metrics": [
            "availability",
            "time_to_first_token_ms",
            "tokens_per_second",
            "total_latency_ms",
            "peak_memory_mb",
            "response_schema_valid",
            "task_score",
        ],
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "execution_performed": False,
        "next_action": "execute_benchmark_with_operator_or_trusted_plan",
    }


def _number(value: object, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default
