from __future__ import annotations

from hex_cortex.memory.cortex_auth_ref import build_cortex_auth_ref
from hex_cortex.memory.cortex_auth_ref import register_cortex_auth_ref
from hex_cortex.memory.cortex_bridge_detect import detect_cortex_bridge_transport
from hex_cortex.memory.cortex_bridge_detect import list_cortex_bridge_transports
from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_caddy import render_cortex_caddyfile
from hex_cortex.memory.cortex_connectors import build_cortex_connector_plan
from hex_cortex.memory.cortex_connectors import list_cortex_connectors
from hex_cortex.memory.cortex_exchange import build_cortex_exchange_packet
from hex_cortex.memory.cortex_exchange import verify_cortex_exchange_packet
from hex_cortex.memory.cortex_project_fit import analyze_cortex_project_fit
from hex_cortex.memory.cortex_research_flow import run_cortex_research_flow
from hex_cortex.memory.cortex_runtime_health import probe_cortex_runtime_targets
from hex_cortex.memory.cortex_runtime_select import build_cortex_runtime_benchmark_plan
from hex_cortex.memory.cortex_runtime_select import select_cortex_runtime_target
from hex_cortex.memory.cortex_runtime_targets import list_cortex_runtime_targets
from hex_cortex.memory.cortex_service_profile import build_cortex_service_profile


def build_cortex_wave3_link() -> dict[str, CortexUnit]:
    return {
        "runtime.targets": CortexUnit(
            name="runtime.targets",
            unit=list_cortex_runtime_targets,
            description="List configured local and server model runtimes.",
        ),
        "runtime.health": CortexUnit(
            name="runtime.health",
            unit=probe_cortex_runtime_targets,
            description="Probe runtime health and model inventories.",
        ),
        "runtime.select": CortexUnit(
            name="runtime.select",
            unit=select_cortex_runtime_target,
            description="Select the best healthy compatible runtime.",
        ),
        "runtime.benchmark.plan": CortexUnit(
            name="runtime.benchmark.plan",
            unit=build_cortex_runtime_benchmark_plan,
            description="Build a bounded runtime benchmark plan.",
        ),
        "research.flow": CortexUnit(
            name="research.flow",
            unit=run_cortex_research_flow,
            description="Run cited search and optional crawl stages.",
        ),
        "auth.ref.build": CortexUnit(
            name="auth.ref.build",
            unit=build_cortex_auth_ref,
            description="Build an external authentication reference.",
        ),
        "auth.ref.register": CortexUnit(
            name="auth.ref.register",
            unit=register_cortex_auth_ref,
            description="Persist an authentication reference receipt.",
            mutates_receipt=True,
        ),
        "connectors.list": CortexUnit(
            name="connectors.list",
            unit=list_cortex_connectors,
            description="List external connector capabilities.",
        ),
        "connector.plan": CortexUnit(
            name="connector.plan",
            unit=build_cortex_connector_plan,
            description="Build an external connector plan.",
        ),
        "bridge.transports": CortexUnit(
            name="bridge.transports",
            unit=list_cortex_bridge_transports,
            description="List ordered bridge transports.",
        ),
        "bridge.detect": CortexUnit(
            name="bridge.detect",
            unit=detect_cortex_bridge_transport,
            description="Select the best available bridge transport.",
        ),
        "exchange.build": CortexUnit(
            name="exchange.build",
            unit=build_cortex_exchange_packet,
            description="Build a signed bounded exchange packet.",
            mutates_receipt=True,
        ),
        "exchange.verify": CortexUnit(
            name="exchange.verify",
            unit=verify_cortex_exchange_packet,
            description="Verify a bounded exchange packet.",
        ),
        "project.fit": CortexUnit(
            name="project.fit",
            unit=analyze_cortex_project_fit,
            description="Detect overlap before integrating a project.",
        ),
        "service.profile": CortexUnit(
            name="service.profile",
            unit=build_cortex_service_profile,
            description="Build a secure loopback service profile.",
        ),
        "service.caddy": CortexUnit(
            name="service.caddy",
            unit=render_cortex_caddyfile,
            description="Render a Caddy reverse-proxy configuration.",
        ),
    }
