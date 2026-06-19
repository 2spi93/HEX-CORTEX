from __future__ import annotations


def list_world_model_metrics() -> list[dict[str, object]]:
    return [
        {"metric": "latent_mse_h1", "direction": "lower", "critical": True},
        {"metric": "latent_mse_h4", "direction": "lower", "critical": True},
        {"metric": "latent_mse_h16", "direction": "lower", "critical": True},
        {"metric": "rollout_divergence", "direction": "lower", "critical": True},
        {"metric": "uncertainty_ece", "direction": "lower", "critical": True},
        {"metric": "planning_success_rate", "direction": "higher", "critical": True},
        {"metric": "goal_reach_rate", "direction": "higher", "critical": True},
        {"metric": "ood_detection_auc", "direction": "higher", "critical": False},
        {"metric": "latency_ms", "direction": "lower", "critical": False},
        {"metric": "vram_mb", "direction": "lower", "critical": False},
        {"metric": "reproducibility_delta", "direction": "lower", "critical": True},
    ]
