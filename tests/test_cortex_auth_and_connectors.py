from hex_cortex.memory.cortex_auth_ref import CORTEX_AUTH_REF_FILENAME
from hex_cortex.memory.cortex_auth_ref import build_cortex_auth_ref
from hex_cortex.memory.cortex_auth_ref import register_cortex_auth_ref
from hex_cortex.memory.cortex_connectors import build_cortex_connector_plan
from hex_cortex.memory.cortex_connectors import list_cortex_connectors


def test_auth_reference_is_external_and_idempotent(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    auth_ref = build_cortex_auth_ref(provider="telegram", account="main")

    first = register_cortex_auth_ref(
        profile,
        provider="telegram",
        account="main",
        auth_ref=auth_ref,
        scopes=["read", "read"],
    )
    second = register_cortex_auth_ref(
        profile,
        provider="telegram",
        account="main",
        auth_ref=auth_ref,
        scopes=["read"],
    )

    record = first["auth_ref_records"][0]
    assert auth_ref == "keyring://hex-cortex/telegram/main"
    assert record["value_persisted"] is False
    assert record["external_store_required"] is True
    assert record["scopes"] == ["read"]
    assert first["auth_ref_count"] == 1
    assert second["auth_ref_count"] == 1
    assert (profile / CORTEX_AUTH_REF_FILENAME).exists()


def test_connector_catalog_contains_requested_services() -> None:
    providers = {row["provider"] for row in list_cortex_connectors()}

    assert providers == {
        "telegram",
        "linkedin",
        "instagram",
        "whatsapp",
        "reddit",
    }


def test_telegram_read_plan_does_not_require_callback() -> None:
    payload = build_cortex_connector_plan(provider="telegram", mode="read")

    assert payload["connection_allowed"] is True
    assert payload["callback_required"] is False
    assert payload["operator_required"] is False


def test_oauth_connector_requires_https_callback() -> None:
    blocked = build_cortex_connector_plan(provider="linkedin", mode="read")
    invalid = build_cortex_connector_plan(
        provider="linkedin",
        mode="read",
        callback_url="http://example.test/callback",
    )
    ready = build_cortex_connector_plan(
        provider="linkedin",
        mode="read",
        callback_url="https://example.test/callback",
    )

    assert blocked["blockers"] == ["callback_url_required"]
    assert invalid["blockers"] == ["callback_url_must_use_https"]
    assert ready["connection_allowed"] is True


def test_outbound_connector_requires_operator() -> None:
    payload = build_cortex_connector_plan(
        provider="telegram",
        mode="outbound",
    )

    assert payload["connection_allowed"] is True
    assert payload["operator_required"] is True
