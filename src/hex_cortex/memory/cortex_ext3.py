from __future__ import annotations

from hex_cortex.memory.cortex_account import build_cortex_account_receipt
from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_encode import build_cortex_encode_receipt
from hex_cortex.memory.cortex_encode import list_cortex_encoders
from hex_cortex.memory.cortex_lane import build_cortex_output_receipt
from hex_cortex.memory.cortex_lane import build_cortex_tool_receipt
from hex_cortex.memory.cortex_lane import build_cortex_visual_receipt
from hex_cortex.memory.cortex_lane import build_cortex_voice_receipt
from hex_cortex.memory.cortex_media import evaluate_cortex_media_candidate
from hex_cortex.memory.cortex_media import list_cortex_media_providers
from hex_cortex.memory.cortex_media_receipt import build_cortex_media_receipt
from hex_cortex.memory.cortex_pick import build_cortex_pick
from hex_cortex.memory.cortex_route import build_cortex_route_receipt
from hex_cortex.memory.cortex_route import list_cortex_routes


def build_cortex_ext3() -> dict[str, CortexUnit]:
    return {
        "action.pick": CortexUnit(
            name="action.pick",
            unit=build_cortex_pick,
            description="Select one ranked proposal.",
            mutates_receipt=True,
        ),
        "action.route": CortexUnit(
            name="action.route",
            unit=build_cortex_route_receipt,
            description="Route one selected proposal.",
            mutates_receipt=True,
        ),
        "routes.list": CortexUnit(
            name="routes.list",
            unit=list_cortex_routes,
            description="List output routes.",
        ),
        "asset.list": CortexUnit(
            name="asset.list",
            unit=list_cortex_media_providers,
            description="List asset candidates.",
        ),
        "asset.check": CortexUnit(
            name="asset.check",
            unit=evaluate_cortex_media_candidate,
            description="Check one asset candidate.",
        ),
        "asset.receipt": CortexUnit(
            name="asset.receipt",
            unit=build_cortex_media_receipt,
            description="Build one asset receipt.",
            mutates_receipt=True,
        ),
        "encode.list": CortexUnit(
            name="encode.list",
            unit=list_cortex_encoders,
            description="List encoder candidates.",
        ),
        "encode.receipt": CortexUnit(
            name="encode.receipt",
            unit=build_cortex_encode_receipt,
            description="Build one encoder receipt.",
            mutates_receipt=True,
        ),
        "account.receipt": CortexUnit(
            name="account.receipt",
            unit=build_cortex_account_receipt,
            description="Build one account receipt.",
            mutates_receipt=True,
        ),
        "output.receipt": CortexUnit(
            name="output.receipt",
            unit=build_cortex_output_receipt,
            description="Build one local output receipt.",
            mutates_receipt=True,
        ),
        "tool.receipt": CortexUnit(
            name="tool.receipt",
            unit=build_cortex_tool_receipt,
            description="Build one tool receipt.",
            mutates_receipt=True,
        ),
        "voice.receipt": CortexUnit(
            name="voice.receipt",
            unit=build_cortex_voice_receipt,
            description="Build one voice receipt.",
            mutates_receipt=True,
        ),
        "visual.receipt": CortexUnit(
            name="visual.receipt",
            unit=build_cortex_visual_receipt,
            description="Build one visual receipt.",
            mutates_receipt=True,
        ),
    }
