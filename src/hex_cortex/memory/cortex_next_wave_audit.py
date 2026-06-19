from __future__ import annotations

from pathlib import Path


def audit_next_wave(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    memory_root = root / "src" / "hex_cortex" / "memory"
    files = {
        "media_runtime_v1": memory_root / "cortex_media_runtime.py",
        "latent_world_model_lab_v1": memory_root / "cortex_latent_lab.py",
        "latent_experiment_receipts_v1": memory_root / "cortex_latent_experiment.py",
        "world_model_training_evaluation_v1": memory_root / "cortex_world_model_eval.py",
        "next_wave_cli": memory_root / "cortex_next_wave_cli.py",
    }
    facts = {name: path.is_file() for name, path in files.items()}
    blockers = [f"{name}_missing" for name, available in facts.items() if not available]
    architecture_ready = not blockers
    return {
        "audit_type": "next_wave_media_world_model_v1",
        "project_root": str(root),
        "architecture_ready": architecture_ready,
        "operational_ready": False,
        "runtime_facts": facts,
        "blockers": blockers,
        "external_runtime_requirements": {
            "media_runtime": "ComfyUI localhost endpoint",
            "latent_encoder": "frozen external encoder or deterministic test encoder",
            "run_environment": "bounded local or server run environment",
        },
        "network_probe_performed": False,
        "process_probe_performed": False,
        "model_run_performed": False,
        "next_action": (
            "validate_next_wave_tests"
            if architecture_ready
            else "repair_next_wave_files"
        ),
    }
