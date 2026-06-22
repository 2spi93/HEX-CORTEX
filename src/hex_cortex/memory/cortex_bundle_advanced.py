from __future__ import annotations

from hex_cortex.memory.cortex_action_link import build_cortex_action_link
from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_channel_link import build_cortex_channel_link
from hex_cortex.memory.cortex_cognitive_brain_registry_units import (
    build_cognitive_brain_registry,
)
from hex_cortex.memory.cortex_cognitive_genome_registry_v2 import (
    build_cognitive_genome_registry,
)
from hex_cortex.memory.cortex_cognitive_memory_registry import (
    build_cognitive_memory_registry,
)
from hex_cortex.memory.cortex_diag_link import build_cortex_diag_link
from hex_cortex.memory.cortex_ext3 import build_cortex_ext3
from hex_cortex.memory.cortex_goal_link import build_cortex_goal_link
from hex_cortex.memory.cortex_seq_link import build_cortex_seq_link
from hex_cortex.memory.cortex_surprise_registry import (
    build_cortex_surprise_registry,
)
from hex_cortex.memory.cortex_transition_registry import (
    build_cortex_transition_registry,
)
from hex_cortex.memory.cortex_verified_cognition_registry import (
    build_verified_cognition_registry,
)
from hex_cortex.memory.cortex_xlink import build_cortex_xlink


def build_cortex_bundle_advanced():
    return combine_cortex_registries(
        build_cortex_transition_registry(),
        build_cortex_surprise_registry(),
        build_cortex_seq_link(),
        build_cortex_goal_link(),
        build_cortex_action_link(),
        build_cortex_channel_link(),
        build_cortex_ext3(),
        build_cortex_xlink(),
        build_cortex_diag_link(),
        build_cognitive_genome_registry(),
        build_cognitive_memory_registry(),
        build_cognitive_brain_registry(),
        build_verified_cognition_registry(),
    )
