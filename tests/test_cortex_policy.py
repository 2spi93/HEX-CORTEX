from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_policy import CortexMode
from hex_cortex.memory.cortex_policy import decide_cortex_unit_access


def test_policy_blocks_unknown_unit() -> None:
    decision = decide_cortex_unit_access(
        mode=CortexMode.AUTO_SAFE,
        unit_name="web.search",
        registry={},
    )

    assert decision.allowed is False
    assert decision.reason == "unknown_unit_requires_registration"
    assert decision.needs_operator is True


def test_policy_auto_safe_allows_registered_readonly_unit() -> None:
    registry = {
        "web.describe": CortexUnit(
            name="web.describe",
            unit=lambda: {"ok": True},
            description="read-only web descriptor",
        )
    }

    decision = decide_cortex_unit_access(
        mode=CortexMode.AUTO_SAFE,
        unit_name="web.describe",
        registry=registry,
    )

    assert decision.allowed is True
    assert decision.reason == "auto_safe_allowed_registered_unit"
    assert decision.needs_operator is False


def test_policy_auto_safe_blocks_operator_unit_without_trusted_plan() -> None:
    registry = {
        "b.build": CortexUnit(
            name="b.build",
            unit=lambda: {"ok": True},
            description="operator unit",
            requires_operator=True,
        )
    }

    decision = decide_cortex_unit_access(
        mode=CortexMode.AUTO_SAFE,
        unit_name="b.build",
        registry=registry,
        trusted_plan=False,
    )

    assert decision.allowed is False
    assert decision.reason == "auto_safe_requires_trusted_plan_for_operator_units"


def test_policy_auto_safe_allows_operator_unit_with_trusted_plan() -> None:
    registry = {
        "b.build": CortexUnit(
            name="b.build",
            unit=lambda: {"ok": True},
            description="operator unit",
            requires_operator=True,
        )
    }

    decision = decide_cortex_unit_access(
        mode=CortexMode.AUTO_SAFE,
        unit_name="b.build",
        registry=registry,
        trusted_plan=True,
    )

    assert decision.allowed is True
    assert decision.reason == "auto_safe_allowed_registered_unit"
