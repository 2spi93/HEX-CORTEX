from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime


def test_runtime_probe_detects_media_to_latent_contracts(tmp_path) -> None:
    memory_root = tmp_path / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    (memory_root / "cortex_media_to_latent_pipeline.py").touch()
    (memory_root / "cortex_media_to_latent_cli.py").touch()

    payload = probe_cortex_runtime(tmp_path)
    facts = payload["runtime_facts"]

    assert facts["media_to_latent_pipeline_available"] is True
    assert facts["media_to_latent_cli_available"] is True
    assert facts["media_to_latent_operational"] is False
