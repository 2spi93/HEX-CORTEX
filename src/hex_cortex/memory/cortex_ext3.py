from __future__ import annotations

from hex_cortex.memory.cortex_account import build_cortex_account_receipt
from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_encode import build_cortex_encode_receipt
from hex_cortex.memory.cortex_encode import list_cortex_encoders
from hex_cortex.memory.cortex_media import evaluate_cortex_media_candidate
from hex_cortex.memory.cortex_media import list_cortex_media_providers
from hex_cortex.memory.cortex_media_receipt import build_cortex_media_receipt
from hex_cortex.memory.cortex_pick import build_cortex_pick


def build_cortex_ext3() -> dict[str, CortexUnit]:
    return {
        "action.pick": CortexUnit(
            name="action.pick",
            unit=build_cortex_pick,
            description="Select one ranked proposal.",
            mutates_receipt=True,
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
    }
