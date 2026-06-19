from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime


def test_runtime_probe_detects_observed_training_contracts(tmp_path) -> None:
    memory_root = tmp_path / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    for name in (
        "cortex_observed_transition_dataset.py",
        "cortex_compact_world_model.py",
        "cortex_world_training_cli.py",
    ):
        (memory_root / name).touch()

    payload = probe_cortex_runtime(tmp_path)
    facts = payload["runtime_facts"]

    assert facts["observed_transition_dataset_available"] is True
    assert facts["compact_world_model_trainer_available"] is True
    assert facts["world_model_training_cli_available"] is True
    assert facts["observed_transition_dataset_ready"] is False
    assert facts["active_compact_world_model_available"] is False
