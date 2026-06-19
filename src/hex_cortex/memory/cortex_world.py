from __future__ import annotations


def compute_cortex_world_readiness(
    *,
    multimodal_inputs: float,
    persistent_memory: float,
    predictive_state: float,
    planning_loop: float,
    surprise_detection: float,
    safety_receipts: float,
) -> dict[str, object]:
    values = {
        "multimodal_inputs": multimodal_inputs,
        "persistent_memory": persistent_memory,
        "predictive_state": predictive_state,
        "planning_loop": planning_loop,
        "surprise_detection": surprise_detection,
        "safety_receipts": safety_receipts,
    }
    blockers = [name for name, value in values.items() if value < 0 or value > 1]
    if blockers:
        return {
            "world_type": "cortex_world_readiness",
            "world_allowed": False,
            "world_status": "blocked",
            "blockers": [f"{name}_out_of_range" for name in blockers],
        }
    score = round(
        100
        * (
            0.18 * multimodal_inputs
            + 0.17 * persistent_memory
            + 0.20 * predictive_state
            + 0.17 * planning_loop
            + 0.13 * surprise_detection
            + 0.15 * safety_receipts
        ),
        2,
    )
    status = "ready_candidate" if score >= 80 else "not_ready"
    return {
        "world_type": "cortex_world_readiness",
        "world_allowed": True,
        "world_status": status,
        "score": score,
        "missing_layers": _missing(values),
        "next_action": "world_model_candidate_adapter" if score >= 80 else "fill_world_model_layers",
    }


def _missing(values: dict[str, float]) -> list[str]:
    return [name for name, value in values.items() if value < 0.8]
