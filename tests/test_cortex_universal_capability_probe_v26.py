"""Read-only readiness must never overstate operational ASR or actuation."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_universal_capability_probe_v26 import (
    main, probe_universal_capabilities,
)


def test_capability_probe_distinguishes_stubs_and_ready_cpu_cells() -> None:
    report = probe_universal_capabilities()
    capabilities = report["capabilities"]
    assert report["status"] == "local_capability_inventory"
    assert capabilities["math_exact"]["status"] == "implemented_exact_cpu_cell"
    assert capabilities["vision"]["object_recognition_performed"] is False
    assert capabilities["voice_input"]["asr_transcription_operational"] is False
    assert capabilities["voice_output"]["tts_synthesis_operational"] is False
    assert capabilities["robotics_objects"]["physical_actuation_authorized"] is False
    assert capabilities["coding"]["patch_execution_authorized"] is False
    assert capabilities["world_latent_dinov2"]["real_world_validated"] is False
    assert report["hardware_device_probed"] is False
    assert report["ollama_model_called"] is False


def test_probe_cli_dry_run_and_real_inventory(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["model_called"] is False
    assert main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["local_files_mutated"] is False
    assert report["cpu_only_paths_available"] is True
