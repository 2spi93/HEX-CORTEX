from __future__ import annotations

from hex_cortex.memory.cortex_bundle_advanced import (
    build_cortex_bundle_advanced,
)
from hex_cortex.memory.cortex_bundle_core import build_cortex_bundle_core
from hex_cortex.memory.cortex_bus import combine_cortex_registries


def build_cortex_bundle():
    return combine_cortex_registries(
        build_cortex_bundle_core(),
        build_cortex_bundle_advanced(),
    )


def build_cortex_bundle_read_plan() -> list[dict[str, object]]:
    return [
        {"name": "domains.list", "kwargs": {}},
        {"name": "modal.list", "kwargs": {}},
        {"name": "providers.list", "kwargs": {}},
        {"name": "outputs.list", "kwargs": {}},
        {"name": "channels.list", "kwargs": {}},
        {"name": "asset.list", "kwargs": {}},
        {"name": "encode.list", "kwargs": {}},
        {"name": "links.list", "kwargs": {}},
        {"name": "preferences.profile", "kwargs": {}},
    ]
