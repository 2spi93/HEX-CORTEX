"""Read-only, conservative inventory of actual local HEX-CORTEX capabilities.

Presence of implementation/dependencies is not proof that hardware, DINO,
ASR, TTS, latent weights or independent scientific validation are ready.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections.abc import Sequence

from hex_cortex.memory.cortex_sensor_providers import list_cortex_sensor_providers


def probe_universal_capabilities() -> dict[str, object]:
    deps = {
        name: importlib.util.find_spec(name) is not None
        for name in ("torch", "transformers", "PIL", "numpy", "soundfile")
    }
    declared = {
        str(record["capability_id"])
        for record in list_cortex_sensor_providers()
    }
    capabilities: dict[str, dict[str, object]] = {
        "math_exact": {
            "status": "implemented_exact_cpu_cell",
            "requirements": ["explicit_math_approval"],
            "real_world_validated": False,
        },
        "physics_classical": {
            "status": "implemented_idealized_cpu_cell",
            "requirements": ["typed_units", "explicit_science_approval"],
            "real_world_validated": False,
        },
        "chemistry_stoichiometry": {
            "status": "implemented_idealized_cpu_cell",
            "requirements": ["typed_composition", "explicit_science_approval"],
            "real_world_validated": False,
        },
        "world_simulation": {
            "status": "implemented_idealized_constant_acceleration_cpu",
            "requirements": ["approved_operator_state", "approved_simulation"],
            "real_world_validated": False,
        },
        "world_latent_dinov2": {
            "status": "dependencies_detected_not_model_attested"
            if deps["torch"] and deps["transformers"]
            else "missing_optional_dependencies",
            "requirements": [
                "local_encoder_weights",
                "trained_world_model_checkpoint",
                "environment_specific_validation",
            ],
            "real_world_validated": False,
        },
        "vision": {
            "status": "local_png_metadata_only",
            "requirements": ["explicit_file_approval"],
            "object_recognition_performed": False,
        },
        "voice_input": {
            "status": "wav_metadata_and_operator_transcripts_only",
            "requirements": ["explicit_local_file_or_text"],
            "asr_transcription_operational": False,
        },
        "voice_output": {
            "status": "provider_contract_only",
            "requirements": ["approved_tts_runtime"],
            "tts_synthesis_operational": False,
        },
        "coding": {
            "status": "static_ast_and_optional_local_review",
            "requirements": ["operator_approved_file", "approved_local_model"],
            "patch_execution_authorized": False,
        },
        "robotics_objects": {
            "status": "hardware_adapter_registered_simulation_only",
            "requirements": ["external_independent_device_safety_gateway"],
            "physical_actuation_authorized": False,
        },
    }
    return {
        "status": "local_capability_inventory",
        "capabilities": capabilities,
        "optional_dependencies_detected": deps,
        "sensor_capabilities_declared": sorted(declared),
        "cpu_only_paths_available": True,
        "gpu_required_for_this_probe": False,
        "onnx_or_torch_inference_executed": False,
        "hardware_device_probed": False,
        "ollama_model_called": False,
        "local_files_mutated": False,
        "real_world_safety_certified": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect CPU scientific, vision, voice, world and hardware readiness."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "dependencies_probed": False,
            "files_mutated": False, "hardware_polled": False,
            "model_called": False,
        }, sort_keys=True))
        return 0
    print(json.dumps(probe_universal_capabilities(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
