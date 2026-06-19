import pytest

from hex_cortex.memory.cortex_hardware_adapter import build_cortex_hardware_adapter
from hex_cortex.memory.cortex_project_adapter import build_cortex_project_adapter
from hex_cortex.memory.cortex_service_adapter import build_cortex_service_adapter


def test_project_adapter_contract() -> None:
    adapter = build_cortex_project_adapter(
        project_id="alpha",
        handler=lambda request: {"status": "ok"},
    )

    assert adapter.name == "project.alpha"
    assert adapter.lane == "tool"
    assert adapter.requires_operator is True
    assert adapter.local_process_capable is True
    assert adapter.auto_safe_capable is False


def test_hardware_adapter_contract() -> None:
    adapter = build_cortex_hardware_adapter(
        device_id="camera_a",
        handler=lambda request: {"status": "ok"},
        lane="visual",
    )

    assert adapter.name == "hardware.camera_a"
    assert adapter.lane == "visual"
    assert adapter.requires_operator is True
    assert adapter.local_process_capable is True
    assert adapter.auto_safe_capable is False


def test_service_adapter_contract() -> None:
    adapter = build_cortex_service_adapter(
        service_id="control_plane",
        handler=lambda request: {"status": "ok"},
        requires_operator=False,
        auto_safe_capable=True,
    )

    assert adapter.name == "service.control_plane"
    assert adapter.network_capable is True
    assert adapter.requires_operator is False
    assert adapter.auto_safe_capable is True


def test_adapter_factories_reject_unsafe_identifiers() -> None:
    with pytest.raises(ValueError):
        build_cortex_project_adapter(
            project_id="bad/value",
            handler=lambda request: {},
        )
    with pytest.raises(ValueError):
        build_cortex_hardware_adapter(
            device_id="bad value",
            handler=lambda request: {},
        )
    with pytest.raises(ValueError):
        build_cortex_service_adapter(
            service_id="BAD",
            handler=lambda request: {},
        )
