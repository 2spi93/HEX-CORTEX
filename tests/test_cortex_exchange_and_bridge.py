import hashlib
import hmac

from hex_cortex.memory.cortex_bridge_detect import detect_cortex_bridge_transport
from hex_cortex.memory.cortex_bridge_detect import list_cortex_bridge_transports
from hex_cortex.memory.cortex_exchange import build_cortex_exchange_packet
from hex_cortex.memory.cortex_exchange import verify_cortex_exchange_packet


def test_bridge_detection_uses_required_order() -> None:
    payload = detect_cortex_bridge_transport(
        {
            "mcp_available": True,
            "openai_models_available": True,
            "declared_api_available": True,
            "cli_stdio_available": True,
        }
    )

    assert payload["selected_transport"] == "mcp"
    assert payload["shared_memory"] is False
    assert [row["transport"] for row in list_cortex_bridge_transports()] == [
        "mcp",
        "openai_compatible",
        "declared_api",
        "cli_stdio",
    ]


def test_bridge_detection_falls_back_to_cli() -> None:
    payload = detect_cortex_bridge_transport(
        {"cli_stdio_available": True}
    )

    assert payload["detection_allowed"] is True
    assert payload["selected_transport"] == "cli_stdio"


def test_exchange_packet_preserves_memory_boundary() -> None:
    signing_material = b"test-only-material"

    def signer(body: bytes) -> str:
        return hmac.new(signing_material, body, hashlib.sha256).hexdigest()

    def verifier(body: bytes, signature: str) -> bool:
        expected = hmac.new(signing_material, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    packet = build_cortex_exchange_packet(
        source="hex-cortex",
        target="hermes-local",
        capability="research",
        request={"query": "bounded"},
        signer=signer,
    )
    result = verify_cortex_exchange_packet(
        packet,
        verifier=verifier,
        now_epoch=int(packet["expires_at_epoch"]) - 1,
    )

    assert packet["memory_shared"] is False
    assert packet["raw_request_persisted"] is False
    assert result["verification_allowed"] is True
    assert result["memory_boundary_preserved"] is True


def test_exchange_packet_rejects_changed_memory_boundary() -> None:
    packet = build_cortex_exchange_packet(
        source="hex-cortex",
        target="hermes-server",
        capability="tool",
        request={"task": "bounded"},
        signer=lambda body: "signature",
    )
    packet["memory_shared"] = True

    result = verify_cortex_exchange_packet(
        packet,
        verifier=lambda body, signature: True,
        now_epoch=int(packet["expires_at_epoch"]) - 1,
    )

    assert result["verification_allowed"] is False
    assert result["blockers"] == ["memory_boundary_violated"]
