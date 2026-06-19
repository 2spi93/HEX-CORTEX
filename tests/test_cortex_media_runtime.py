import pytest

from hex_cortex.memory.cortex_media_runtime import build_media_job
from hex_cortex.memory.cortex_media_runtime import build_media_runtime_descriptors
from hex_cortex.memory.cortex_media_runtime import orchestrate_media_runtime
from hex_cortex.memory.cortex_media_runtime import probe_media_runtime
from hex_cortex.memory.cortex_media_runtime import submit_media_job


def test_media_descriptors_are_local_and_output_specific() -> None:
    rows = build_media_runtime_descriptors()

    assert len(rows) == 3
    assert all(row["local_only"] is True for row in rows)
    assert rows[0]["supported_outputs"] == ["generate_image"]
    assert "generate_3d_scene" in rows[2]["supported_outputs"]


def test_media_descriptor_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        build_media_runtime_descriptors(comfyui_endpoint="https://example.com:8188")


def test_media_health_probe_collects_redacted_device_summary() -> None:
    descriptor = build_media_runtime_descriptors()[0]

    def transport(method, url, payload, timeout):
        assert method == "GET"
        assert url.endswith("/system_stats")
        assert payload is None
        return {
            "devices": [
                {
                    "name": "GPU-0",
                    "type": "cuda",
                    "vram_total": 12_000,
                    "vram_free": 8_000,
                    "sensitive": "not persisted",
                }
            ]
        }

    receipt = probe_media_runtime(descriptor, transport=transport)

    assert receipt["healthy"] is True
    assert receipt["device_count"] == 1
    assert receipt["devices"][0] == {
        "name": "GPU-0",
        "type": "cuda",
        "vram_total": 12_000,
        "vram_free": 8_000,
    }
    assert receipt["raw_response_persisted"] is False


def test_media_job_is_bounded_and_hash_only() -> None:
    job = build_media_job(
        output_id="generate_video",
        prompt="A short geometric animation",
        width=1280,
        height=720,
        frames=48,
        seed=7,
    )

    assert job["job_allowed"] is True
    assert job["prompt_persisted"] is False
    assert job["negative_prompt_persisted"] is False
    assert len(job["prompt_hash"]) == 64
    assert job["generation_performed"] is False


def test_media_job_rejects_invalid_dimensions() -> None:
    job = build_media_job(
        output_id="generate_image",
        prompt="test",
        width=100,
        height=100,
    )

    assert job["job_allowed"] is False
    assert "dimensions_invalid" in job["blockers"]


def test_media_submission_requires_operator_for_network() -> None:
    descriptor = build_media_runtime_descriptors()[0]
    job = build_media_job(output_id="generate_image", prompt="test")

    receipt = submit_media_job(
        descriptor,
        job=job,
        workflow={"1": {"class_type": "Example"}},
        execute_network=True,
        operator_approved=False,
    )

    assert receipt["status"] == "blocked"
    assert receipt["network_call_performed"] is False
    assert "operator_approval_required" in receipt["blockers"]


def test_media_submission_can_submit_to_mock_transport() -> None:
    descriptor = build_media_runtime_descriptors()[0]
    job = build_media_job(output_id="generate_image", prompt="test")

    def transport(method, url, payload, timeout):
        assert method == "POST"
        assert url.endswith("/prompt")
        assert "prompt" in payload
        return {"prompt_id": "prompt-123"}

    receipt = submit_media_job(
        descriptor,
        job=job,
        workflow={"1": {"class_type": "Example"}},
        execute_network=True,
        operator_approved=True,
        transport=transport,
    )

    assert receipt["status"] == "submitted"
    assert receipt["prompt_id"] == "prompt-123"
    assert receipt["network_call_performed"] is True
    assert receipt["raw_workflow_persisted"] is False


def test_media_orchestrator_is_offline_by_default() -> None:
    payload = orchestrate_media_runtime(
        output_id="generate_image",
        prompt="test",
    )

    assert payload["status"] == "planned"
    assert payload["selected_runtime_id"] == "media.comfyui.image"
    assert payload["network_call_performed"] is False
    assert payload["generation_performed"] is False
