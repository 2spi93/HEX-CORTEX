from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime


def test_runtime_probe_detects_next_wave_contracts(tmp_path) -> None:
    memory_root = tmp_path / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    for filename in (
        "cortex_media_runtime.py",
        "cortex_latent_lab.py",
        "cortex_latent_experiment.py",
        "cortex_world_model_eval.py",
        "cortex_next_wave_cli.py",
    ):
        (memory_root / filename).touch()

    payload = probe_cortex_runtime(tmp_path)
    facts = payload["runtime_facts"]

    assert facts["media_runtime_contract_available"] is True
    assert facts["latent_world_model_lab_available"] is True
    assert facts["world_model_training_evaluation_available"] is True
    assert facts["next_wave_cli_available"] is True
    assert facts["media_runtime_available"] is False
    assert facts["comfyui_endpoint_configured"] is False
    assert facts["learned_world_model_available"] is False
