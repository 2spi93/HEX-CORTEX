import json
from pathlib import Path

from hex_cortex.memory.cortex_operational_media_audit import audit_operational_media_encoder
from hex_cortex.memory.cortex_operational_media_cli import main


def test_operational_audit_on_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = audit_operational_media_encoder(root)

    assert payload["architecture_ready"] is True
    assert payload["operational_ready"] is False
    assert payload["profile_valid"] is True
    assert payload["network_probe_performed"] is False


def test_audit_cli(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    code = main(["audit", "--project-root", str(root)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True


def test_workflow_validate_cli(capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = root / "workflows" / "comfyui" / "txt2img_basic_api_v1.workflow.json"

    code = main(
        [
            "workflow-validate",
            str(workflow),
            "--allow-placeholders",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["workflow_valid"] is True


def test_workflow_import_cli(tmp_path, capsys) -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = root / "workflows" / "comfyui" / "txt2img_basic_api_v1.workflow.json"
    profile = root / "workflows" / "comfyui" / "txt2img_basic_api_v1.profile.json"

    code = main(
        [
            "workflow-import",
            str(workflow),
            str(profile),
            "--registry-root",
            str(tmp_path / "registry"),
            "--operator-approved",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["imported"] is True


def test_encoder_plan_cli(tmp_path, capsys) -> None:
    image = tmp_path / "image.bin"
    image.write_bytes(b"image")

    code = main(["encoder-plan", str(image)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["plan_allowed"] is True
    assert payload["local_files_only"] is True
