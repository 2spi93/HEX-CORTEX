import json

from hex_cortex.memory.cortex_next_wave_cli import main


def test_next_wave_audit_cli(capsys, tmp_path) -> None:
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

    code = main(["audit", "--project-root", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True
    assert payload["operational_ready"] is False
    assert payload["network_probe_performed"] is False


def test_media_plan_cli_is_offline_by_default(capsys) -> None:
    code = main(["media-plan", "generate_image", "A geometric icon"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "planned"
    assert payload["selected_runtime_id"] == "media.comfyui.image"
    assert payload["network_call_performed"] is False


def test_latent_spec_cli(capsys) -> None:
    code = main(
        [
            "latent-spec",
            "--latent-dim",
            "16",
            "--action-dim",
            "3",
            "--horizons",
            "1,4,8",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["spec_allowed"] is True
    assert payload["latent_dim"] == 16
    assert payload["horizons"] == [1, 4, 8]


def test_latent_demo_cli(capsys) -> None:
    code = main(["latent-demo", "--latent-dim", "3", "--action-dim", "2"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["experiment_allowed"] is True
    assert payload["evaluation"]["surprising"] is False
    assert payload["network_call_performed"] is False


def test_candidate_evaluation_cli(capsys) -> None:
    baseline = json.dumps(
        {
            "prediction_error": 0.20,
            "surprise_calibration": 0.70,
            "planning_success": 0.60,
        }
    )
    candidate = json.dumps(
        {
            "prediction_error": 0.15,
            "surprise_calibration": 0.75,
            "planning_success": 0.66,
        }
    )

    code = main(["evaluate-candidate", baseline, candidate])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["evaluation_allowed"] is True
    assert payload["promotion_allowed"] is True
