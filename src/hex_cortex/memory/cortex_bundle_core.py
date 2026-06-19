from __future__ import annotations

from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_provider_extra import (
    build_cortex_provider_extra_registry,
)
from hex_cortex.memory.cortex_provider_registry import (
    build_cortex_provider_registry,
)
from hex_cortex.memory.cortex_registry import build_cortex_registry
from hex_cortex.memory.cortex_world_flow import build_cortex_world_flow_registry


def build_cortex_bundle_core():
    return combine_cortex_registries(
        build_cortex_registry(),
        build_cortex_provider_registry(),
        build_cortex_provider_extra_registry(),
        build_cortex_world_flow_registry(),
    )
