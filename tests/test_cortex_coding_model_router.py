import pytest

from hex_cortex.memory.cortex_coding_model_router import build_coding_model_catalog
from hex_cortex.memory.cortex_coding_model_router import route_coding_task


def test_catalog_contains_local_and_remote_without_raw_secrets() -> None:
    payload = build_coding_model_catalog()

    assert payload["status"] == "ready"
    assert [row["provider_id"] for row in payload["providers"]] == [
        "local_open_weight",
        "remote_api",
    ]
    assert payload["raw_secret_persistence_allowed"] is False
    assert payload["fallback_policy"] == "explicit_receipted_no_silent_substitution"


def test_catalog_rejects_non_local_local_endpoint() -> None:
    with pytest.raises(ValueError):
        build_coding_model_catalog(local_endpoint="https://example.com:8080")


def test_secret_context_requires_local_provider() -> None:
    payload = route_coding_task(
        task_class="complex_patch",
        context_sensitivity="secret",
        complexity="high",
        local_available=False,
        remote_available=True,
        operator_allows_remote=True,
    )

    assert payload["status"] == "blocked"
    assert payload["selected_provider_id"] is None
    assert payload["blockers"] == ["local_provider_required_for_secret_context"]


def test_remote_provider_requires_operator_authorization() -> None:
    local_fallback = route_coding_task(
        task_class="final_review",
        complexity="high",
        local_available=True,
        remote_available=True,
        operator_allows_remote=False,
    )
    remote = route_coding_task(
        task_class="final_review",
        complexity="high",
        local_available=True,
        remote_available=True,
        operator_allows_remote=True,
    )

    assert local_fallback["selected_provider_id"] == "local_open_weight"
    assert remote["selected_provider_id"] == "remote_api"
    assert remote["fallback_silent"] is False
