from __future__ import annotations

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_surfaces import audit_cortex_surface
from hex_cortex.memory.cortex_surfaces import build_cortex_surface_manifest
from hex_cortex.memory.cortex_surfaces import list_cortex_surfaces
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring
from hex_cortex.memory.cortex_wiring import list_cortex_runtime_facts
from hex_cortex.memory.cortex_wiring import list_cortex_wiring_stages


def build_cortex_diag_link() -> dict[str, CortexUnit]:
    return {
        "wiring.audit": CortexUnit(
            name="wiring.audit",
            unit=audit_cortex_wiring,
            description="Audit static wiring and runtime facts.",
        ),
        "wiring.stages": CortexUnit(
            name="wiring.stages",
            unit=list_cortex_wiring_stages,
            description="List architecture wiring stages.",
        ),
        "runtime.facts": CortexUnit(
            name="runtime.facts",
            unit=list_cortex_runtime_facts,
            description="List runtime facts required for operation.",
        ),
        "surfaces.list": CortexUnit(
            name="surfaces.list",
            unit=list_cortex_surfaces,
            description="List supported deployment surfaces.",
        ),
        "surface.audit": CortexUnit(
            name="surface.audit",
            unit=audit_cortex_surface,
            description="Audit one deployment surface.",
        ),
        "surface.manifest": CortexUnit(
            name="surface.manifest",
            unit=build_cortex_surface_manifest,
            description="Build one deployment surface manifest.",
        ),
    }
