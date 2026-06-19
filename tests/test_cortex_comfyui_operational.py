import json

from hex_cortex.memory.cortex_comfyui_operational import bind_workflow
from hex_cortex.memory.cortex_comfyui_operational import import_workflow_bundle
from hex_cortex.memory.cortex_comfyui_operational import load_workflow_bundle
from hex_cortex.memory.cortex_comfyui_operational import probe_comfyui
from hex_cortex.memory.cortex_comfyui_operational import submit_and_wait
from hex_cortex.memory.cortex_comfyui_operational import validate_api_workflow


def _workflow():
    return {
        "1": {"class_type": "Source", "inputs": {"value": "__PROMPT__"}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "HEX"},
        },
    }


def _bindings():
    return {
        "prompt": {"node_id": "1", "input": "value", "required": True},
        "filename_prefix": {
            "node_id": "2",
            "input": "filename_prefix",
            "required": False,
        },
    }


def test_probe_checks_expected_endpoints() -> None:
    calls = []

    def transport(method, url, payload, timeout):
        calls.append(url)
        return {"ok": True}

    result = probe_comfyui(transport=transport)

    assert result["healthy"] is True
    assert calls == [
        "http://127.0.0.1:8188/system_stats",
        "http://127.0.0.1:8188/queue",
        "http://127.0.0.1:8188/object_info",
    ]


def test_validation_placeholder_modes() -> None:
    blocked = validate_api_workflow(_workflow())
    allowed = validate_api_workflow(_workflow(), allow_placeholders=True)

    assert blocked["workflow_valid"] is False
    assert allowed["workflow_valid"] is True


def test_import_bind_and_load(tmp_path) -> None:
    source = tmp_path / "workflow.json"
    source.write_text(json.dumps(_workflow()), encoding="utf-8")
    registry = tmp_path / "registry"

    result = import_workflow_bundle(
        source_path=source,
        registry_root=registry,
        workflow_id="demo.v1",
        capability="generate_image",
        bindings=_bindings(),
        allow_placeholders=True,
        operator_approved=True,
    )
    workflow, manifest = load_workflow_bundle(registry, "demo.v1")
    bound = bind_workflow(workflow, manifest, {"prompt": "diagram"})

    assert result["imported"] is True
    assert bound["1"]["inputs"]["value"] == "diagram"
    assert validate_api_workflow(bound)["workflow_valid"] is True


def test_import_requires_approval(tmp_path) -> None:
    source = tmp_path / "workflow.json"
    source.write_text(json.dumps(_workflow()), encoding="utf-8")

    result = import_workflow_bundle(
        source_path=source,
        registry_root=tmp_path / "registry",
        workflow_id="demo.v1",
        capability="generate_image",
        bindings=_bindings(),
        allow_placeholders=True,
        operator_approved=False,
    )

    assert result["imported"] is False
    assert "operator_approval_required" in result["blockers"]


def test_submit_and_wait_collects_output_manifest() -> None:
    workflow = _workflow()
    workflow["1"]["inputs"]["value"] = "ready"

    def transport(method, url, payload, timeout):
        if method == "POST":
            return {"prompt_id": "prompt-1"}
        return {
            "prompt-1": {
                "outputs": {
                    "2": {
                        "images": [
                            {"filename": "hex.png", "subfolder": "", "type": "output"}
                        ]
                    }
                }
            }
        }

    result = submit_and_wait(
        endpoint="http://127.0.0.1:8188",
        workflow=workflow,
        operator_approved=True,
        transport=transport,
        timeout_seconds=1.0,
    )

    assert result["status"] == "completed"
    assert result["output_manifest"][0]["filename"] == "hex.png"
