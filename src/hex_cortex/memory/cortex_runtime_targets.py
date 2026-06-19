from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class CortexRuntimeTarget:
    target_id: str
    kind: str
    endpoint: str
    platform: str
    priority: int = 50
    auth_ref: str | None = None
    enabled: bool = True


def build_cortex_runtime_targets(
    *targets: CortexRuntimeTarget,
) -> dict[str, CortexRuntimeTarget]:
    registry: dict[str, CortexRuntimeTarget] = {}
    for target in targets:
        validate_cortex_runtime_target(target)
        if target.target_id in registry:
            raise ValueError(f"duplicate runtime target: {target.target_id}")
        registry[target.target_id] = target
    return registry


def list_cortex_runtime_targets(
    registry: dict[str, CortexRuntimeTarget],
) -> list[dict[str, object]]:
    return [
        {
            "target_id": target.target_id,
            "kind": target.kind,
            "endpoint": target.endpoint,
            "platform": target.platform,
            "priority": target.priority,
            "auth_ref": target.auth_ref,
            "auth_value_persisted": False,
            "enabled": target.enabled,
        }
        for target in sorted(registry.values(), key=lambda item: item.target_id)
    ]


def default_cortex_runtime_targets(
    *,
    linux_endpoint: str = "https://llama-server.invalid",
    linux_auth_ref: str | None = None,
) -> dict[str, CortexRuntimeTarget]:
    return build_cortex_runtime_targets(
        CortexRuntimeTarget(
            target_id="windows-ollama",
            kind="ollama",
            endpoint="http://127.0.0.1:11434",
            platform="windows",
            priority=90,
        ),
        CortexRuntimeTarget(
            target_id="linux-llama-server",
            kind="openai_compatible",
            endpoint=linux_endpoint,
            platform="linux",
            priority=100,
            auth_ref=linux_auth_ref,
        ),
    )


def validate_cortex_runtime_target(target: CortexRuntimeTarget) -> None:
    if not target.target_id or not target.target_id.replace("-", "").isalnum():
        raise ValueError("target_id must use alphanumeric characters and hyphens")
    if target.kind not in {"ollama", "openai_compatible"}:
        raise ValueError("runtime kind is unsupported")
    if target.platform not in {"windows", "linux", "macos", "server", "unknown"}:
        raise ValueError("runtime platform is unsupported")
    if target.priority < 0 or target.priority > 100:
        raise ValueError("runtime priority must be in [0, 100]")
    parsed = urlparse(target.endpoint)
    if parsed.username or parsed.password:
        raise ValueError("runtime endpoint must not contain credentials")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("runtime endpoint must use http or https")
    if not parsed.hostname:
        raise ValueError("runtime endpoint must include a hostname")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme == "http" and parsed.hostname not in local_hosts:
        raise ValueError("remote runtime endpoints must use https")
    if parsed.scheme == "http" and parsed.port is None:
        raise ValueError("local runtime endpoint must include an explicit port")
